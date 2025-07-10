from flask import Blueprint, jsonify, request
from app.editandoVideo.editando_video_studio import tratamento_videos
from app.core.logger_config import setup_logger
from app.bd.bd import consultar_videos_studio
from google.cloud import storage
from app.config.gcp_config import get_credentials_path
from datetime import datetime, timedelta
from app.config.ffmpeg import clean_temp_directories

video_studio_bp = Blueprint('video_studio', __name__)
logger = setup_logger(__name__)

# Configurações do GCS
BUCKET_NAME = "conteudo-autenticare-videos"

try:
    # Obter caminho correto das credenciais
    credentials_path = get_credentials_path()
    logger.info(f"Usando arquivo de credenciais: {credentials_path}")
    
    # Inicializa o cliente do GCS com as credenciais corretas
    storage_client = storage.Client.from_service_account_json(credentials_path)
    bucket = storage_client.bucket(BUCKET_NAME)
    logger.info("Cliente GCS inicializado com sucesso")
    
except Exception as e:
    logger.error(f"Erro ao inicializar cliente GCS: {str(e)}")
    storage_client = None
    bucket = None

@video_studio_bp.route("/get_signed_url", methods=['POST'])
def get_signed_url():
    """
    Gera URLs assinadas para upload de vídeos no Google Cloud Storage.

    Recebe:
        - POST request com JSON contendo:
            - fileName (str): Nome do arquivo a ser enviado
            - contentType (str, opcional): Tipo de conteúdo do arquivo (default: 'video/mp4')

    Retorna:
        - JSON com:
            - signedUrl (str): URL assinada para upload do arquivo
            - publicUrl (str): URL pública para acesso ao vídeo após upload
            - directUrl (str): URL direta do GCS (formato gs://)
            - fileName (str): Nome único gerado para o arquivo
        - Em caso de erro:
            - JSON com mensagem de erro e código HTTP apropriado
    """
    try:
        if not storage_client or not bucket:
            return jsonify({"error": "Cliente GCS não inicializado"}), 500
            
        # Configurar CORS para o bucket
        bucket.cors = [{
            #'origin': ['https://microservice-yduqs-frontend-745371796940.us-central1.run.app'],  # ou ['https://seu-dominio.com']
            'origin': ['*'],  # ou ['https://seu-dominio.com']
            'method': ['GET', 'HEAD', 'PUT', 'POST', 'OPTIONS'],
            'responseHeader': ['Content-Type', 'Access-Control-Allow-Origin'],
            'maxAgeSeconds': 3600
        }]
        bucket.update()
            
        data = request.json
        file_name = data.get('fileName')
        content_type = data.get('contentType', 'video/mp4')
        
        if not file_name:
            return jsonify({"error": "Nome do arquivo não fornecido"}), 400
            
        # Gera nome único com timestamp (formato ISO)
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%S')
        unique_filename = f"videos_studio/{timestamp}_{file_name}"
        
        logger.info(f"Gerando URL assinada para: {unique_filename}")
        
        # Cria o blob e gera URL assinada
        blob = bucket.blob(unique_filename)
        
        # URL assinada válida por 15 minutos
        signed_url = blob.generate_signed_url(
            version="v4",
            method="PUT",
            expiration=timedelta(minutes=15),
            content_type=content_type,
        )
        
        # URL pública para acesso ao vídeo
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{unique_filename}"
        
        # URL direta do GCS
        direct_url = f"gs://{BUCKET_NAME}/{unique_filename}"
        
        logger.info(f"URL assinada gerada com sucesso")
        logger.info(f"Nome do arquivo: {unique_filename}")
        logger.info(f"URL pública: {public_url}")
        
        return jsonify({
            'signedUrl': signed_url,
            'publicUrl': public_url,
            'directUrl': direct_url,
            'fileName': unique_filename
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar URL assinada: {str(e)}")
        return jsonify({"error": str(e)}), 500

@video_studio_bp.route("/process", methods=['POST'])
async def process_video():
    """
    Processa o vídeo após upload para o GCS

    Recebe:
        - POST request com JSON contendo:
            - videoUrl (str): URL do vídeo a ser processado
            - site (str, opcional): Site de origem do vídeo (default: 'none')   

    Retorna:
        - JSON com:
            - status (str): Status do processamento
            - message (str): Mensagem de sucesso ou erro
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Dados JSON não fornecidos"}), 400
            
        video_url = data.get('videoUrl')
        site = data.get('site', 'none')
        
        if not video_url:
            return jsonify({"status": "error", "message": "URL do vídeo não fornecida"}), 400
            
        logger.info(f"Iniciando processamento do vídeo: {video_url}")
        
        # Definir timeout mais longo ou configurar assíncrono para processos longos
        # Processa o vídeo com tratamento de erros mais robusto
        try:
            result = await tratamento_videos(video_url, site)
        except Exception as e:
            logger.error(f"Erro na função tratamento_videos: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"Erro ao processar vídeo: {str(e)}"
            }), 500

        # Após processamento bem sucedido, deleta o vídeo original do bucket
        if result:
            try:
                # Verifica se é uma URL do GCS (gs://) ou HTTPS
                if video_url.startswith('gs://'):
                    video_path = video_url.replace('gs://', '').split('/')
                else:
                    # Converte URL HTTPS para formato GCS
                    video_path = video_url.replace('https://storage.googleapis.com/', '').split('/')
                
                bucket_name = video_path[0]
                blob_name = '/'.join(video_path[1:])
                
                logger.info(f"Deletando vídeo: bucket={bucket_name}, blob={blob_name}")
                
                # Inicializa cliente do Storage
                storage_client = storage.Client.from_service_account_json(get_credentials_path())
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                
                # Deleta o blob
                blob.delete()
                try:
                    clean_temp_directories()
                    logger.info("Diretórios temporários limpos com sucesso")
                except Exception as e:
                    logger.warning(f"Erro ao limpar diretórios temporários: {str(e)}")
                logger.info(f"Vídeo original deletado do bucket: {video_url}")
            except Exception as e:
                logger.warning(f"Erro ao deletar vídeo original do bucket: {str(e)}")
                # Continua execução mesmo se falhar a deleção
        
        if result:
            return jsonify({
                "status": "success",
                "message": "Vídeo processado com sucesso"
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Falha ao processar o vídeo"
            }), 500
            
    except Exception as e:
        logger.error(f"Erro global no endpoint /process: {str(e)}")
        # Garantir que sempre retorne uma resposta válida
        return jsonify({
            "status": "error",
            "message": f"Erro no servidor: {str(e)}"
        }), 500

@video_studio_bp.route("/list", methods=['GET'])
def list_videos():
    """
    Lista todos os vídeos do estúdio salvos no banco de dados.

    Retorna:
        - JSON com:
            - status (str): Status da operação
            - videos (list): Lista de vídeos encontrados
    """
    try:
        videos = consultar_videos_studio()
        return jsonify({
            "status": "success",
            "videos": videos
        }), 200
    except Exception as e:
        logger.error(f"Erro ao listar vídeos: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Erro ao buscar vídeos"
        }), 500