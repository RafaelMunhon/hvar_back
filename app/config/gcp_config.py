import os
from app.core.logger_config import setup_logger
from google.cloud import bigquery
from google.oauth2 import service_account

logger = setup_logger(__name__)

def initialize_gcp():
    """Initialize GCP configuration and set credentials"""
    try:
        credentials_path = get_credentials_path()
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        logger.info(f"GCP credentials configured successfully from: {credentials_path}")
    except Exception as e:
        logger.error(f"Failed to initialize GCP: {str(e)}")
        raise

def get_credentials_path():
    """Retorna o caminho correto das credenciais do GCP"""
    # Lista de possíveis localizações do arquivo de credenciais
    possible_paths = [
        os.path.join(os.getcwd(), 'conteudo-autenticare-d2aaae9aeffe.json'),
        os.path.join(os.getcwd(), 'app', 'conteudo-autenticare-d2aaae9aeffe.json'),
        os.path.join(os.getcwd(), 'conteudo-autenticare-d2aaae9aeffe.json'),
        os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    ]
    
    # Log dos caminhos possíveis
    logger.info("Procurando arquivo de credenciais em:")
    for path in possible_paths:
        logger.info(f"- {path}")
        if os.path.isfile(path):
            logger.info(f"Arquivo de credenciais encontrado em: {path}")
            return path
            
    # Se não encontrar, tenta usar variável de ambiente
    env_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if env_path:
        logger.info(f"Usando caminho das credenciais da variável de ambiente: {env_path}")
        return env_path
            
    raise FileNotFoundError("Arquivo de credenciais GCP não encontrado em nenhum local esperado")

def get_bigquery_client():
    # Caminho para o arquivo de credenciais
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'conteudo-autenticare-d2aaae9aeffe.json')
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        
        client = bigquery.Client(
            credentials=credentials,
            project=credentials.project_id
        )
        return client
    except Exception as e:
        print(f"Erro ao configurar cliente BigQuery: {str(e)}")
        raise 