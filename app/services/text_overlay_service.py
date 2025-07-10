import random
import ffmpeg
import logging
import shutil
import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import uuid
from app.bd.bd import inserir_video
from app.config.ffmpeg import get_root_path
from app.services.speech_service import upload_video_to_bucket
from app.core.logger_config import setup_logger

# Configuração básica do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = setup_logger(__name__)

# Variável global para armazenar os últimos tempos usados
_ultimo_tempo_fim = 0
_ultimo_tempo_fim_imagem = 0  # Nova variável para imagens
_ultimo_tempo_fim_codigo = 0.0

def get_temp_files_path():
    """
    Retorna o caminho para o diretório de arquivos temporários.
    """
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "arquivosTemporarios")

def get_videos_finalized_path():
    """
    Retorna o caminho para o diretório de vídeos finalizados.
    """
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "videosFinalizados")

temp_path = get_temp_files_path()
final_path = get_videos_finalized_path()

def encontrar_tempo_frase(transcricao_com_tempos, frase, threshold=0.5, eh_imagem=False):
    """
    Encontra o tempo de início e fim da primeira ocorrência de uma frase na transcrição
    com correspondência mais precisa - versão otimizada para evitar sobreposições
    """
    global _ultimo_tempo_fim, _ultimo_tempo_fim_imagem
    
    logger.info(f"\n=== Procurando tempo para frase: '{frase}' ===")
    
    # Verifica se a transcrição está vazia
    if not transcricao_com_tempos:
        logger.warning("Transcrição vazia recebida!")
        # Retorna valores padrão
        tempo_inicio = 2.0 if not eh_imagem else 5.0
        tempo_fim = tempo_inicio + (2.0 if not eh_imagem else 3.0)
        return tempo_inicio, tempo_fim
    
    # Obtém o último tempo usado (texto ou imagem)
    ultimo_tempo = _ultimo_tempo_fim_imagem if eh_imagem else _ultimo_tempo_fim
    
    # Define a margem mínima entre textos (2 segundos)
    margem_minima = 1.0
    
    # Converte a frase para minúsculas e divide em palavras-chave
    frase = frase.lower()
    palavras_chave = [palavra for palavra in frase.split() if len(palavra) > 2]
    logger.info(f"Palavras-chave: {palavras_chave}")
    
    # Se não houver palavras-chave significativas, use a frase completa
    if not palavras_chave:
        palavras_chave = frase.split()
    
    # Cria uma string da transcrição completa para busca
    texto_transcricao = " ".join([item["word"].lower() for item in transcricao_com_tempos])
    logger.info(f"Texto da transcrição: {texto_transcricao[:100]}...")
    
    # Tenta encontrar correspondência exata primeiro
    indice_correspondencia = texto_transcricao.find(frase)
    
    if indice_correspondencia >= 0:
        logger.info(f"Correspondência exata encontrada na posição {indice_correspondencia}")
        
        # Encontra a palavra na transcrição que corresponde ao início da frase
        palavras_antes = texto_transcricao[:indice_correspondencia].split()
        indice_palavra_inicio = len(palavras_antes)
        
        # Encontra a palavra na transcrição que corresponde ao fim da frase
        palavras_frase = frase.split()
        indice_palavra_fim = indice_palavra_inicio + len(palavras_frase) - 1
        
        # Obtém os tempos de início e fim
        if indice_palavra_inicio < len(transcricao_com_tempos):
            tempo_inicio = transcricao_com_tempos[indice_palavra_inicio]["start_time"]
        else:
            tempo_inicio = transcricao_com_tempos[-1]["end_time"] - 1.0
            
        if indice_palavra_fim < len(transcricao_com_tempos):
            tempo_fim = transcricao_com_tempos[indice_palavra_fim]["end_time"]
        else:
            tempo_fim = tempo_inicio + 1.0
            
        # Garante uma duração mínima de 1 segundo
        if tempo_fim - tempo_inicio < 1.0:
            tempo_fim = tempo_inicio + 1.0
            
        logger.info(f"Tempo encontrado (correspondência exata): {tempo_inicio:.2f} - {tempo_fim:.2f}")
        
        # Se o tempo encontrado começa menos de 2 segundos após o último tempo usado, descartamos esta palavra
        if tempo_inicio < ultimo_tempo + margem_minima:
            logger.info(f"Sobreposição detectada com tempo anterior ({ultimo_tempo:.2f}). Descartando esta palavra-chave.")
            return None, None
        
        # Atualiza o último tempo usado
        if eh_imagem:
            _ultimo_tempo_fim_imagem = tempo_fim + 1.0  # Adiciona 1 segundo de margem
        else:
            _ultimo_tempo_fim = tempo_fim + 0.5  # Adiciona 0.5 segundos de margem
            
        logger.info(f"Palavra: '{frase}' | Tempo: {tempo_inicio} - {tempo_fim}")
        logger.info(f"Último tempo atualizado para: {_ultimo_tempo_fim if not eh_imagem else _ultimo_tempo_fim_imagem}")
        return tempo_inicio, tempo_fim
    
    # Se não encontrou correspondência exata, não usamos palavras-chave individuais para textos
    # Apenas para imagens permitimos usar palavras-chave individuais
    if not eh_imagem:
        logger.warning(f"Correspondência exata não encontrada para o texto: '{frase}'. Ignorando este texto.")
        logger.info(f"Ignorando palavra devido à falta de correspondência exata: '{frase}'")
        return None, None
    
    # Para imagens, continuamos tentando encontrar por palavras-chave
    logger.info("Correspondência exata não encontrada, tentando por palavras-chave (apenas para imagens)...")
    
    # Procura por cada palavra-chave na transcrição
    for palavra in palavras_chave:
        indice_palavra = texto_transcricao.find(palavra)
        if indice_palavra >= 0:
            # Conta quantas palavras existem antes da correspondência
            palavras_antes = texto_transcricao[:indice_palavra].split()
            indice_palavra_transcricao = len(palavras_antes)
            
            # Verifica se o índice está dentro dos limites da transcrição
            if indice_palavra_transcricao < len(transcricao_com_tempos):
                tempo_inicio = transcricao_com_tempos[indice_palavra_transcricao]["start_time"]
                tempo_fim = transcricao_com_tempos[indice_palavra_transcricao]["end_time"]
                
                # Garante uma duração mínima de 1 segundo
                if tempo_fim - tempo_inicio < 1.0:
                    tempo_fim = tempo_inicio + 1.0
                
                logger.info(f"Palavra-chave '{palavra}' encontrada na posição {indice_palavra}")
                logger.info(f"Tempo encontrado (palavra-chave): {tempo_inicio:.2f} - {tempo_fim:.2f}")
                
                # Se o tempo encontrado começa menos de 2 segundos após o último tempo usado, tenta a próxima palavra-chave
                if tempo_inicio < ultimo_tempo + margem_minima:
                    logger.info(f"Sobreposição detectada com tempo anterior ({ultimo_tempo:.2f}). Tentando próxima palavra-chave.")
                    continue
                
                # Atualiza o último tempo usado
                if eh_imagem:
                    _ultimo_tempo_fim_imagem = tempo_fim + 1.0
                else:
                    _ultimo_tempo_fim = tempo_fim + 0.2
                
                logger.info(f"Palavra: '{frase}' | Tempo: {tempo_inicio} - {tempo_fim}")
                logger.info(f"Último tempo atualizado para: {_ultimo_tempo_fim if not eh_imagem else _ultimo_tempo_fim_imagem}")
                return tempo_inicio, tempo_fim
    
    # Se chegou aqui, não encontrou nenhuma correspondência para imagens
    logger.warning(f"Nenhuma correspondência encontrada para a imagem com momento-chave: '{frase}'")
    return None, None

