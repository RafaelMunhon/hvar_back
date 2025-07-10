import random
import subprocess
import os
import time
import requests
import json
from app import settings
from app.config.gemini_client import get_gemini_manager
from app.config.ffmpeg import get_temp_files_path
from app.services.speech_service import extract_audio, extract_audio_from_video, transcribe_with_timestamps, upload_video_to_bucket
from app.videoPexel.narration import generate_voiceover
from app.videoPexel.music import download_background_music, add_background_music
from app.videoPexel.config import (
     VIDEO_FORMATS
)
from app.videoPexel.utils import (
    clean_temp_folder, get_temp_files_pexel_path,
    remove_html_tags, adjust_text_for_duration
)
from app.config.vertexAi import generate_content
from app.videoPexel.search import download_video, generate_search_queries
import re
from app.videoPexel.subtitles import add_logo_and_blur, add_subtitles, cut_video, get_video_duration
from google.cloud import storage
from app.core.logger_config import setup_logger

# Configurar logger
logger = setup_logger(__name__)

def standardize_video(input_path, output_path, format_type):
    """Padroniza o vídeo para o formato desejado"""
    try:
        format_config = VIDEO_FORMATS[format_type]
        target_width = format_config["width"]
        target_height = format_config["height"]
        
        print(f"\nPadronizando vídeo: {input_path}")
        print(f"Formato alvo: {target_width}x{target_height}")

        # Primeiro, verifica o formato do vídeo de entrada
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "json",
            input_path
        ]
        
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        if probe_result.returncode == 0:
            info = json.loads(probe_result.stdout)
            stream = info.get('streams', [{}])[0]
            input_width = int(stream.get('width', 0))
            input_height = int(stream.get('height', 0))
            print(f"Formato original: {input_width}x{input_height}")
        
        # Comando ffmpeg para padronizar o vídeo
        cmd = [
            "ffmpeg",
            "-y",  # Sobrescrever arquivo de saída
            "-i", input_path,  # Arquivo de entrada
            "-vf", (
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
            ),
            "-r", "30",  # Frame rate
            "-c:v", "libx264",  # Codec de vídeo
            "-preset", "medium",  # Preset de compressão
            "-crf", "23",  # Qualidade do vídeo
            "-movflags", "+faststart",  # Otimização para web
            "-pix_fmt", "yuv420p",  # Formato de pixel
            output_path
        ]
        
        print("Executando comando de padronização...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Erro ao padronizar vídeo: {result.stderr}")
            return None
            
        # Verifica se o vídeo de saída está no formato correto
        probe_result = subprocess.run(probe_cmd[:-1] + [output_path], capture_output=True, text=True)
        if probe_result.returncode == 0:
            info = json.loads(probe_result.stdout)
            stream = info.get('streams', [{}])[0]
            output_width = int(stream.get('width', 0))
            output_height = int(stream.get('height', 0))
            print(f"Formato final: {output_width}x{output_height}")
            
            if output_width != target_width or output_height != target_height:
                print(f"AVISO: O vídeo não está no formato alvo exato!")
                return None
        
        print(f"Vídeo padronizado com sucesso: {output_path}")
        return output_path

    except Exception as e:
        print(f"Erro ao padronizar vídeo: {str(e)}")
        if hasattr(e, '__traceback__'):
            import traceback
            print("Traceback completo:")
            traceback.print_tb(e.__traceback__)
        return None

