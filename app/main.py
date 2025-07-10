import logging
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from app.api.video import video_bp
from app.api.audiobook import audiobook_bp
from app.api.audiovideo import audiovideo_bp
from app.api.process import process_bp
from app.api.front_app import app_bp
from app.api.import_file import import_file_bp
from app.api.video_pexel import video_pexel_bp
from app.api.video_studio import video_studio_bp
from app.api.audioqa import audioqa_bp
from app.api.microlearning import microlearning_bp
from app.api.podcast import podcast_bp
from app.api.contextualizacao import contextualizacao_bp
from app.config.gcp_config import get_credentials_path, initialize_gcp
from app.api.mental_map import mental_map_bp # Nova importação
from dotenv import load_dotenv
from app.core.config_manager import get_config_manager
from app.core.logger_config import setup_logger
from app.core.console_interceptor import start_console_interception, stop_console_interception
from app.config.config import initialize_config
from app.api.metrics import metrics_bp
import atexit

# Configurar o logger primeiro
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuração inicial
logger.info("Iniciando configuração da aplicação...")

# Inicia interceptação do console
start_console_interception()
logger.info("Interceptação do console iniciada")

# Registra função para parar interceptação ao encerrar
atexit.register(stop_console_interception)

# Inicializa configurações
initialize_config()
initialize_gcp()

def initialize_environment():
    """Initialize environment variables and configuration"""
    # Carregar variáveis de ambiente do arquivo .env
    logger.info("Loading environment variables...")
    load_dotenv(override=True)  # Força o recarregamento

    # Log environment variables (masked)
    env_vars = ['HEYGEN_API_KEY', 'GCP_PROJECT_ID', 'BUCKET_NAME']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            masked = f"{value[:5]}...{value[-5:]}" if len(value) > 10 else "***"
            logger.info(f"Environment variable {var} loaded: {masked}")
        else:
            logger.warning(f"Environment variable {var} not found")

    # Initialize configuration manager first to get default values
    config_manager = get_config_manager()
    api_config = config_manager.get_api_config()

    # Configurar credenciais GCP usando o valor do config_manager
    try:
        credentials_path = os.path.join(os.getcwd(), api_config.google_credentials)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        logger.info(f"Using Google credentials from: {credentials_path}")
    except Exception as e:
        logger.error(f"AVISO: {str(e)}")

    return config_manager

# Initialize environment and configuration
config_manager = initialize_environment()

app = Flask(__name__)
CORS(app)  # Permite acesso de qualquer origem

# Registrar blueprints
app.register_blueprint(video_bp, url_prefix='/api/video')
app.register_blueprint(audiobook_bp, url_prefix='/api/audio')
app.register_blueprint(audiovideo_bp, url_prefix='/api')
app.register_blueprint(process_bp, url_prefix='/api/process')
app.register_blueprint(app_bp, url_prefix='/api') # front_app é registrado aqui
app.register_blueprint(import_file_bp, url_prefix='/api/import')
app.register_blueprint(video_pexel_bp, url_prefix='/api/video_pexel')
app.register_blueprint(video_studio_bp, url_prefix='/api/video_studio')
app.register_blueprint(contextualizacao_bp, url_prefix='/api/context')
app.register_blueprint(mental_map_bp, url_prefix='/api/mental_map') # Novo registro

app.register_blueprint(audioqa_bp)
app.register_blueprint(microlearning_bp)
app.register_blueprint(podcast_bp)
app.register_blueprint(metrics_bp, url_prefix='/api')

logger.info("Aplicação configurada e pronta para uso")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False) # Ajustado para Cloud Run