def gerar_drawtext_info(palavras_encontradas, transcricao_com_tempos):
    """
    Gera informações para o filtro drawtext do FFmpeg.
    Modificado para evitar duplicação de texto, mantendo apenas as imagens de fundo.
    """
    drawtext_info = []
    
    for palavra in palavras_encontradas:
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, palavra)
        
        # Se os tempos são None, significa que a palavra deve ser ignorada devido a sobreposição
        if tempo_inicio is None or tempo_fim is None:
            logger.info(f"Ignorando palavra devido a sobreposição: '{palavra}'")
            continue
        
        logger.info(f"Palavra: '{palavra}' | Tempo: {tempo_inicio} - {tempo_fim}")
        
        # Gera um ID único para o arquivo de fundo
        bg_id = uuid.uuid4().hex[:8]
        bg_path = os.path.join(temp_path, f"bg_{bg_id}.png")
        
        # Cria uma imagem de fundo para o texto
        criar_background_arredondado(bg_path, palavra)
        logger.info(f"Background criado: {bg_path} para texto: '{palavra}'")
        
        # Configuração do texto (mantemos apenas para referência na estrutura)
        fonte_size = 36
        fonte_style = os.path.join(get_root_path(), "fonte", "Poppins-Bold.ttf")
        posicao_y = '(h*0.75)'  # Posição Y fixa para todos os textos
        
        # Adiciona informações para o filtro drawtext
        text_info = {
            'text': palavra,
            'x': '(w-text_w)/2',  # Centraliza o texto horizontalmente
            'y': posicao_y,
            'fontsize': fonte_size,
            'fontcolor': 'white',
            'fontfile': fonte_style,
            'background_image': bg_path,
            'background_y': posicao_y,
            'enable': f'between(t,{tempo_inicio-0.5},{tempo_fim+0.5})'
        }
        
        drawtext_info.append(text_info)
    
    return drawtext_info