def add_narration_to_video(video_path, narration_path, output_path):
    """Adiciona narração ao vídeo com delay inicial"""
    try:
        print(f"\nAdicionando narração ao vídeo...")
        
        # Cria um arquivo de silêncio com 5 segundos
        silence_path = os.path.join(os.path.dirname(narration_path), "silence.mp3")
        silence_cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "5",  # 5 segundos de silêncio
            silence_path
        ]
        
        result = subprocess.run(silence_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Erro ao criar arquivo de silêncio: {result.stderr}")
            return None
            
        # Concatena o silêncio com a narração
        delayed_narration = os.path.join(os.path.dirname(narration_path), "delayed_narration.mp3")
        concat_cmd = [
            "ffmpeg",
            "-y",
            "-i", "concat:"+silence_path+"|"+narration_path,
            "-acodec", "copy",
            delayed_narration
        ]
        
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Erro ao adicionar delay à narração: {result.stderr}")
            return None

        # Adiciona a narração com delay ao vídeo
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-i", delayed_narration,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Erro ao adicionar narração: {result.stderr}")
            return None

        print("Narração adicionada com sucesso!")
        
        # Limpa arquivos temporários
        if os.path.exists(silence_path):
            os.remove(silence_path)
        if os.path.exists(delayed_narration):
            os.remove(delayed_narration)
            
        return output_path

    except Exception as e:
        print(f"Erro ao adicionar narração: {str(e)}")
        return None

