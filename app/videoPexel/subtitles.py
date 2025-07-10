import json
import os
import re
import subprocess
from app.config.ffmpeg import get_temp_files_pexel_path
from app.videoPexel.config import LOGO_SCALE
from app.services.speech_service import transcribe_with_timestamps_v2 as transcribe_audio

def split_long_sentence(sentence, max_words=12, max_chars=60, format_type="desktop"):
    """
    Divide uma frase longa em partes menores para melhor legibilidade.

    Recebe uma frase e divide em partes menores baseado em limites de palavras e caracteres,
    considerando o formato do vídeo (desktop/mobile). Tenta fazer divisões naturais em pontuações.

    Args:
        sentence (str): A frase a ser dividida
        max_words (int, optional): Número máximo de palavras por linha. Padrão é 12.
        max_chars (int, optional): Número máximo de caracteres por linha. Padrão é 60.
        format_type (str, optional): Tipo de formato do vídeo ('desktop' ou 'mobile'). Padrão é 'desktop'.

    Returns:
        list: Lista de strings contendo as partes da frase dividida.
              Se a frase original estiver dentro dos limites, retorna lista com apenas a frase original.
    """
    # Ajusta limites baseado no formato
    if format_type == "mobile":
        max_words = 6  # Palavras por linha para mobile
        max_chars = 30  # Caracteres por linha para mobile
    
    words = sentence.split()
    if len(words) <= max_words and len(sentence) <= max_chars:
        return [sentence]
        
    # Tenta dividir em duas linhas naturalmente
    mid_point = len(words) // 2
    
    # Procura por pontuações naturais próximas ao meio
    for i in range(mid_point - 2, mid_point + 2):
        if i > 0 and i < len(words):
            if words[i-1].endswith((',', ';', ':', '-')):
                mid_point = i
                break
    
    line1 = ' '.join(words[:mid_point])
    line2 = ' '.join(words[mid_point:])
    
    return [line1, line2]