def gerar_overlay_info(frases_chave, transcricao_com_tempos):
    """
    Gera informações de overlay para as frases-chave.
    
    Args:
        frases_chave (list): Lista de frases-chave
        transcricao_com_tempos (list): Transcrição com tempos
        
    Returns:
        list: Lista de informações de overlay
    """
    logger.info("Gerando informações de texto...")
    
    # Reseta os tempos globais
    global _ultimo_tempo_fim
    _ultimo_tempo_fim = 0
    
    overlay_info = []
    
    # Filtra frases vazias ou None
    frases_filtradas = [frase for frase in frases_chave if frase and isinstance(frase, str)]
    
    # Processa cada frase-chave
    for frase in frases_filtradas:
        # Encontra o tempo da frase
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, frase)
        
        # Se não encontrou tempo válido (retornou None, None) ou se o tempo de início é None, pula esta frase
        if tempo_inicio is None or tempo_fim is None:
            logger.warning(f"Tempo não encontrado para a frase: '{frase}'. Pulando.")
            continue
        
        # Verifica se há sobreposição com overlays existentes
        sobreposicao = False
        for info in overlay_info:
            # Se o início do novo overlay está dentro do intervalo de um overlay existente
            if (info['tempo_inicio'] <= tempo_inicio <= info['tempo_fim']) or \
               (info['tempo_inicio'] <= tempo_fim <= info['tempo_fim']) or \
               (tempo_inicio <= info['tempo_inicio'] and tempo_fim >= info['tempo_fim']):
                sobreposicao = True
                logger.warning(f"Sobreposição detectada para a frase: '{frase}'. Pulando.")
                break
        
        if sobreposicao:
            continue
        
        # Gera um ID único para o background
        bg_id = uuid.uuid4().hex[:8]
        bg_path = os.path.join(temp_path, f"bg_{bg_id}.png")
        
        # Cria o background arredondado
        criar_background_arredondado(bg_path, frase)
        
        logger.info(f"Background criado: {bg_path} para texto: '{frase}'")
        
        # Adiciona à lista de overlay_info
        overlay_info.append({
            'tipo': 'texto',
            'texto': frase,
            'tempo_inicio': tempo_inicio,
            'tempo_fim': tempo_fim,
            'bg_path': bg_path
        })
    
    logger.info(f"Informações de texto geradas: {overlay_info}")
    return overlay_info

def gerar_overlay_info_imagens(imagem_path, transcricao_com_tempos):
    """
    Gera a lista de dicionários overlay_info com base nas informações das imagens e na transcrição.
    """
    logger.info(f"gerar_overlay_info:  {imagem_path}")
    overlay_info = []    

    # Processa as imagens com espaçamento adequado
    for img_info in imagem_path:
        path_name = os.path.join(temp_path, img_info.get('nomeArquivo'))
        # Verifica se a imagem existe
        if not os.path.exists(path_name):
            logger.warning(f"Imagem não encontrada: {path_name}")
            continue

        # Obtém o momento-chave para a imagem
        momento_chave = img_info.get('momentoChave')
        if not momento_chave:
            logger.warning(f"Momento-chave não definido para imagem: {path_name}")
            continue

        # Encontra o tempo para o momento-chave
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, momento_chave, eh_imagem=True)
        
        if tempo_inicio is None or tempo_fim is None:
            logger.warning(f"Não foi possível encontrar tempo para o momento-chave: {momento_chave}")
            continue
        
        # Aumenta a duração da imagem em 3 segundos
        tempo_fim += 3.0
        
        logger.info(f"Momento-chave: '{momento_chave}' | Tempo: {tempo_inicio:.1f} - {tempo_fim:.1f}")

        # Adiciona informações do overlay
        overlay_info.append({
            'img_path': path_name,
            'start': tempo_inicio,
            'end': tempo_fim,
            'momento_chave': momento_chave
        })

    logger.info(f"Total de {len(overlay_info)} imagens processadas")
    return overlay_info

