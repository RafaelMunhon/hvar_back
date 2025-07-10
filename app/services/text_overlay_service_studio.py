import random
import ffmpeg
import logging
import shutil
import os
import requests
from datetime import datetime
import math
from PIL import Image, ImageDraw
import uuid
import traceback

from app.config.ffmpeg import get_root_path
from app.searchImagens.searchImagens_Google import busca_imagens

# Configuração básica do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Variável global para armazenar os últimos tempos usados
_ultimo_tempo_fim = 0
_ultimo_tempo_fim_imagem = 0  # Nova variável para imagens

def get_temp_files_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "arquivosTemporarios")

def get_videos_finalized_path():
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
        tempo_inicio = 1.0 if not eh_imagem else 4.0
        tempo_fim = tempo_inicio + (1.0 if not eh_imagem else 2.0)
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


def criar_efeitos_artisticos():
    """
    Cria uma coleção de efeitos artísticos e dinâmicos para texto em vídeos.
    """
    efeitos = {
        'movimentos_x': [
            r'(w-tw)/2',  # Centralizado
        ],
        'movimentos_y': [
            r'h*0.7',  # Abaixo do centro
            r'h*0.7 + sin(t*3)*50',              # Flutuação vertical
            r'h*0.7 + cos(t*2)*30',              # Ondulação suave
            r'h*0.8 + sin(t)*20',                # Movimento próximo ao rodapé
            r'h*0.8 + t*10',                     # Subida gradual
        ],
        'estilos_texto': {
            'dinamico': {
                'alpha': 'if(lt(t,1),t,1-min(1,max(0,(t-fadein)/(fadeout-fadein))))',
                'scale': 'if(lt(t,1),1+t/2,1+sin(t*2)*0.1)',
                'rotation': 'sin(t*2)*5'
            },
            'fade_suave': {
                'alpha': 'if(lt(t,1),t,1-min(1,max(0,(t-fadein)/(fadeout-fadein))))',
            },
            'zoom_sutil': {
                'scale': '1 + sin(t)*0.05'
            },
            'sem_efeitos': {
                'alpha': '1',
                'scale': '1',
                'rotation': '0'
            }
        },
        'cores_gradiente': [
            '0xFF0000',  # Vermelho
            '0x00FF00',  # Verde
            '0x0000FF',  # Azul
            '0xFFFF00',  # Amarelo
        ],
        'sombras_artisticas': [
            {'x': 3, 'y': 3, 'color': '0x000000@0.5'},    # Sombra clássica
            {'x': -2, 'y': -2, 'color': '0x000000@0.3'},  # Sombra invertida
            {'x': 1, 'y': 1, 'color': '0x4169E1@0.4'}     # Sombra azulada
        ],
        'fontes_modernas': [
            'C:/projetos/yduqs_back/fonte/Poppins-Bold.ttf',
            'C:/projetos/yduqs_back/fonte/Hypop-LightItalic.otf',
            'C:/projetos/yduqs_back/fonte/HappySeason-Bold.ttf'
        ]
    }
    return efeitos