async def process_videos(custom_prompt, voice=None, music_style=None, num_scenes=4, site=None):
    """
    Processa os vídeos com base no prompt fornecido.

    Tenta processar os vídeos com base no prompt fornecido.

    Retorna:
        str: URL do vídeo processado
    """
    try:
        # Limpa a pasta temp
        clean_temp_folder()

        # Verifica o formato do vídeo
        format_type = os.environ.get("VIDEO_FORMAT", "mobile")
        if format_type not in VIDEO_FORMATS:
            raise ValueError(f"Formato de vídeo inválido: {format_type}")

        # Obtém o caminho base para os arquivos temporários
        pasta_temp = get_temp_files_path()

        print(f"\nGerando vídeo com {num_scenes} cenas...")
        print(f"Formato: {format_type}")
        print(f"Resolução alvo: {VIDEO_FORMATS[format_type]['width']}x{VIDEO_FORMATS[format_type]['height']}")

        # Baixa os vídeos
        downloaded_video_ids = set()
        video_files = []
        max_retries = 3
        retry_count = 0
        
        while len(video_files) < num_scenes and retry_count < max_retries:
            if retry_count > 0:
                print(f"\nTentativa {retry_count + 1} de encontrar vídeos suficientes...")
                # Gera novas queries com critérios diferentes
                if retry_count == 1:
                    new_prompt = f"refazer a busca, {custom_prompt}"
                elif retry_count == 2:
                    new_prompt = f"refazer a busca, {custom_prompt}"
                search_queries = await generate_search_queries(new_prompt, num_scenes - len(video_files))
            else:
                search_queries = await generate_search_queries(custom_prompt, num_scenes)
            
            for query in search_queries:
                if len(video_files) >= num_scenes:
                    break
                    
                print(f"\nBaixando vídeo {len(video_files) + 1}/{num_scenes}...")
                video_path = download_video(query, format_type, downloaded_video_ids, max_attempts=3, site=site)
                if video_path:
                    video_files.append(video_path)
            
            retry_count += 1
            
        if len(video_files) < num_scenes:
            print(f"\nAviso: Foram encontrados apenas {len(video_files)} vídeos dos {num_scenes} solicitados")
            if not video_files:
                raise Exception("Nenhum vídeo foi baixado com sucesso")
        
        # Corta os vídeos para duração específica
        print("\nCortando vídeos para duração específica...")
        cut_video_files = []
        for i, video_path in enumerate(video_files):
            output_path = os.path.join(pasta_temp, f"cut_video_{i}.mp4")
            
            # Define a duração baseada na posição do vídeo
            if i == 0:  # Primeira cena
                target_duration = 5  # 5 segundos para introdução
            elif i == len(video_files) - 1:  # Última cena
                target_duration = 5  # 5 segundos para conclusão
            else:  # Cenas do meio
                target_duration = 10  # 10 segundos para cada cena do meio
                
            print(f"\nProcessando vídeo {i+1}/{len(video_files)}")
            cut_result = cut_video(
                video_path=video_path,
                output_path=output_path,
                duration=target_duration
            )
            
            if cut_result:
                cut_video_files.append(cut_result)
                print(f"Vídeo {i+1} cortado com sucesso")
            else:
                print(f"Erro ao cortar vídeo {i+1}")

        if not cut_video_files:
            raise Exception("Falha ao cortar os vídeos")
            
        print(f"\nVídeos cortados com sucesso: {len(cut_video_files)}/{len(video_files)}")

        # Padroniza os vídeos cortados
        print("\nPadronizando vídeos...")
        standardized_videos = []
        for i, video_path in enumerate(cut_video_files):
            output_path = os.path.join(pasta_temp, f"std_video_{i}.mp4")
            standardized = standardize_video(video_path, output_path, format_type)
            if standardized:
                standardized_videos.append(standardized)
            else:
                print(f"Erro ao padronizar vídeo {i}")

        if not standardized_videos:
            raise Exception("Nenhum vídeo foi padronizado com sucesso")

        print(f"\nVídeos padronizados com sucesso: {len(standardized_videos)}/{len(video_files)}")

        # Adiciona logo com blur na primeira e última cena
        print("\nAdicionando logo nas cenas de abertura e encerramento...")
        first_scene = standardized_videos[0]
        last_scene = standardized_videos[-1]
        
        first_scene_with_logo = os.path.join(pasta_temp, "first_scene_with_logo.mp4")
        first_scene_processed = add_logo_and_blur(
            video_path=first_scene,
            format_type=format_type,
            output_path=first_scene_with_logo,
            duration=10
        )
        
        last_scene_with_logo = os.path.join(pasta_temp, "last_scene_with_logo.mp4")
        last_scene_processed = add_logo_and_blur(
            video_path=last_scene,
            format_type=format_type,
            output_path=last_scene_with_logo,
            duration=10
        )
        
        # Atualiza a lista de vídeos com as cenas processadas
        standardized_videos[0] = first_scene_processed
        standardized_videos[-1] = last_scene_processed

        # Concatena os vídeos após processar logos
        print("\nConcatenando vídeos...")
        concatenated_video = os.path.join(pasta_temp, "concatenated.mp4")
        if not concatenate_videos(standardized_videos, concatenated_video):
            raise Exception("Falha ao concatenar vídeos")

        # Obtém a duração do vídeo concatenado
        video_duration = get_video_duration(concatenated_video)
        if not video_duration:
            raise Exception("Não foi possível obter a duração do vídeo")
        print(f"\nDuração total do vídeo: {video_duration:.1f} segundos")

        # Gera o texto narrativo e a narração
        prompt = f"""
        Crie um texto publicitário curto para narração em vídeo sobre:
        "{custom_prompt}"

        Requisitos:
        - Linguagem direta e envolvente
        - Entre 80 e 120 palavras
        - Sem marcações ou formatações
        - Texto em português do Brasil
        - Tom publicitário e persuasivo

        O texto deve seguir esta estrutura:
        1. Abertura impactante (1-2 frases)
        2. Desenvolvimento do tema (2-3 frases)
        3. Conclusão com call-to-action (1 frase)

        Retorne apenas o texto para narração, sem formatações ou marcações.
        """

        manager = get_gemini_manager()
        response = await manager.generate_content(
            prompt,
            model=settings.GEMINI
        )
        if not response or not response:
            raise Exception("Não foi possível gerar o texto narrativo")

        # Limpa o texto
        texto_narrativo = response.strip()
        texto_narrativo = remove_html_tags(texto_narrativo)
        texto_narrativo = re.sub(r'\[.*?\]', '', texto_narrativo)
        texto_narrativo = re.sub(r'\(.*?\)', '', texto_narrativo)
        texto_narrativo = ' '.join(texto_narrativo.split())

        print("\nTexto gerado para narração:")
        print(texto_narrativo)
        
        # Gera narração
        logger.info("Gerando narração...")
        narration_path = None
        max_retries = 10
        retry_count = 0

        while not narration_path and retry_count < max_retries:
            retry_count += 1
            logger.info(f"Tentativa {retry_count} de {max_retries} para gerar narração...")
            narration_path = generate_voiceover(
                text=texto_narrativo,
                voice=voice if voice else 'pt-BR-Standard-A'
            )

        if not narration_path:
            raise Exception("Falha ao gerar narração!")

        # Extrai o áudio da narração para transcrição
        audio_file = os.path.join(pasta_temp, "narration_audio.wav")
        #if not extract_audio_from_video(narration_path, audio_file):
        #    logger.error("Falha ao extrair áudio da narração")
        #    raise Exception("Falha ao extrair áudio da narração!")

        # Transcreve o áudio para obter os timestamps
        print("\nTranscrevendo narração para sincronizar legendas...")
        transcricao_com_tempos = transcribe_with_timestamps(audio_file)
        if transcricao_com_tempos:
            # Formata a transcrição completa
            transcricao = " ".join([item["word"] for item in transcricao_com_tempos])
            logger.info(f"Transcrição completa: {transcricao}")
        else:
            logger.warning("Falha na transcrição. Gerando timestamps manualmente...")
            # Gera timestamps manualmente se a transcrição falhar
            palavras = texto_narrativo.split()
            duracao_total = get_video_duration(narration_path)
            tempo_por_palavra = (duracao_total - 5.0) / len(palavras)  # 5s de delay inicial
            
            transcricao_com_tempos = []
            for i, palavra in enumerate(palavras):
                start_time = 5.0 + (i * tempo_por_palavra)
                end_time = start_time + tempo_por_palavra
                transcricao_com_tempos.append({
                    'word': palavra,
                    'start_time': start_time,
                    'end_time': end_time
                })
            
            transcricao = texto_narrativo
            logger.info(f"Timestamps gerados manualmente para {len(palavras)} palavras")

        # Adiciona narração ao vídeo
        print("\nAdicionando narração ao vídeo...")
        video_with_narration = os.path.join(pasta_temp, "video_with_narration.mp4")
        if not add_narration_to_video(concatenated_video, narration_path, video_with_narration):
            raise Exception("Falha ao adicionar narração ao vídeo!")

        # Adiciona logo e legendas usando a transcrição
        print("\nAdicionando logo e legendas...")
        video_with_subtitles = os.path.join(pasta_temp, "video_with_subtitles.mp4")

        # Debug dos timestamps antes de adicionar legendas
        logger.info("Timestamps para legendas:")
        for ts in transcricao_com_tempos[:5]:  # Mostra as 5 primeiras palavras
            logger.info(f"Palavra: {ts['word']}, Início: {ts['start_time']:.2f}, Fim: {ts['end_time']:.2f}")

        final_result = add_subtitles(
            video_path=video_with_narration,
            transcription=transcricao_com_tempos,
            format_type=format_type,
            output_path=video_with_subtitles,
            start_delay=5.0
        )
        if not final_result:
            raise Exception("Falha ao adicionar logo e legendas ao vídeo!")

        # Baixa música de fundo
        print("\nBaixando música de fundo...")
        background_music = download_background_music(music_style)
        if not background_music:
            raise Exception("Falha ao baixar música de fundo!")

        # Adiciona música de fundo ao vídeo final
        print("\nAdicionando música de fundo...")
        final_video = os.path.join(pasta_temp, "final_video.mp4")
        final_result = add_background_music(
            video_with_subtitles,
            background_music,
            final_video
        )
        if not final_result:
            raise Exception("Falha ao adicionar música de fundo ao vídeo!")

        # Após processar o vídeo, faz upload para o bucket
        timestamp = int(time.time())
        final_video_name = f"final_video_{timestamp}.mp4"
        final_video_path = os.path.join(pasta_temp, final_video_name)
        
        # Move o vídeo final para o novo nome com timestamp
        os.rename(final_video, final_video_path)
        
        # Faz upload para o bucket
        bucket_url = upload_video_to_bucket(final_video_path)
        
        if not bucket_url:
            raise Exception("Falha ao fazer upload do vídeo para o bucket")

        logger.info("Vídeo processado com sucesso!")
        return bucket_url

    except Exception as e:
        logger.error(f"Erro no processamento: {str(e)}")
        logger.exception("Detalhes do erro:")  # Adiciona stack trace completo
        return None