def encontrar_tempo_frase_codigo(transcricao_com_tempos, momento_chave, fim_momento_chave):
    """
    Encontra o tempo de início e fim para um trecho de código baseado nas frases de marcação.
    """
    global _ultimo_tempo_fim_codigo
    
    logger.info(f"\n=== Procurando tempo para código: Início='{momento_chave}', Fim='{fim_momento_chave}' ===")
    
    def limpar_texto(texto):
        """Remove pontuação e normaliza espaços"""
        texto = ''.join(c.lower() for c in texto if c.isalnum() or c.isspace())
        return ' '.join(texto.split())
    
    # Limpa as frases de busca
    momento_chave = limpar_texto(momento_chave)
    fim_momento_chave = limpar_texto(fim_momento_chave)
    
    logger.info(f"Buscando início: '{momento_chave}'")
    logger.info(f"Buscando fim: '{fim_momento_chave}'")
    
    # Constantes
    MAX_SNIPPET_DURATION = 20  # Duração máxima de um snippet em segundos
    MIN_GAP_BETWEEN_SNIPPETS = 2  # Intervalo mínimo entre snippets
    
    # Encontrar tempo de início
    tempo_inicio = None
    palavras_inicio = [p for p in momento_chave.split() if len(p) > 2]
    
    # Se temos um tempo fim anterior, começar a busca depois dele
    start_search_from = _ultimo_tempo_fim_codigo + MIN_GAP_BETWEEN_SNIPPETS if _ultimo_tempo_fim_codigo else 0
    
    # Procura pela sequência de palavras importantes
    for i in range(len(transcricao_com_tempos)):
        current_time = float(transcricao_com_tempos[i]['start_time'])
        
        # Pular se estiver antes do tempo de início da busca
        if current_time < start_search_from:
            continue
            
        palavras_encontradas = 0
        palavras_sequencia = []
        
        # Olha para uma janela de palavras
        for j in range(i, min(i + 10, len(transcricao_com_tempos))):
            palavra_atual = limpar_texto(transcricao_com_tempos[j]['word'])
            palavras_sequencia.append(palavra_atual)
            
            if palavra_atual in palavras_inicio:
                palavras_encontradas += 1
            
            # Se encontrou pelo menos 60% das palavras importantes
            if palavras_encontradas >= len(palavras_inicio) * 0.6:
                tempo_inicio = float(transcricao_com_tempos[i]['start_time'])
                logger.info(f"Sequência de início encontrada: '{' '.join(palavras_sequencia)}' em t={tempo_inicio}")
                break
        if tempo_inicio:
            break
    
    # Encontrar tempo de fim
    tempo_fim = None
    if tempo_inicio:
        palavras_fim = [p for p in fim_momento_chave.split() if len(p) > 2]
        
        # Procurar fim dentro do intervalo máximo
        max_end_time = tempo_inicio + MAX_SNIPPET_DURATION
        
        for i in range(len(transcricao_com_tempos)):
            current_time = float(transcricao_com_tempos[i]['start_time'])
            
            # Pular se estiver antes do início ou depois do tempo máximo
            if current_time <= tempo_inicio or current_time > max_end_time:
                continue
            
            palavras_encontradas = 0
            palavras_sequencia = []
            
            # Olha para uma janela de palavras
            for j in range(i, min(i + 5, len(transcricao_com_tempos))):
                palavra_atual = limpar_texto(transcricao_com_tempos[j]['word'])
                palavras_sequencia.append(palavra_atual)
                
                if palavra_atual in palavras_fim:
                    palavras_encontradas += 1
                
                # Se encontrou pelo menos 60% das palavras importantes
                if palavras_encontradas >= len(palavras_fim) * 0.6:
                    tempo_fim = float(transcricao_com_tempos[j]['end_time'])
                    logger.info(f"Sequência de fim encontrada: '{' '.join(palavras_sequencia)}' em t={tempo_fim}")
                    break
            if tempo_fim:
                break
        
        # Se não encontrou fim dentro do intervalo máximo, usar tempo_inicio + MAX_SNIPPET_DURATION
        if not tempo_fim:
            tempo_fim = tempo_inicio + MAX_SNIPPET_DURATION
            logger.warning(f"Fim não encontrado, usando duração máxima. Fim definido como: {tempo_fim}")
    
    if tempo_inicio and tempo_fim:
        # Atualizar último tempo fim para evitar sobreposições
        _ultimo_tempo_fim_codigo = tempo_fim
        logger.info(f"Tempos encontrados: {tempo_inicio:.2f} - {tempo_fim:.2f}")
        return tempo_inicio, tempo_fim
    
    logger.warning(f"Não foi possível encontrar tempos para o código. Início: '{momento_chave}', Fim: '{fim_momento_chave}'")
    return None, None