def gerar_drawtext_info(palavras_encontradas, transcricao_com_tempos):
    """
    Gera informações de texto com efeitos artísticos avançados.

    Args:
        palavras_encontradas (list): Lista de palavras encontradas na transcrição
        transcricao_com_tempos (list): Lista de dicionários com a transcrição e timestamps

    Retorna:
        list: Lista de dicionários com informações para overlay.
    """
    efeitos = criar_efeitos_artisticos()
    drawtext_info = []

    for palavra in palavras_encontradas:
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, palavra, eh_imagem=False)
        
        if tempo_inicio is not None and tempo_fim is not None:
            # Aumenta a duração dos efeitos
            duracao_efeito = tempo_fim - tempo_inicio
            tempo_inicio_efeito = tempo_inicio - 1  # Inicia 1 segundo antes
            tempo_fim_efeito = tempo_fim + 2        # Termina 2 segundos depois

            # Verifica se a palavra é composta por duas partes
            partes = palavra.split()
            if len(partes) == 2:
                # Duração do movimento (em segundos)
                duracao_movimento = tempo_fim - tempo_inicio

                # Decide aleatoriamente se usa efeitos ou não
                usar_efeitos = random.random() > 0.3  # 70% de chance de usar efeitos

                # Posições Y para evitar sobreposição
                y1 = f'h*0.6'  # Primeira palavra acima do centro
                y2 = f'h*0.8'  # Segunda palavra abaixo do centro

                # Primeira palavra: centralizada
                info_texto_esquerda = {
                    'text': partes[0].upper(),
                    'x': r'(w-tw)/2',  # Centralizado
                    'y': y1,
                    'fontsize': 80 if len(palavra) > 20 else random.choice([80, 100, 120, 150]),
                    'fontcolor': random.choice(efeitos['cores_gradiente']),
                    'fadeInStart': tempo_inicio_efeito,
                    'fadeInEnd': tempo_inicio_efeito + 2,  # Aumenta o tempo de fade-in
                    'fadeOutStart': tempo_fim_efeito - 2,  # Aumenta o tempo de fade-out
                    'fadeOutEnd': tempo_fim_efeito,
                    'fontfile': random.choice(efeitos['fontes_modernas']),
                }

                # Segunda palavra: centralizada
                info_texto_direita = {
                    'text': partes[1].upper(),
                    'x': r'(w-tw)/2',  # Centralizado
                    'y': y2,
                    'fontsize': 80 if len(palavra) > 20 else random.choice([80, 100, 120, 150]),
                    'fontcolor': random.choice(efeitos['cores_gradiente']),
                    'fadeInStart': tempo_inicio_efeito,
                    'fadeInEnd': tempo_inicio_efeito + 2,  # Aumenta o tempo de fade-in
                    'fadeOutStart': tempo_fim_efeito - 2,  # Aumenta o tempo de fade-out
                    'fadeOutEnd': tempo_fim_efeito,
                    'fontfile': random.choice(efeitos['fontes_modernas']),
                }

                # Adiciona efeitos dinâmicos (se aplicável)
                estilo_atual = random.choice(list(efeitos['estilos_texto'].values())) if usar_efeitos else efeitos['estilos_texto']['sem_efeitos']
                info_texto_esquerda.update({
                    'alpha': estilo_atual.get('alpha', '1'),
                    'scale': estilo_atual.get('scale', '1'),
                    'rotation': estilo_atual.get('rotation', '0')
                })
                info_texto_direita.update({
                    'alpha': estilo_atual.get('alpha', '1'),
                    'scale': estilo_atual.get('scale', '1'),
                    'rotation': estilo_atual.get('rotation', '0')
                })

                # Adiciona sombra artística
                sombra = random.choice(efeitos['sombras_artisticas'])
                info_texto_esquerda.update({
                    'shadowx': sombra['x'],
                    'shadowy': sombra['y'],
                    'shadowcolor': sombra['color']
                })
                info_texto_direita.update({
                    'shadowx': sombra['x'],
                    'shadowy': sombra['y'],
                    'shadowcolor': sombra['color']
                })

                # Adiciona efeito de caixa ocasional
                if random.random() > 0.6:
                    info_texto_esquerda.update({
                        'box': 1,
                        'boxcolor': '0x000000@0.3',
                        'boxborderw': 15
                    })
                    info_texto_direita.update({
                        'box': 1,
                        'boxcolor': '0x000000@0.3',
                        'boxborderw': 15
                    })

                drawtext_info.append(info_texto_esquerda)
                drawtext_info.append(info_texto_direita)
            else:
                # Palavra única: mantém o comportamento original
                info_texto = {
                    'text': palavra.upper(),
                    'x': r'(w-tw)/2',  # Centralizado
                    'y': random.choice(efeitos['movimentos_y']).replace('=', r'\\='),
                    'fontsize': 80 if len(palavra) > 20 else random.choice([80, 100, 120, 150]),
                    'fontcolor': random.choice(efeitos['cores_gradiente']),
                    'fadeInStart': tempo_inicio_efeito,
                    'fadeInEnd': tempo_inicio_efeito + 2,  # Aumenta o tempo de fade-in
                    'fadeOutStart': tempo_fim_efeito - 2,  # Aumenta o tempo de fade-out
                    'fadeOutEnd': tempo_fim_efeito,
                    'fontfile': random.choice(efeitos['fontes_modernas']),
                }

                # Adiciona efeitos dinâmicos
                estilo_atual = random.choice(list(efeitos['estilos_texto'].values()))
                info_texto.update({
                    'alpha': estilo_atual.get('alpha', '1'),
                    'scale': estilo_atual.get('scale', '1'),
                    'rotation': estilo_atual.get('rotation', '0')
                })

                # Adiciona sombra artística
                sombra = random.choice(efeitos['sombras_artisticas'])
                info_texto.update({
                    'shadowx': sombra['x'],
                    'shadowy': sombra['y'],
                    'shadowcolor': sombra['color']
                })

                # Adiciona efeito de caixa ocasional
                if random.random() > 0.6:
                    info_texto.update({
                        'box': 1,
                        'boxcolor': '0x000000@0.3',
                        'boxborderw': 15
                    })

                drawtext_info.append(info_texto)

    return drawtext_info