def add_subtitles(video_path, transcription, format_type, output_path, start_delay=5.0):
    """
    Adiciona legendas a um vídeo usando FFmpeg.

    Recebe um vídeo e sua transcrição com timestamps, e gera um novo vídeo com legendas
    sobrepostas. As legendas são formatadas e posicionadas de acordo com o tipo de formato
    do vídeo (desktop/mobile).

    Args:
        video_path (str): Caminho do arquivo de vídeo de entrada
        transcription (list): Lista de dicionários contendo as palavras e seus timestamps
        format_type (str): Tipo de formato do vídeo ('desktop' ou 'mobile')
        output_path (str): Caminho onde o vídeo com legendas será salvo
        start_delay (float, optional): Atraso inicial em segundos antes da primeira legenda. 
                                     Padrão é 5.0 segundos.

    Returns:
        str: Caminho do vídeo com legendas adicionadas em caso de sucesso
        None: Em caso de erro
    """
    try:
        if not os.path.exists(video_path):
            print(f"ERRO: Vídeo não encontrado em: {video_path}")
            return None

        print(f"format_type: {format_type}")
        
        # Define o tamanho da fonte baseado no formato
        font_sizes = {
            "mobile": "h/50",
            "desktop": "h/30",
            "stories": "h/15",
        }
        font_size = font_sizes.get(format_type, "h/30")
        print(f"Usando tamanho de fonte: {font_size} para formato {format_type}")

        # Agrupa palavras em frases maiores
        current_phrase = []
        phrases = []
        current_start = None
        last_end_time = 0
        
        for word in transcription:
            if not isinstance(word, dict) or 'word' not in word:
                continue
                
            if current_start is None:
                current_start = float(word.get('start_time', 0))
                
            current_phrase.append(word['word'])
            current_end = float(word.get('end_time', 0))
            
            # Condições para quebrar a frase:
            # 1. Palavra termina com pontuação forte
            # 2. Frase tem mais de X palavras
            # 3. Gap de tempo grande entre palavras (pausa natural)
            if (word['word'].strip().endswith(('.', '!', '?')) or 
                len(current_phrase) >= 15 or  # Aumentado para frases maiores
                (len(current_phrase) > 5 and current_end - last_end_time > 0.5)):  # Pausa de 0.5s
                
                phrases.append({
                    'text': ' '.join(current_phrase),
                    'start': current_start + start_delay,
                    'end': current_end + start_delay #+ 0.3  # Pequeno delay extra no final
                })
                current_phrase = []
                current_start = None
            
            last_end_time = current_end
        
        # Adiciona última frase se houver
        if current_phrase:
            last_word = transcription[-1]
            phrases.append({
                'text': ' '.join(current_phrase),
                'start': current_start + start_delay,
                'end': float(last_word.get('end_time', 0)) + start_delay + 0.3
            })

        print("\nFrases processadas:")
        for phrase in phrases:
            print(f"Texto: {phrase['text']}")
            print(f"Início: {phrase['start']:.1f}s")
            print(f"Fim: {phrase['end']:.1f}s\n")

        # Constrói o filtro de legendas
        filter_complex = []
        
        for i, phrase in enumerate(phrases):
            text = phrase['text'].strip()
            if not text:
                continue
                
            # Escapa caracteres especiais
            text = text.replace("'", "\\'").replace('"', '\\"')
            
            # Divide texto longo em duas linhas se necessário
            lines = split_long_sentence(text, format_type=format_type)
            
            # Ajusta posição vertical baseado no número de linhas
            y_positions = ['h*0.85', 'h*0.9'] if len(lines) > 1 else ['h*0.9']
            
            for line_num, line in enumerate(lines):
                filter_text = (
                    f"drawtext=text='{line}':fontfile=/projetos/yduqs_back/fonte/Poppins-Bold.ttf"
                    f":fontcolor=white:fontsize={font_size}:box=1:boxcolor=black@0.7"
                    f":boxborderw=10:x=(w-text_w)/2:y={y_positions[line_num]}"
                    f":enable='between(t,{phrase['start']},{phrase['end']})':line_spacing=10"
                )
                filter_complex.append(filter_text)

        # Junta todos os filtros
        final_filter = ','.join(filter_complex)
        
        # Prepara o comando ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", final_filter,
            "-c:a", "copy",
            output_path
        ]

        print("\nComando ffmpeg:")
        print(" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Erro ao adicionar legendas: {result.stderr}")
            return None

        print("Legendas adicionadas com sucesso!")
        return output_path

    except Exception as e:
        print(f"Erro ao adicionar legendas: {str(e)}")
        if hasattr(e, '__traceback__'):
            import traceback
            print("Traceback completo:")
            traceback.print_tb(e.__traceback__)
        return None

