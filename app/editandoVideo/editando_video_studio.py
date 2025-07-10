import logging
import os
from google.cloud import storage
from app import settings
from app.config.gemini_client import get_gemini_manager
from app.videoPexel.subtitles import get_video_duration
import speech_recognition as sr
import time
import json

from app.config import ffmpeg
from app.config.vertexAi import generate_content
from app.core import file_manager
from app.searchImagens import searchImagens_Envato, searchImagens_Google, searchImagens_GoogleImagem, searchImagens_Pexel
from app.searchImagens.searchImagens_Envato import buscar_imagens_envato as busca_imagens_envato
from app.services import video_service
from app.services.speech_service import extract_audio, transcribe_with_timestamps, upload_video_to_bucket
from app.services.text_overlay_service_studio import criar_video
from app.services.vertexai_service import encontrar_palavras_chaves_imagem
from app.core.logger_config import setup_logger
from app.bd.bd import inserir_video_pexel

from dotenv import load_dotenv

# Adiciona no início do arquivo, após os outros imports
logger = setup_logger(__name__)

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

#nome_arquivo = "zanata_sem lettering_10_percent_acelerado_alta.mp4"
pasta_videos_estudio = ffmpeg.get_files_estudio_videos_path()
file_manager.criar_diretorio_se_nao_existir(pasta_videos_estudio)

pasta_temp_videos_estudio = ffmpeg.get_temp_files_path()
file_manager.criar_diretorio_se_nao_existir(pasta_temp_videos_estudio)

def download_video_from_gcs(video_path):
    """
    Faz o download de um vídeo do GCS para o sistema local.
    
    Args:
        video_path (str): Caminho do vídeo no GCS (https:// ou gs://)

    Retorna:
        str: Caminho local do vídeo baixado
    """
    try:
        # Configura o cliente do GCS
        storage_client = storage.Client()
        
        # Extrai o nome do bucket e o caminho do arquivo
        if video_path.startswith('gs://'):
            # Formato gs://bucket/path/to/file
            bucket_name = video_path.replace('gs://', '').split('/')[0]
            blob_name = '/'.join(video_path.replace('gs://', '').split('/')[1:])
        else:
            # Formato https://storage.googleapis.com/bucket/path/to/file
            parts = video_path.replace('https://storage.googleapis.com/', '').split('/')
            bucket_name = parts[0]
            blob_name = '/'.join(parts[1:])
            
        logger.info(f"Bucket: {bucket_name}")
        logger.info(f"Blob: {blob_name}")
        
        # Obtém referências para o bucket e blob
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Define o caminho local para salvar o vídeo
        local_path = ffmpeg.get_temp_files_path()
        local_video_path = os.path.join(local_path, os.path.basename(blob_name))
        
        # Faz o download do vídeo
        logger.info(f"Iniciando download do vídeo para: {local_video_path}")
        blob.download_to_filename(local_video_path)
        logger.info(f"Vídeo baixado com sucesso para: {local_video_path}")
        
        return local_video_path
        
    except Exception as e:
        logger.error(f"Erro ao fazer download do vídeo do GCS: {str(e)}")
        raise