def gerar_overlay_info(imagem_path, transcricao_com_tempos):
    #logger.info("\n=== Gerando overlay info ===")
    #logger.info(f"Recebido imagem_path com {len(imagem_path)} imagens")
    #logger.info(f"Dados das imagens: {imagem_path}")
    
    overlay_info = []
    for img_info in imagem_path:
        #logger.info(f"\nProcessando imagem: {img_info}")
        nome_arquivo = img_info.get('nomeArquivo')
        momento_chave = img_info.get('momentoChave')
        
        # Passa eh_imagem=True para usar a lógica específica para imagens
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, momento_chave, threshold=0.5, eh_imagem=True)
        
        #logger.info(f"Momento chave: {momento_chave}")
        #logger.info(f"Tempo encontrado - início: {tempo_inicio}, fim: {tempo_fim}")
        
        if tempo_inicio is not None and tempo_fim is not None:
            img_info = {
                'nomeArquivo': nome_arquivo,
                'x': img_info.get('x', 0),
                'y': img_info.get('y', 0),
                'start': tempo_inicio,
                'end': tempo_fim - 1
            }
            overlay_info.append(img_info)
            #logger.info(f"Imagem será inserida: {img_info}")
        else:
            logger.warning(f"Tempo não encontrado para imagem {nome_arquivo}")
    
    #logger.info(f"\nTotal de imagens a serem inseridas: {len(overlay_info)}")
    return overlay_info

def gerar_overlay_info_imagens(imagem_path, transcricao_com_tempos):
    """
    Gera a lista de dicionários overlay_info com base nas informações das imagens e na transcrição.
    """
    logger.info(f"Gerando overlay para {len(imagem_path)} imagens")
    overlay_info = []
    imagens_processadas = set()
    
    # Espaçamento mínimo entre imagens (em segundos)
    espacamento_minimo = 1.5
    
    # Processa as imagens com espaçamento adequado
    for i, img_info in enumerate(imagem_path):
        nome_arquivo = img_info.get('nomeArquivo')
        if nome_arquivo in imagens_processadas:
            continue
        
        momento_chave = img_info.get('momentoChave')
        if not momento_chave:
            continue
            
        logger.info(f"Processando imagem {i+1}/{len(imagem_path)}: {nome_arquivo}")
        logger.info(f"Momento-chave: '{momento_chave}'")
        
        # Busca o tempo na transcrição
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, momento_chave, eh_imagem=True)
        
        if tempo_inicio is not None and tempo_fim is not None:
            # Adiciona a imagem à lista de overlay usando os tempos exatos da frase
            overlay_info.append({
                "nomeArquivo": nome_arquivo,
                "start": tempo_inicio,
                "end": tempo_fim,
                "momentoChave": momento_chave
            })
            
            imagens_processadas.add(nome_arquivo)
            logger.info(f"Imagem '{nome_arquivo}' programada para exibição em {tempo_inicio:.1f}-{tempo_fim:.1f}s")
        else:
            logger.warning(f"Tempo não encontrado para imagem {nome_arquivo}")
    
    return overlay_info