def concatenate_videos(video_list, output_path):
    """Concatena uma lista de vídeos em um único arquivo"""
    try:
        if not video_list:
            print("Lista de vídeos vazia")
            return None
            
        pasta_temp = get_temp_files_path()
        file_list_path = os.path.join(pasta_temp, "file_list.txt")
        
        print("\nPreparando para concatenar vídeos:")
        print(f"Número de vídeos: {len(video_list)}")
        
        # Verifica se todos os vídeos existem
        for video in video_list:
            if not os.path.exists(video):
                print(f"ERRO: Vídeo não encontrado: {video}")
                return None
            print(f"Vídeo encontrado: {video}")
        
        # Cria o arquivo de lista com caminhos absolutos
        with open(file_list_path, "w", encoding='utf-8') as f:
            for video in video_list:
                abs_path = os.path.abspath(video)
                f.write(f"file '{abs_path}'\n")
        
        print(f"\nArquivo de lista criado em: {file_list_path}")
        
        # Comando ffmpeg para concatenação
        cmd = [
            "ffmpeg",
            "-y",  # Sobrescreve arquivo de saída
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c:v", "libx264",  # Recodifica vídeo para garantir compatibilidade
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",  # Recodifica áudio para garantir compatibilidade
            output_path
        ]
        
        print("\nExecutando comando de concatenação:")
        print(" ".join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Erro ao concatenar vídeos: {result.stderr}")
            return None
            
        if not os.path.exists(output_path):
            print("Erro: Arquivo de saída não foi gerado")
            return None
            
        print(f"Vídeos concatenados com sucesso: {output_path}")
        return output_path

    except Exception as e:
        print(f"Erro na concatenação: {str(e)}")
        return None

def get_audio_duration(audio_path):
    """Obtém a duração de um arquivo de áudio em segundos"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return float(info['format']['duration'])
        return 0
    except:
        return 0

def adjust_narration_text(current_duration, video_duration, prompt):
    """Ajusta o prompt para gerar um texto com duração adequada"""
    target_duration = video_duration - 10  # Alvo: 10 segundos menor que o vídeo total
    
    # Se a narração estiver muito diferente do alvo (mais que 3 segundos), ajusta
    duration_diff = abs(current_duration - target_duration)
    if duration_diff > 3:
        print(f"\nDuração atual da narração: {current_duration:.1f}s")
        print(f"Duração do vídeo: {video_duration:.1f}s")
        print(f"Duração alvo da narração: {target_duration:.1f}s")
        print("Ajustando texto para atingir duração alvo...")
        
        # Estima número de palavras necessário (média de 2.5 palavras por segundo)
        target_words = int(target_duration * 2.5)
        
        adjusted_prompt = f"""
        Crie um texto publicitário para narração em vídeo sobre:
        "{prompt}"

        Requisitos IMPORTANTES:
        - O texto DEVE ter duração de {target_duration:.1f} segundos quando narrado
        - Use aproximadamente {target_words} palavras
        - Linguagem direta e envolvente
        - Tom publicitário e persuasivo
        - Texto em português do Brasil
        - Sem marcações ou formatações

        Estrutura:
        1. Abertura impactante (2-3 frases)
        2. Desenvolvimento do tema (3-4 frases)
        3. Conclusão com call-to-action (1-2 frases)

        Retorne apenas o texto para narração.
        """
        return adjusted_prompt
    
    return None  # Duração está adequada