def get_video_duration(video_path):
    """
    Obtém a duração de um arquivo de vídeo em segundos.

    Utiliza o ffprobe para extrair a duração do vídeo especificado.

    Args:
        video_path (str): Caminho do arquivo de vídeo

    Returns:
        float: Duração do vídeo em segundos
        0: Em caso de erro ou se não for possível obter a duração
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        return 0
    except:
        return 0

def add_logo_and_blur(video_path, format_type, output_path, duration=None, start_time=0):
    """
    Adiciona logo com efeito de blur ao vídeo.

    Recebe um vídeo e adiciona uma logo com efeito de blur ao fundo. A logo é posicionada 
    no centro do vídeo e dimensionada de acordo com o formato (desktop/mobile). O fundo 
    da logo recebe um efeito de desfoque (blur) para melhor visibilidade.

    Args:
        video_path (str): Caminho do arquivo de vídeo de entrada
        format_type (str): Tipo de formato do vídeo ('desktop' ou 'mobile')
        output_path (str): Caminho onde o vídeo com logo será salvo
        duration (float, optional): Duração desejada do vídeo em segundos. 
                                  Se não fornecido, usa 10 segundos
        start_time (float, optional): Tempo inicial do vídeo em segundos. 
                                    Padrão é 0

    Returns:
        str: Caminho do vídeo com logo adicionada em caso de sucesso
        None: Em caso de erro
    """
    try:
        print("\nAdicionando logo com blur ao vídeo...")
        
        # Verifica se o vídeo existe
        if not os.path.exists(video_path):
            print(f"ERRO: Vídeo não encontrado em: {video_path}")
            return None
        

            
        # Caminho do logo
        #logo_path = r"C:\projetos\YDUQS\app\videoPexel\logo\logo-autenticare-02.png"
        logo_path = os.path.join(get_temp_files_pexel_path(), "logo", "logo_yduqs.png")
        #logo_path = r"C:\projetos\YDUQS\app\videoPexel\logo\logo_puc_minas.png"
        
        # Escala do logo baseada no formato do vídeo
        logo_scale = LOGO_SCALE.get(format_type, 1.00)
        
        # Comando ffmpeg - Reorganizado para incluir corte e efeitos em uma única operação
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", logo_path,
            "-filter_complex",
            f"[0:v]split=2[v1][v2];"
            f"[v2]scale=iw:-1,boxblur=10:5[blurred];"
            f"[v1][blurred]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[v3];"
            f"[1:v]scale=iw*{logo_scale}:-1[logo];"
            f"[v3][logo]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[out]",
            "-map", "[out]",
            "-map", "0:a?",  # Mantém o áudio original se existir
            "-c:a", "copy",  # Copia o áudio sem recodificar
            "-t", str(duration) if duration else "10",  # Duração padrão de 10s se não especificada
            output_path
        ]
        
        print("\nComando ffmpeg:")
        print(" ".join(cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Verifica se o arquivo foi gerado e tem tamanho adequado
        if result.returncode != 0:
            print(f"Erro ao adicionar logo com blur: {result.stderr}")
            return None
            
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
            print(f"Erro: Arquivo de saída não foi gerado corretamente")
            print(f"Tamanho do arquivo: {os.path.getsize(output_path) if os.path.exists(output_path) else 0} bytes")
            print("Saída do ffmpeg:", result.stderr)
            return None

        print("Logo com blur adicionado com sucesso!")
        print(f"Tamanho do arquivo: {os.path.getsize(output_path)} bytes")
        return output_path

    except Exception as e:
        print(f"Erro ao adicionar logo com blur: {str(e)}")
        return None

def cut_video(video_path, output_path, duration, start_time=0):
    """
    Corta um vídeo para uma duração específica a partir de um ponto inicial.

    Recebe um vídeo e o corta para a duração desejada, começando do ponto inicial 
    especificado. Se o vídeo original for menor que a duração solicitada, retorna 
    o vídeo original sem modificações.

    Args:
        video_path (str): Caminho do arquivo de vídeo de entrada
        output_path (str): Caminho onde o vídeo cortado será salvo
        duration (float): Duração desejada em segundos
        start_time (float, optional): Tempo inicial do corte em segundos. Padrão é 0.

    Returns:
        str: Caminho do vídeo cortado em caso de sucesso
        None: Em caso de erro ou se o vídeo não for encontrado
    """
    try:
        if not os.path.exists(video_path):
            print(f"ERRO: Vídeo não encontrado em: {video_path}")
            return None
            
        # Obtém a duração atual do vídeo
        current_duration = get_video_duration(video_path)
        if not current_duration:
            print("Erro ao obter duração do vídeo")
            return None
            
        # Se o vídeo for menor que a duração desejada, retorna o vídeo original
        if current_duration <= duration:
            print(f"Vídeo já tem duração menor que {duration}s. Usando vídeo original.")
            return video_path
            
        print(f"\nCortando vídeo para {duration} segundos...")
        print(f"Vídeo original: {video_path}")
        print(f"Duração original: {current_duration:.2f}s")
        print(f"Duração desejada: {duration}s")
        print(f"Início em: {start_time}s")
        
        # Comando ffmpeg para cortar o vídeo - usando recodificação para corte preciso
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:v", "libx264",     # Usa recodificação para corte preciso
            "-preset", "fast",      # Preset rápido para não demorar muito
            "-crf", "23",          # Qualidade razoável
            "-c:a", "aac",         # Recodifica áudio também
            "-avoid_negative_ts", "make_zero",  # Evita timestamps negativos
            output_path
        ]
        
        print("\nExecutando comando de corte:")
        print(" ".join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Erro ao cortar vídeo: {result.stderr}")
            return None
            
        # Verifica se o arquivo foi gerado corretamente
        if not os.path.exists(output_path):
            print("Erro: Arquivo de saída não foi gerado")
            return None
            
        # Verifica a duração do vídeo cortado
        new_duration = get_video_duration(output_path)
        print(f"Duração do vídeo cortado: {new_duration:.2f}s")
        
        if abs(new_duration - duration) > 0.5:  # Permite 0.5 segundo de diferença
            print(f"AVISO: Duração do vídeo cortado ({new_duration:.2f}s) difere da duração desejada ({duration}s)")
            if new_duration < duration/2:  # Se o vídeo ficou muito curto
                print("Erro: Vídeo cortado ficou muito curto")
                return None
        
        print("Vídeo cortado com sucesso!")
        return output_path

    except Exception as e:
        print(f"Erro ao cortar vídeo: {str(e)}")
        if hasattr(e, '__traceback__'):
            import traceback
            print("Traceback completo:")
            traceback.print_tb(e.__traceback__)
        return None

def limit_video_duration(video_path, output_path, max_duration=15):
    """
    Limita a duração de um vídeo ao número máximo de segundos especificado.

    Recebe um vídeo e gera uma versão mais curta mantendo apenas os primeiros X segundos,
    onde X é a duração máxima especificada. Útil para adequar vídeos a limites de duração
    de plataformas.

    Args:
        video_path (str): Caminho do arquivo de vídeo de entrada
        output_path (str): Caminho onde o vídeo cortado será salvo
        max_duration (int, optional): Duração máxima em segundos. Padrão é 15 segundos.

    Returns:
        str: Caminho do vídeo cortado em caso de sucesso
        None: Em caso de erro ou se o vídeo já estiver dentro do limite
    """
    try:
        # Obtém a duração atual do vídeo
        duration = get_video_duration(video_path)
        
        if duration <= max_duration:
            print(f"Vídeo já está dentro do limite de {max_duration} segundos")
            return video_path
            
        print(f"\nLimitando vídeo para {max_duration} segundos...")
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-t", str(max_duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Erro ao limitar duração: {result.stderr}")
            return None

        print("Duração do vídeo limitada com sucesso!")
        return output_path

    except Exception as e:
        print(f"Erro ao limitar duração: {str(e)}")
        return None

def sync_text_with_audio(text, audio_path, video_duration, format_type="desktop"):
    """
    Sincroniza um texto com um arquivo de áudio, gerando timestamps para legendas.

    Recebe um texto e um arquivo de áudio e tenta sincronizar o texto com a fala,
    gerando timestamps precisos para cada parte do texto. Usa reconhecimento de fala
    e alinhamento de texto para determinar quando cada parte deve aparecer.

    Args:
        text (str): O texto a ser sincronizado
        audio_path (str): Caminho do arquivo de áudio
        video_duration (float): Duração total do vídeo em segundos
        format_type (str, optional): Tipo de formato do vídeo ('desktop' ou 'mobile'). 
                                   Padrão é 'desktop'.

    Returns:
        list: Lista de dicionários contendo o texto e seus timestamps no formato:
              [{'text': str, 'start': float, 'end': float}, ...]
        None: Em caso de erro na sincronização
    """
    try:
        print("\nSincronizando texto com áudio...")
        
        # Divide o texto em partes menores
        text_parts = []
        for sentence in text.split('.'):
            parts = split_long_sentence(sentence.strip(), format_type=format_type)
            text_parts.extend(parts)
            
        # Usa Whisper para obter timestamps precisos
        transcription = transcribe_audio(audio_path)
        if not transcription:
            return transcribe_audio(text, video_duration)
            
        # Alinha o texto com a transcrição usando similaridade de texto
        from difflib import SequenceMatcher
        
        def similarity(a, b):
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()
            
        subtitles = []
        for part in text_parts:
            # Encontra o segmento mais similar na transcrição
            best_match = max(transcription, 
                           key=lambda x: similarity(part, x['text']))
            
            subtitles.append({
                'text': part,
                'start': best_match['start'],
                'end': best_match['end']
            })
            
        # Ordena por tempo de início
        subtitles.sort(key=lambda x: x['start'])
        
        return subtitles
        
    except Exception as e:
        print(f"Erro ao sincronizar: {str(e)}")
        return transcribe_audio(text, video_duration) 
    