async def tratamento_videos(video_path=None, site='envato'):
    """
    Processa um vídeo para edição e criação de um vídeo final.

    Args:
        video_path (str, opcional): Caminho do vídeo no GCS (https:// ou gs://)
        site (str, opcional): Site de origem do vídeo (default: 'envato')

    Retorna:
        bool: True se o vídeo foi processado com sucesso, False caso contrário
    """ 
    imagem_path = []
    
    try:
        if video_path:
            # Primeiro, baixa o vídeo do GCS
            video_path_local = download_video_from_gcs(video_path)
            logger.info(f"Processando vídeo local: {video_path_local}")

             # Extrai o áudio da narração para transcrição
            audio_file = os.path.join(pasta_temp_videos_estudio, "video_studio_audio.wav")
            if not extract_audio(video_path_local, audio_file):
                logger.error("Falha ao extrair áudio do vídeo")
                raise Exception("Falha ao extrair áudio da narração!")

            # Transcreve o áudio para obter os timestamps
            print("\nTranscrevendo narração para sincronizar legendas...")
            # Mudando para a versão que usa GCS para áudios longos
            transcricao_com_tempos = transcribe_with_timestamps(audio_file)
            if transcricao_com_tempos:
                # Formata a transcrição completa
                transcricao = " ".join([item["word"] for item in transcricao_com_tempos])
            else:
                transcricao = None

            duracao_video = get_video_duration(video_path_local)
            duracao_video = float(duracao_video)
            logger.info(f"Duração do vídeo: {duracao_video} segundos")

            #Quantidade de imagens no video.
            # Calcula quantidade de imagens baseado na duração do vídeo
            quantidade_imagens = int((duracao_video / 60) * 4)
            #quantidade_palavras_chaves = int((duracao_video / 60) * 10)
            # Convertendo minutos para segundos e dividindo por 5 (uma palavra a cada 5 segundos)
            quantidade_palavras_chaves = int(duracao_video / 5)
            logger.info(f"Quantidade de imagens a serem buscadas: {quantidade_imagens}")
            logger.info(f"Quantidade de palavras-chave a serem buscadas: {quantidade_palavras_chaves}")

            if transcricao:
                logger.info(f"Transcrição: {transcricao}")
                json_data = await encontrar_palavras_chaves_imagem(transcricao, quantidade_palavras_chaves, quantidade_imagens)
                
                # Log para debug
                logger.info("JSON recebido para imagens:")
                logger.info(json_data)
                
                lista_palavras_chaves = json_data['palavras_chaves']
                imagem_path = list_imagem_envato(json_data, imagem_path, site, transcricao)
                
                # Log para debug do resultado da busca
                logger.info(f"Resultado da busca de imagens:")
                logger.info(f"Site usado: {site}")
                logger.info(f"Quantidade de imagens encontradas: {len(imagem_path)}")
                for img in imagem_path:
                    logger.info(f"Imagem: {img}")

                logger.info(f"video_path_local: {video_path_local}")
                logger.info(f"Lista de palavras-chave: {lista_palavras_chaves}")
                logger.info(f"Lista de imagens: {imagem_path}")
                logger.info(f"transcricao_com_tempos: {transcricao_com_tempos}")
                logger.info(f"duracao_video: {duracao_video}")

                # Limpa memória
                #del json_data
                
                # Processa o vídeo e obtém o caminho do vídeo final
                video_final = criar_video(video_path_local, lista_palavras_chaves, imagem_path, transcricao_com_tempos, duracao_video)
                
                if video_final:
                    logger.info(f"Vídeo processado: {video_final}")
                    # Faz upload para o bucket
                    bucket_url = upload_video_to_bucket(video_final)
                    
                    if bucket_url:
                        # Salva no banco de dados
                        video_id = inserir_video_pexel(bucket_url, 'STUDIO')
                        if video_id:
                            logger.info(f"Vídeo processado e salvo com sucesso. ID: {video_id}")
                            return True
                    
                logger.error("Falha ao processar/salvar vídeo")
                return False
            else:
                logger.error("Falha ao transcrever o vídeo")
                return False

    except Exception as e:
        logger.error(f"Erro ao processar vídeo: {str(e)}")
        return False

def list_imagem_envato(json_data, lista_imagens, site, transcricao):
    """
    Lista imagens de acordo com o site especificado.

    Args:
        json_data (dict): Dados JSON contendo informações sobre as imagens
        lista_imagens (list): Lista de imagens existentes   
        site (str): Site de origem das imagens

    Retorna:
        list: Lista de imagens encontradas
    """
    if site != 'none':
        pasta_arquivos_temporarios = ffmpeg.get_temp_files_path()
        file_manager.criar_diretorio_se_nao_existir(pasta_arquivos_temporarios)

        for imagem in json_data["imagens"]:
                    
                    # Verifica se 'urlimg' existe e é uma string
                    if 'descricaoBuscaEnvato' in imagem and isinstance(imagem.get('descricaoBuscaEnvato'), str):
                        
                        # Extrair nome base da URL
                        url_img_base = os.path.basename(imagem["descricaoBuscaEnvato"])  # Pega a url para extrair a parte que nomeia as fotos.
                        
                        nome_base_imagem_aux = url_img_base.replace(' ', '_')
                        nome_base_imagem = nome_base_imagem_aux.split('.')[0] # Tira o .jpg .jpeg ou qualquer outro do nome.
                        
                        momento_chave = imagem.get('momentoChave', None)
                        filename_imagem = f"{nome_base_imagem}.jpg"  # Utilizando o nome customizado e sempre salva como png
                        path_name = os.path.join(pasta_arquivos_temporarios, f"{nome_base_imagem}.jpg")

                        termo_melhorado = melhorarTermo(imagem.get('descricaoBuscaEnvato')) 

                        if site == 'envato':
                            #lista_imagens = searchImagens_Envato.buscar_imagens_envato(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
                            #lista_imagens = searchImagens_Google.busca_imagens_google(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave, transcricao)
                            lista_imagens = searchImagens_GoogleImagem.generate(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
                        elif site == 'pexels':
                            lista_imagens = searchImagens_Pexel.busca_imagens_pexels(lista_imagens, termo_melhorado, filename_imagem, path_name, momento_chave)

        return lista_imagens

async def melhorarTermo(termo):
    prompt_melhorar_palavras_chaves = f"""
    Pegue esse termo no texto abaixo e melhore ele para realizar buscas em bancos de imagens para trazer a melor imagem.
    faça isso em até 5 palavras.
    {termo}
    
    """
    
    try:
        manager = get_gemini_manager()
        responses = await manager.generate_content(prompt_melhorar_palavras_chaves, model=settings.GEMINI) # chama o modelo antigo
        # print("Chamada ao novo modelo")
        # responses = generate(prompt_roteiro) # chama o novo modelo 
        if responses:
            response_text = responses

        if not response_text:
            print("Resposta do modelo está vazia.")
            return None
        
        return response_text
    
    except Exception as e:
            logging.error(f"Erro ao gerar vídeo: {e}")
            print(f"Erro ao decodificar JSON: ")
            return None

if __name__ == "__main__":
    tratamento_videos()