def gerar_overlay_info_codigo(lista_imagens_codigo, transcricao_com_tempos):
    """
    Gera informações de overlay para imagens de código.
    """
    overlay_info = []
    
    for img_info in lista_imagens_codigo:
        if not os.path.exists(img_info['caminho']):
            logger.warning(f"Imagem de código não encontrada: {img_info['caminho']}")
            continue

        tempo_inicio, tempo_fim = encontrar_tempo_frase_codigo(
            transcricao_com_tempos,
            img_info['momentoChave'],
            img_info['fimMomentoChave']
        )
        
        if tempo_inicio is not None and tempo_fim is not None:
            overlay_info.append({
                'img_path': img_info['caminho'],
                'start': tempo_inicio,
                'end': tempo_fim,
                'momento_chave': 'code_snippet',
                'fontsize': 24,  # Fonte menor para código
                'x': '(W-w)/2',  # Centralizar horizontalmente
                'y': '(H-h)/2'   # Centralizar verticalmente
            })
        
    return overlay_info

def converter_para_png(caminho_imagem):
    """Converte uma imagem para PNG se necessário"""
    try:
        # Verifica se já é PNG
        if caminho_imagem.lower().endswith('.png'):
            return caminho_imagem
            
        # Abre e converte a imagem
        with Image.open(caminho_imagem) as img:
            # Cria novo caminho para PNG
            novo_caminho = os.path.splitext(caminho_imagem)[0] + '.png'
            # Converte para RGB se necessário (remove canal alpha)
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                background.save(novo_caminho, 'PNG')
            else:
                img.convert('RGB').save(novo_caminho, 'PNG')
            
            logger.info(f"Imagem convertida para PNG: {novo_caminho}")
            return novo_caminho
    except Exception as e:
        logger.error(f"Erro ao converter imagem {caminho_imagem}: {str(e)}")
        return None

def verificar_e_preparar_imagem(caminho):
    """Verifica e prepara uma imagem para uso no ffmpeg"""
    try:
        # Tenta abrir a imagem para validar
        with Image.open(caminho) as img:
            # Verifica se é uma imagem válida
            img.verify()
            
        # Se passou na verificação, converte para PNG
        caminho_png = converter_para_png(caminho)
        if caminho_png:
            return caminho_png
            
        return None
    except Exception as e:
        logger.error(f"Imagem inválida {caminho}: {str(e)}")
        return None

def gerar_comando_ffmpeg(video_path, output_path, overlay_info_imagens, overlay_info_codigo, overlay_info_texto):
    try:
        # Input base do vídeo
        stream = ffmpeg.input(video_path)
        
        # Processar overlays de imagens
        video_stream = stream
        for i, info in enumerate(overlay_info_imagens):
            split_label = f'img{i}'
            
            # Verificar e preparar imagem
            img_path = verificar_e_preparar_imagem(info['img_path'])
            if not img_path:
                logger.warning(f"Pulando imagem inválida: {info['img_path']}")
                continue
            
            # Forçar interpretação como imagem
            img = (ffmpeg
                .input(img_path, f='image2')
                .filter('scale', 
                    'if(gt(iw/ih,1920/1080),1920,trunc(1080*iw/ih/2)*2)', 
                    'if(gt(iw/ih,1920/1080),trunc(1920*ih/iw/2)*2,1080)'
                )
                .filter('pad', 1920, 1080, '(ow-iw)/2', '(oh-ih)/2')
                .split()[split_label])
            
            video_stream = video_stream.overlay(
                img,
                enable=f"between(t,{info['start']},{info['end']})",
                x=0, 
                y=0
            )

        # Processar overlays de código
        for i, info in enumerate(overlay_info_codigo):
            split_label = f'code{i}'
            
            # Verificar e preparar imagem
            img_path = verificar_e_preparar_imagem(info['img_path'])
            if not img_path:
                logger.warning(f"Pulando código inválido: {info['img_path']}")
                continue
            
            code_img = (ffmpeg
                .input(img_path, f='image2')
                .filter('scale', w='iw', h='ih')  # Mantém tamanho original
                .filter('scale', w='min(iw,1920)', h='min(ih,1080)')  # Limita ao tamanho do vídeo
                .filter('pad', w=1920, h=1080, x='(ow-iw)/2', y='(oh-ih)/2')  # Centraliza
            )
            
            video_stream = video_stream.overlay(
                code_img,
                x='(main_w-overlay_w)/2',
                y='(main_h-overlay_h)/2',
                enable=f"between(t,{info['start']},{info['end']})",
                eof_action='repeat'
            )

        # Processar overlays de texto
        for i, info in enumerate(overlay_info_texto):
            split_label = f'txt{i}'
            
            try:
                enable_expr = info['enable']
                times = enable_expr.split('between(t,')[1].split(')')[0]
                start_time, end_time = times.split(',')
                
                # Verificar e preparar imagem de fundo
                bg_path = verificar_e_preparar_imagem(info['background_image'])
                if not bg_path:
                    logger.warning(f"Pulando background inválido: {info['background_image']}")
                    continue
                
                bg = (ffmpeg
                    .input(bg_path, f='image2')
                    .split()[split_label])
                
                # Posicionar background na parte inferior
                video_stream = video_stream.overlay(
                    bg,
                    enable=f"between(t,{start_time},{end_time})",
                    x='(W-w)/2',
                    y='H-150'  # 150 pixels da borda inferior
                )
                
                # Posicionar texto alinhado com o background
                video_stream = video_stream.drawtext(
                    enable=info['enable'],
                    fontcolor=info['fontcolor'],
                    fontfile=info['fontfile'],
                    fontsize=info['fontsize'],
                    text=info['text'],
                    x='(w-text_w)/2',
                    y='H-140'  # 130 pixels da borda inferior
                )
            except Exception as e:
                logger.error(f"Erro ao processar overlay de texto {i}: {str(e)}")
                logger.error(f"Enable expression: {info.get('enable', 'N/A')}")
                continue

        # Configurar saída com mapeamento explícito de streams
        stream = ffmpeg.output(
            video_stream,        # Stream de vídeo processado
            stream.audio,        # Stream de áudio original
            output_path,
            acodec='copy',      # Copiar áudio sem recodificar
            vcodec='libx264',   # Codec de vídeo
            map_metadata=0      # Preservar metadados
        )

        return stream

    except Exception as e:
        logger.error(f"Erro ao gerar comando FFmpeg: {str(e)}")
        raise