def criar_video(video_path, palavras_encontradas, imagem_path, transcricao_com_tempos, duracao_video, semEfeitos=True):
    """
    Cria um vídeo com efeitos de texto e imagem sobrepostos.

    Args:
        video_path (str): Caminho do vídeo de entrada
        palavras_encontradas (list): Lista de palavras encontradas na transcrição
        imagem_path (list): Lista de dicionários contendo informações das imagens
        transcricao_com_tempos (list): Lista de dicionários com a transcrição e timestamps  
    """
    
    logger.info(f"Iniciando criação do vídeo: {video_path}")
    logger.info(f"Iniciando palavras_encontradas: {palavras_encontradas}")
    logger.info(f"Iniciando imagem_path: {imagem_path}")
    logger.info(f"Iniciando duracao_video: {duracao_video}")
    
    try:
        # Entrada de vídeo
        in_file = ffmpeg.input(video_path)
        logger.info("Entrada de vídeo carregada com sucesso.")

        # Geração de informações de texto e imagem
        logger.info("Gerando informações de texto...")
        if semEfeitos:
            # Modo sem efeitos: usa o estilo antigo
            drawtext_info = gerar_drawtext_info_simples(palavras_encontradas, transcricao_com_tempos)
        else:
            # Modo com efeitos: usa o estilo novo
            drawtext_info = gerar_drawtext_info(palavras_encontradas, transcricao_com_tempos)
        logger.info(f"Informações de texto geradas: {drawtext_info}")

        logger.info("Gerando informações de imagem...")
        overlay_info = gerar_overlay_info_imagens(imagem_path, transcricao_com_tempos)
        logger.info(f"Informações de imagem geradas: {overlay_info}")

        # Aplicação dos textos sobrepostos
        logger.info("\n=== Aplicando textos ao vídeo ===")
        current_stream = in_file
        for info in drawtext_info:
            # Primeiro aplica o background
            if 'background_image' in info:
                bg = ffmpeg.input(info['background_image'])
                
                # Verifica se a palavra tem acento
                palavra = info['text']
                tem_acento = any(c in 'áéíóúâêîôûãõàèìòùäëïöüÁÉÍÓÚÂÊÎÔÛÃÕÀÈÌÒÙÄËÏÖÜ' for c in palavra)
                
                # Ajusta a posição Y do background baseado na presença de acento
                bg_y = '(H*0.75-9)' if tem_acento else '(H*0.75-18)'
                
                logger.info(f"\nAplicando background para: {palavra}")
                logger.info(f"- Tem acento: {tem_acento}")
                logger.info(f"- Posição Y: {bg_y}")
                
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
            
        # Aplicação das imagens sobrepostas
        logger.info("\n=== Aplicando imagens ao vídeo ===")
        for img_info in overlay_info:
            img_path = os.path.join(temp_path, img_info['nomeArquivo'])
            logger.info(f"\nProcessando imagem: {img_info['nomeArquivo']}")
            logger.info(f"- Caminho completo: {img_path}")
            logger.info(f"- Existe arquivo? {os.path.exists(img_path)}")
            
            if os.path.exists(img_path):
                logger.info("Iniciando sobreposição da imagem...")
                # Ajusta a imagem para preencher a tela sem distorção
                overlay_stream = (
                    ffmpeg.input(img_path)
                    .filter('scale', 
                        'if(gt(iw/ih,1920/1080),1920,trunc(1080*iw/ih/2)*2)', 
                        'if(gt(iw/ih,1920/1080),trunc(1920*ih/iw/2)*2,1080)'
                    )
                    .filter('pad', 1920, 1080, '(ow-iw)/2', '(oh-ih)/2')
                )

                current_stream = current_stream.overlay(
                    overlay_stream,
                    x='(main_w-overlay_w)/2',
                    y='(main_h-overlay_h)/2',
                    enable=f"between(t,{img_info['start']},{img_info['end']})"
                )
                logger.info("Imagem sobreposta com sucesso")
            else:
                logger.error(f"Arquivo de imagem não encontrado: {img_path}")

        logger.info("Imagens aplicadas com sucesso.")

        # Configuração de saída
        output_path = os.path.join(final_path, f"video_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        # Garantir que o diretório de saída existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        logger.info(f"Configurando saída para: {output_path}")
        logger.info(f"Diretório de saída existe: {os.path.exists(os.path.dirname(output_path))}")
        
        out = ffmpeg.output(
            current_stream, in_file['a'],
            output_path,
            vcodec='libx264',
            preset='fast',
            acodec='aac',
            audio_bitrate='192k',
            crf=18
        )

        # Log do comando ffmpeg
        logger.info("\n=== Comando FFmpeg Completo ===")
        logger.info(f"ffmpeg {' '.join(out.get_args())}")

        # Execução do comando FFmpeg
        logger.info("Executando comando FFmpeg...")
        try:
            out, err = ffmpeg.run(out, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            logger.error("Erro ao processar vídeo: ffmpeg error")
            logger.error(f"FFmpeg stderr output:\n{e.stderr.decode() if e.stderr else 'No stderr'}")
            logger.error(f"FFmpeg stdout output:\n{e.stdout.decode() if e.stdout else 'No stdout'}")
            logger.error("Stack trace completo:")
            logger.error(traceback.format_exc())
        logger.info(f"Vídeo finalizado com sucesso: {output_path}")
        
        return output_path  # Retorna o caminho do vídeo processado

    except Exception as e:
        logger.error(f"Erro ao processar vídeo: {str(e)}")
        logger.error("Stack trace completo:", exc_info=True)
        if isinstance(e, ffmpeg.Error):
            logger.error(f"FFmpeg stderr output:\n{e.stderr.decode() if e.stderr else 'No stderr'}")
            logger.error(f"FFmpeg stdout output:\n{e.stdout.decode() if e.stdout else 'No stdout'}")
        return None


def gerar_drawtext_info_simples(palavras_encontradas, transcricao_com_tempos):
    drawtext_info = []
    for palavra in palavras_encontradas:
        tempo_inicio, tempo_fim = encontrar_tempo_frase(transcricao_com_tempos, palavra, eh_imagem=False)
        if tempo_inicio is not None and tempo_fim is not None:
            # Posição Y comum para texto e background (75% da altura do vídeo)
            posicao_y = '(h*0.75)'  # Alterado de 0.8 para 0.75
            
            #logger.info("\n=== Gerando informações de texto ===")
            #logger.info(f"Palavra: {palavra}")
            #logger.info(f"Tempo início: {tempo_inicio}, Tempo fim: {tempo_fim}")
            
            # Cria background personalizado
            fonte_size = 50
            bg_path = criar_background_arredondado(palavra, fonte_size)
            
            #logger.info(f"Background gerado: {bg_path}")
            #logger.info(f"Posição Y definida: {posicao_y}")
            
            fonte_style = os.path.join(get_root_path(), "fonte", "Poppins-Bold.ttf")
            #logger.info(f"Fonte: {fonte_style}")
            
            # Configura o texto
            text_info = {
                'text': palavra.upper(),
                'x': '(w-tw)/2',  # w = largura do vídeo, tw = largura do texto
                'y': posicao_y,
                'fontsize': fonte_size,
                'fontcolor': 'white',
                'fadeInStart': tempo_inicio - 0.5,
                'fadeInEnd': tempo_inicio + 0.5,
                'fadeOutStart': tempo_fim - 0.5,
                'fadeOutEnd': tempo_fim + 0.5,
                'fontstyle': fonte_style,
                'fontfile': f'{fonte_style}',
                'background_image': bg_path,
                'background_y': posicao_y,
                'enable': f'between(t,{tempo_inicio-0.5},{tempo_fim+0.5})'
            }
            #logger.info(f"Informações de texto geradas: {text_info}")
            drawtext_info.append(text_info)
            
    return drawtext_info


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

def criar_background_arredondado(texto, fonte_size, padding_horizontal=5, padding_vertical=30, radius=15):
    """
    Cria um background com cantos arredondados que se adapta ao tamanho do texto.
    """
    # Estima o tamanho do texto (aproximado)
    texto_width = len(texto) * (fonte_size * 0.8)  # Aumentado de 0.7 para 0.8
    
    # Adiciona uma largura mínima para palavras curtas
    largura_minima = fonte_size * 2  # Garante um mínimo de 2 caracteres de largura
    texto_width = max(texto_width, largura_minima)
    
    texto_height = fonte_size
    
    # Adiciona padding
    width = int(texto_width + (padding_horizontal))
    height = int(texto_height + (padding_vertical))
    
    # Cria uma imagem com transparência
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Desenha o retângulo com cantos arredondados
    rect = [(0, 0), (width, height)]
    draw.rounded_rectangle(rect, radius, fill=(55, 21, 59, 235))
    
    # Salva a imagem
    output_path = os.path.join(temp_path, f'bg_{texto[:10]}_{uuid.uuid4().hex[:8]}.png')
    img.save(output_path)
    
    return output_path

def processar_imagens(json_data, transcricao_com_tempos):
    """
    Processa as imagens do JSON e retorna uma lista de informações para overlay.
    """
    imagens = []
    
    if "imagens" in json_data and json_data["imagens"]:
        for i, img in enumerate(json_data["imagens"]):
            momento_chave = img.get("momentoChave", "")
            descricao_busca = img.get("descricaoBuscaEnvato", "")
            
            if not momento_chave or not descricao_busca:
                continue
                
            # Gera um nome de arquivo único para a imagem
            filename = f"{descricao_busca.replace(' ', '_')[:50]}.jpg"
            filename = ''.join(c for c in filename if c.isalnum() or c in ['_', '-', '.'])
            
            # Caminho completo para salvar a imagem
            path_name = os.path.join(get_temp_files_path(), filename)
            
            # Busca a imagem usando a nova função que tenta múltiplas fontes
            imagens = busca_imagens(imagens, descricao_busca, filename, path_name, momento_chave, transcricao_com_tempos)
    
    # Gera as informações de overlay para as imagens encontradas
    overlay_info = gerar_overlay_info_imagens(imagens, transcricao_com_tempos)
    
    return overlay_info
