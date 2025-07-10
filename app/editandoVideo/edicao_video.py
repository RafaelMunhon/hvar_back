import logging
import os
import requests
from app.core.logger_config import setup_logger
from app.core import file_manager
from app.config import ffmpeg as ffmpeg_config
from app.videoPexel.subtitles import get_video_duration
from dotenv import load_dotenv 
from app.services import text_overlay_service, video_service, speech_service
import json
import traceback

load_dotenv()
logger = setup_logger(__name__)

def editandoVideo(fileNameVideoHeyGen, json_data=None, lista_imagens=None, envato=None, ID=None, theme=None, titulo_nc=None):
    """
    Edita um vídeo com base em um JSON de configuração.

    Args:
        fileNameVideoHeyGen (str): Nome do arquivo de vídeo.
        json_data (dict): O objeto do json de configuração a ser utilizado em sua lógica.  
        lista_imagens (list): Lista de imagens a serem utilizadas no vídeo.
        envato (bool): Indica se as imagens serão buscadas no Envato.
        ID (str): ID do vídeo.
        theme (str): Tema do vídeo.
        titulo_nc (str): Título do vídeo.

    Retorna:
        None
    """
    try:
        logger.info("=== Iniciando função editandoVideo ===")
        
        # Se json_data for um caminho de arquivo, carregar o conteúdo
        if isinstance(json_data, str):
            logger.info(f"Tentando carregar JSON do arquivo: {json_data}")
            try:
                with open(json_data, 'r', encoding='utf-8') as f:
                    json_data = json.loads(f.read())
                logger.info("JSON carregado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao carregar arquivo JSON: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return

        logger.info(f"editandoVideo - lista_imagens : {lista_imagens}")
        logger.info(f"editandoVideo - envato : {envato}")
        logger.info(f"editandoVideo - ID : {ID}")
        logger.info(f"editandoVideo - theme : {theme}")
        logger.info(f"editandoVideo - titulo_nc : {titulo_nc}")
        logger.info(f"editandoVideo - fileNameVideoHeyGen : {fileNameVideoHeyGen}")

        filename_video = f"{fileNameVideoHeyGen}"
        logger.info(f"Nome do arquivo de vídeo definido: {filename_video}")

        pasta_arquivos_temporarios = ffmpeg_config.get_temp_files_path()
        pasta_videos_finalizados = ffmpeg_config.get_videos_finalized_path()
        logger.info(f"Pasta temporária: {pasta_arquivos_temporarios}")
        logger.info(f"Pasta de vídeos finalizados: {pasta_videos_finalizados}")

        file_manager.criar_diretorio_se_nao_existir(pasta_arquivos_temporarios)
        file_manager.criar_diretorio_se_nao_existir(pasta_videos_finalizados)

        caminho_download = os.path.join(ffmpeg_config.get_base_path(), "downloadHeygen")
        logger.info(f"Caminho de download: {caminho_download}")

        logger.info(f"Iniciando processo do vídeo: {filename_video} com a transcrição")
   
        video_path = os.path.join(caminho_download, filename_video)
        logger.info(f"Caminho completo do vídeo: {video_path}")

        if not os.path.exists(video_path):
            logger.error(f"Vídeo não encontrado no caminho: {video_path}")
            return

        logger.info("Vídeo encontrado, iniciando processamento.")

        try:
            logger.info("Tentando obter duração do vídeo...")
            duracao_video = get_video_duration(video_path)
            logger.info(f"Duração do vídeo obtida: {duracao_video} segundos")

            if not duracao_video:
                logger.error("Não foi possível obter a duração do vídeo.")
                return

            logger.info("Verificando code snippets no JSON...")
            lista_imagens_codigo = veridicarCodesnippet(json_data)
            logger.info(f"Code snippets encontrados: {len(lista_imagens_codigo)}")

            if json_data and 'cenas' in json_data and "imagens" in json_data:
                logger.info("JSON válido com cenas e imagens encontrado")
                imagens_locais = {}
                momento_chave = None

                if not lista_imagens and envato == False:
                    logger.info("Processando imagens do JSON...")
                    for imagem in json_data["imagens"]:
                        logger.info(f"Processando imagem: {imagem}")
                        if 'urlImg' in imagem and isinstance(imagem.get('urlImg'), str):
                            url_img_base = os.path.basename(imagem["urlImg"])
                            logger.info(f"Nome base da imagem: {url_img_base}")
                            nome_base_imagem = url_img_base.split('.')[0]

                            filename_imagem = os.path.join(pasta_arquivos_temporarios, f"{nome_base_imagem}.png")
                            logger.info(f"Tentando baixar imagem para: {filename_imagem}")
                            
                            imagem_baixada = baixar_imagem(imagem["urlImg"], filename_imagem)
                            
                            if imagem_baixada:
                                logger.info(f"Imagem baixada com sucesso: {imagem_baixada}")
                                imagens_locais[imagem["urlImg"]] = imagem_baixada

                            momento_chave = imagem.get('momentoChave', None)
                            if isinstance(momento_chave, str):
                                logger.info(f"Momento chave encontrado: {momento_chave}")
                                lista_imagens.append({
                                    "urlImg": imagem["urlImg"],
                                    "caminho": imagens_locais.get(imagem["urlImg"]),
                                    "momentoChave": momento_chave,
                                    "nomeArquivo": f"{nome_base_imagem}.png"
                                })
                
                logger.info("Extraindo áudio do vídeo...")
                audio_file_path = os.path.join(pasta_arquivos_temporarios, f"{os.path.basename(video_path).split('.')[0]}.wav")
                logger.info(f"Caminho do arquivo de áudio: {audio_file_path}")
                
                try:
                    speech_service.extract_audio_from_video(video_path, audio_file_path)
                    logger.info("Áudio extraído com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao extrair áudio: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return

                logger.info("Iniciando transcrição do áudio...")
                transcricao_com_tempos = speech_service.transcribe_with_timestamps(audio_file_path)
                logger.info(f"Transcrição concluída com {len(transcricao_com_tempos) if transcricao_com_tempos else 0} palavras")

                gravar_log(lista_imagens, envato, ID, theme, titulo_nc, fileNameVideoHeyGen, transcricao_com_tempos)

                all_palavras_encontradas = []
                all_texto_transcrito = ""

                logger.info("Processando cenas do vídeo...")
                for cena in json_data['cenas']:
                    if "script" in cena:
                        texto_transcrito = cena["script"]
                        palavras_encontradas = cena.get('palavras_chave', [])
                        
                        all_palavras_encontradas.extend(palavras_encontradas)
                        all_texto_transcrito = " ".join([all_texto_transcrito, texto_transcrito])

                logger.info(f"Total de palavras-chave encontradas: {len(all_palavras_encontradas)}")
                logger.info("Iniciando criação do vídeo com overlays...")
                
                try:
                    text_overlay_service.criar_video(
                        video_path, 
                        all_palavras_encontradas, 
                        lista_imagens, 
                        transcricao_com_tempos, 
                        duracao_video, 
                        ID, 
                        theme, 
                        titulo_nc, 
                        lista_imagens_codigo
                    )
                    logger.info("Vídeo criado com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao criar vídeo: {str(e)}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    raise

            else:
                logger.error("Formato json inválido ou sem cenas ou imagens!")

        except Exception as e:
            logger.error(f"Erro ao processar o vídeo: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    except Exception as e:
        logger.error(f"Erro ao processar o vídeo, arquivo JSON: {str(e)}")
        logger.error(f"Traceback completo: {traceback.format_exc()}")

    logger.info("=== Script finalizado ===")

def baixar_imagem(url, filename):
    """
    Baixa uma imagem de uma URL e salva em um arquivo local.

    Args:
        url (str): URL da imagem a ser baixada.
        filename (str): Caminho completo para salvar a imagem.

    Retorna:
        str: Caminho completo para a imagem salva.
    """
    try:
        logger.info(f"Iniciando download da imagem: {url}")
        logger.info(f"Salvando imagem em: {filename}")

        response = requests.get(url, stream=True, verify=False)
        response.raise_for_status()

        with open(filename, 'wb') as image_file:
            for chunk in response.iter_content(chunk_size=8192):
                image_file.write(chunk)

        logger.info(f"Imagem baixada e salva em: {filename}")
        return filename

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao baixar imagem: {e}")
        return None

def veridicarCodesnippet(json_data):
    """
    Verifica e processa os code snippets do JSON, gerando imagens para cada um.
    
    Args:
        json_data (dict): JSON contendo a lista de códigos
        
    Returns:
        list: Lista de dicionários com informações das imagens geradas
    """
    imagens_codigo = []
    pasta_temp = ffmpeg_config.get_temp_files_path()
    
    if json_data and 'codigo' in json_data:
        codigos = json_data['codigo']
        
        for i, codigo in enumerate(codigos):
            if ('code-snippet' in codigo and 
                'momentoChaveCodigo' in codigo and 
                'fimMomentoChaveCodigo' in codigo):
                
                try:
                    # Nome do arquivo baseado no índice
                    filename = f"code_snippet_{i}.png"
                    path_name = os.path.join(pasta_temp, filename)
                    
                    # Gerar imagem do código
                    gerar_imagem_codigo(
                        codigo['code-snippet'], 
                        path_name
                    )
                    
                    # Adicionar informações da imagem
                    imagens_codigo.append({
                        "nomeArquivo": filename,
                        "caminho": path_name,
                        "momentoChave": codigo['momentoChaveCodigo'],
                        "fimMomentoChave": codigo['fimMomentoChaveCodigo']
                    })
                    
                    logger.info(f"Imagem gerada para código {i+1}: {path_name}")
                    
                except Exception as e:
                    logger.error(f"Erro ao gerar imagem para código {i+1}: {str(e)}")
                    continue
    
    return imagens_codigo

def gerar_imagem_codigo(codigo, path_name):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import sys
        
        # Dimensões finais desejadas
        final_width = 1920
        final_height = 1080
        
        # Criar imagem
        img = Image.new('RGB', (final_width, final_height), (30, 30, 30))
        draw = ImageDraw.Draw(img)
        
        # Configurações
        font_size = 36
        line_spacing = 1.2
        indent_size = 30
        
        # Carregar fonte
        try:
            if sys.platform == "win32":
                font = ImageFont.truetype("consola.ttf", font_size)
            elif sys.platform == "darwin":
                font = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", font_size)
            else:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        lines = codigo.split('\n')
        
        # Calcular a largura máxima do bloco de código
        max_width = 0
        for line in lines:
            indent_level = len(line) - len(line.lstrip())
            line_width = font.getlength(line) + (indent_level * indent_size)
            max_width = max(max_width, line_width)
        
        # Calcular posição inicial para centralizar o bloco inteiro
        start_x = (final_width - max_width) // 2
        
        # Calcular altura e posição vertical
        line_height = int(font_size * line_spacing)
        total_height = len(lines) * line_height
        start_y = (final_height - total_height) // 2
        
        # Desenhar cada linha
        y = start_y
        for line in lines:
            # Calcular indentação
            indent_level = len(line) - len(line.lstrip())
            x = start_x + (indent_level * indent_size)
            
            # Desenhar linha
            if line.strip().startswith('#'):
                draw.text((x, y), line, font=font, fill=(106, 153, 85))
            else:
                draw.text((x, y), line, font=font, fill=(212, 212, 212))
            
            y += line_height
        
        # Salvar imagem
        img.save(path_name, quality=95)
        
    except Exception as e:
        logger.error(f"Erro ao gerar imagem do código: {str(e)}")
        
        raise


def gravar_log(lista_imagens, envato, ID, theme, titulo_nc, fileNameVideoHeyGen, transcricao_com_tempos):
    """
    Grava informações no arquivo de log.

    Args:

    
    """
    try:

        # Criar arquivo de log com as informações
        log_path = os.path.join(ffmpeg_config.get_temp_files_path(), 'video_info.txt')

        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Informações do Vídeo:\n")
            f.write(f"Lista de imagens: {lista_imagens}\n")
            f.write(f"Envato: {envato}\n")
            f.write(f"ID: {ID}\n")
            f.write(f"Theme: {theme}\n")
            f.write(f"Título NC: {titulo_nc}\n")
            f.write(f"Nome do arquivo: {fileNameVideoHeyGen}\n")
            f.write(f"Transcricao com tempos: {transcricao_com_tempos}\n")
        logger.info(f"Informações salvas em: {log_path}")
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo de log: {e}")

# if __name__ == "__main__":
#       try:
#           # Definindo variáveis com caminhos corretos
#           fileNameVideoHeyGen = "video_20250520T165954.mp4"
#           id = 'e357d2e6-f174-436e-97ee-3645308c6684'
#           theme = 'Introdução aos princípios fundamentais da computação'
#           titulo_nc = 'Humano versus máquina'
#           json_data = os.path.join(ffmpeg_config.get_root_path(), "output_jsons","2025-05-20_16-52-53_output_20250520165253.json")
#           envato = True
#           imagem_path = [{'nomeArquivo': 'Abstract_mind_metaphysics_concept,_human_head,_ai_brain,_creative_idea.jpg', 'momentoChave': 'Estamos falando especificamente da metafísica, a construção', 'caminho': 'app/arquivosTemporarios/Abstract_mind_metaphysics_concept,_human_head,_ai_brain,_creative_idea.jpg'}, {'nomeArquivo': 'Abstract_mind_metaphysics_concept,_human_head,_ai_brain,_creative_idea.jpg', 'momentoChave': 'Estamos falando especificamente da metafísica, a construção'}, {'nomeArquivo': 'Chess_board_game,_strategy_and_competition_success_concept,_intelligence.jpg', 'momentoChave': 'Enquanto as máquinas não receberam todas as informações', 'caminho': 'app/arquivosTemporarios/Chess_board_game,_strategy_and_competition_success_concept,_intelligence.jpg'}]
#           print("Iniciando processamento do vídeo...")
#           editandoVideo(fileNameVideoHeyGen, json_data, imagem_path, envato, id, theme, titulo_nc)
#           print("Processamento finalizado!")
      
#       except Exception as e:
#          print(f"Erro durante a execução: {str(e)}")