def criar_video(video_path, palavras_encontradas, imagem_path, transcricao_com_tempos, duracao_video, id_video, theme, titulo_nc, lista_imagens_codigo):
    """
    Cria um vídeo com sobreposições de texto e imagem, incluindo efeitos de zoom e nitidez.

    Args:
        video_path (str): Caminho do arquivo de vídeo de entrada.
        palavras_encontradas (list): Lista de palavras a serem destacadas no vídeo.
        imagem_path (list): Lista de dicionários com informações das imagens a serem sobrepostas.
            Cada dicionário deve conter:
            - nomeArquivo (str): Nome do arquivo de imagem
            - urlImg (str): URL para download da imagem (opcional)
            - momentoChave (str): Texto para sincronizar a imagem com a transcrição
        transcricao_com_tempos (list): Lista de dicionários com a transcrição e tempos.
            Cada dicionário deve conter:
            - word (str): Palavra transcrita
            - start_time (float): Tempo de início em segundos
            - end_time (float): Tempo de fim em segundos
        duracao_video (float): Duração total do vídeo em segundos.
        id_video (str): Identificador único do vídeo.
        theme (str): Tema visual a ser aplicado.
        titulo_nc (str): Título do conteúdo.

    Returns:
        None

    Raises:
        ffmpeg.Error: Se houver erro durante o processamento do vídeo
        Exception: Para outros erros durante o processamento

    """
    logger.info(f"Iniciando criação do vídeo: {video_path}")
    logger.info(f"Transcricao com tempos: {transcricao_com_tempos}")

    
    try:
        # Entrada de vídeo e áudio
        in_file = ffmpeg.input(video_path)
        logger.info("Entrada de vídeo carregada com sucesso.")

        # Geração de informações de texto e imagem
        logger.info("Gerando informações de texto...")
        drawtext_info = gerar_drawtext_info(palavras_encontradas, transcricao_com_tempos)
        logger.info(f"Informações de texto geradas: {drawtext_info}")

        logger.info("Gerando informações de imagem...")
        overlay_info = gerar_overlay_info_imagens(imagem_path, transcricao_com_tempos)
        logger.info(f"Informações de imagem geradas: {overlay_info}")

        logger.info("Gerando informações de imagem com codigo...")
        overlay_info_codigo = gerar_overlay_info_codigo(lista_imagens_codigo, transcricao_com_tempos)
        logger.info(f"Informações de imagem com codigo geradas: {overlay_info_codigo}")

        # Geração de momentos aleatórios de zoom
        logger.info("Gerando momentos de zoom aleatórios...")
        momentos_zoom = gerar_momentos_zoom(duracao_video)
        logger.info(f"Momentos de zoom definidos: {momentos_zoom}")

        # Aplicação do filtro de zoom no vídeo
        current_stream = in_file['v']  # Usar apenas o stream de vídeo
        for inicio, fim in momentos_zoom:
            current_stream = current_stream.filter(
                'zoompan',
                z=f"if(between(in_time,{inicio},{fim}),min(max(zoom,pzoom)+0.02,1.2),1)",  # 0.08 Velocidade, 1.5 Profundidade do zoom
                x='iw/2-(iw/zoom/2)',
                y='ih/4-(ih/zoom/2)',
                d=1
            )
            logger.info(f"Zoom aplicado no intervalo: {inicio}s - {fim}s")

        # Aplicar filtro de nitidez
        try:
            current_stream = current_stream.filter('unsharp', 3, 3, 0.5, 3, 3, 0.2)
            logger.info("Filtro unsharp aplicado com sucesso.")
        except ffmpeg.Error as e:
            logger.error(f"Erro ao aplicar filtro unsharp: {e.stderr.decode()}")

        # Ajustar os timestamps do áudio para sincronizar com o vídeo
        audio_stream = in_file['a'].filter('asetpts', 'PTS-STARTPTS')
        logger.info("Timestamps do áudio ajustados.")

        # Aplicação dos textos sobrepostos
        logger.info("Aplicando textos ao vídeo...")
        current_stream = in_file
        for info in drawtext_info:
            # Primeiro aplica o background
            if 'background_image' in info:
                bg = ffmpeg.input(info['background_image'])
                
                # Verifica se a palavra tem acento
                palavra = info['text']
                tem_acento = any(c in 'áéíóúâêîôûãõàèìòùäëïöüÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÄËÏÖÜ' for c in palavra)
                
                # Ajusta a posição Y do background baseado na presença de acento
                bg_y = '(H*0.75-1)' if tem_acento else '(H*0.75-1)'  # Aumentado 5px (de -11 para -6 e de -16 para -11)
                
                #logger.info(f"\nAplicando background para: {palavra}")
                #logger.info(f"- Tem acento: {tem_acento}")
                #logger.info(f"- Posição Y: {bg_y}")
                
                current_stream = current_stream.overlay(
                    bg,
                    x='(W-w)/2',
                    y=bg_y,
                    enable=info['enable']
                )
            
            #logger.info(f"\nAplicando texto: {info['text']}")
            #logger.info(f"- Fonte: {info['fontfile']}")
            #logger.info(f"- Tamanho: {info['fontsize']}")
            #logger.info(f"- Posição Y do texto: (h*0.75)")
            #logger.info(f"- Enable: {info['enable']}")
            
            current_stream = current_stream.drawtext(
                text=info['text'],
                fontfile=info['fontfile'],
                fontsize=info['fontsize'],
                fontcolor=info['fontcolor'],
                x='(w-tw)/2',
                y='(h*0.75)',   # Mantém a posição original
                enable=info['enable']
            )
        logger.info("Textos aplicados com sucesso.")

        # Aplicação das imagens sobrepostas
        logger.info("=== INÍCIO DO PROCESSAMENTO DE IMAGENS ===")
        logger.info(f"Imagens a processar: {[img['img_path'] for img in overlay_info]}")

        for i, img_info in enumerate(overlay_info):
            img_path = img_info['img_path']
            logger.info(f"\nProcessando imagem {i+1}/{len(overlay_info)}: {img_path}")
            
            if os.path.exists(img_path):
                # Cria um stream de overlay para cada imagem com um identificador único
                overlay_stream = (
                    ffmpeg.input(img_path)
                    .filter('scale', 
                        'if(gt(iw/ih,1920/1080),1920,trunc(1080*iw/ih/2)*2)', 
                        'if(gt(iw/ih,1920/1080),trunc(1920*ih/iw/2)*2,1080)'
                    )
                    .filter('pad', 1920, 1080, '(ow-iw)/2', '(oh-ih)/2')
                )
                
                logger.info(f"Aplicando overlay para imagem {i+1} no intervalo {img_info['start']:.1f}-{img_info['end']:.1f}")
                
                # Aplica o overlay e atualiza o stream atual
                current_stream = current_stream.overlay(
                    overlay_stream,
                    x='(main_w-overlay_w)/2',
                    y='(main_h-overlay_h)/2',
                    enable=f"between(t,{img_info['start']:.1f},{img_info['end']:.1f})"
                )
                
                logger.info(f"Overlay da imagem {i+1} aplicado com sucesso")
            else:
                logger.error(f"Arquivo de imagem não encontrado: {img_path}")

        logger.info("=== FIM DO PROCESSAMENTO DE IMAGENS ===")

        # Aplicar overlays das imagens de código
        logger.info("Aplicando overlays de código...")
        for info in overlay_info_codigo:
            overlay_stream = (
                ffmpeg.input(info['img_path'])
                .filter('scale', w=1920, h=1080)  # Força o tamanho exato do vídeo
            )
            
            current_stream = current_stream.overlay(
                overlay_stream,
                x='(main_w-overlay_w)/2',  # Centraliza horizontalmente
                y='(main_h-overlay_h)/2',  # Centraliza verticalmente
                enable=f"between(t,{info['start']},{info['end']})",
                eof_action='repeat'
            )

        # Configuração de saída
        output_path = os.path.join(final_path, f"video_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        logger.info(f"Configurando saída para: {output_path}")

        out = gerar_comando_ffmpeg(video_path, output_path, overlay_info, overlay_info_codigo, drawtext_info)

        # Compilação do comando FFmpeg para debug
        comando_ffmpeg = ffmpeg.compile(out, overwrite_output=True)
        logger.info(f"Comando FFmpeg compilado: {' '.join(comando_ffmpeg)}")

        # Execução do comando FFmpeg
        logger.info("Executando comando FFmpeg...")
        ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        logger.info(f"Vídeo finalizado com sucesso: {output_path}")

        # mandar o video para o bucket
        video_url = upload_video_to_bucket(output_path)
        logger.info(f"Vídeo enviado para o bucket: {video_url}")

        # inserir o video no banco de dados
        insert_video_bd =inserir_video(id_video, video_url, theme, titulo_nc, "HEYGEN")
        logger.info(f"Video inserido no banco de dados: {insert_video_bd}")

    except ffmpeg.Error as e:
        logger.error(f"Erro no FFmpeg: {e.stderr.decode()}")
        if 'comando_ffmpeg' in locals():
            logger.error(f"Comando que falhou: {' '.join(comando_ffmpeg)}")
    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}")


def gerar_momentos_zoom(duracao_video, qtd_zooms=3, intervalo_minimo=10):
    """
    Gera momentos de zoom aleatórios espaçados pelo intervalo mínimo no vídeo.
    """
    momentos_zoom = []
    tempo_atual = 0
    
    # Divide o tempo total do vídeo em partes para garantir espaçamento entre os zooms
    espacamento = duracao_video // (qtd_zooms + 1)
    
    for _ in range(qtd_zooms):
        inicio_zoom = tempo_atual + random.uniform(0, espacamento - intervalo_minimo)
        fim_zoom = inicio_zoom + 15  # Duração do zoom de 15 segundos

        # Garante que o zoom não ultrapasse o final do vídeo
        if fim_zoom > duracao_video:
            fim_zoom = duracao_video - 1

        momentos_zoom.append((inicio_zoom, fim_zoom))
        tempo_atual += espacamento
    
    return momentos_zoom


def criar_background_arredondado(bg_path, texto, padding_x=20, padding_y=10, cor_fundo=(55, 21, 59, 235), raio=15):
    """
    Cria uma imagem de fundo arredondada para o texto.
    
    Args:
        bg_path (str): Caminho onde a imagem será salva
        texto (str): Texto a ser exibido (usado apenas para calcular o tamanho)
        padding_x (int): Padding horizontal
        padding_y (int): Padding vertical
        cor_fundo (tuple): Cor de fundo (R, G, B, A)
        cor_borda (tuple): Cor da borda (R, G, B)
        espessura_borda (int): Espessura da borda
        raio (int): Raio dos cantos arredondados
    """
    # Configuração da fonte
    fonte_path = os.path.join(get_root_path(), "fonte", "Poppins-Bold.ttf")
    fonte_size = 36
    
    # Cria uma imagem temporária para medir o tamanho do texto
    img_temp = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    draw_temp = ImageDraw.Draw(img_temp)
    
    try:
        fonte = ImageFont.truetype(fonte_path, fonte_size)
    except IOError:
        logger.warning(f"Fonte {fonte_path} não encontrada. Usando fonte padrão.")
        fonte = ImageFont.load_default()

    bbox = draw_temp.textbbox((0, 0), texto, font=fonte)
    largura_texto, altura_texto = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # Calcula o tamanho da imagem
    largura = largura_texto + 2 * padding_x
    altura = altura_texto + 2 * padding_y
    
    # Cria a imagem com fundo transparente
    img = Image.new('RGBA', (largura, altura), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Desenha o retângulo arredondado - removendo a borda para evitar problemas de alinhamento
    draw.rounded_rectangle([(0, 0), (largura-1, altura-1)], radius=raio, fill=cor_fundo)
    
    # Não desenha o texto, apenas salva o fundo
    img.save(bg_path)
    return bg_path

def verifica_dimensao_video(video_path):
    """
    Verifica as dimensões do vídeo.
    """
    try:
        metadata = ffmpeg.probe(video_path)
        width = metadata['streams'][0]['width']
        height = metadata['streams'][0]['height']
        return width, height
    except Exception as e:
        logger.error(f"Erro ao verificar dimensões do vídeo: {e}")
        return None, None
