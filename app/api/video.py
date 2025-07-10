from flask import Blueprint, jsonify, request
from app.bd.bd import execute_query
from app.config.ffmpeg import clean_temp_directories
from app.services.video_service import gerar_video_template_3_roteiro
import logging
from app.core.logger_config import setup_logger

logger = setup_logger(__name__)

video_bp = Blueprint('video', __name__)
    
@video_bp.route("/generate_template", methods=['POST'])
async def create_video_template_roteiro():
    """
    Gera um vídeo baseado em um template pré-definido.

    Recebe um JSON com os seguintes campos:
    - titulo_nc: Título do conteúdo
    - id: Identificador único do vídeo
    - busca_imagem: Lista de imagens para overlay
    - avatar_number: Número do avatar a ser usado
    - theme: Tema visual a ser aplicado

    Retorna:
    - JSON com o URL do vídeo gerado
    - 200: Se o vídeo foi gerado com sucesso
    - 400: Se o JSON de entrada estiver vazio ou inválido
    """
    logging.info("Recebendo requisição para gerar vídeo por template")

    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON de entrada está vazio ou inválido"}), 400
        
        # Validar campos obrigatórios
        required_fields = ['titulo_nc', 'id', 'busca_imagem', 'avatar_number']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Campo obrigatório '{field}' não encontrado"}), 400
                
        titulo_nc = data['titulo_nc']
        id = data['id']
        theme = data['theme']
        avatar_number = data['avatar_number']
        busca_imagem = data['busca_imagem']

        logging.info(f"titulo_nc: {titulo_nc}")
        logging.info(f"id: {id}")
        logging.info(f"avatar_number: {avatar_number}")
        logging.info(f"busca_imagem: {busca_imagem}")
        
        # Buscar dados do JSON no banco
        query = f"""
        SELECT JSON_CONTEUDO as conteudo
        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2  
        WHERE 1=1 
        and a2.ID = '{str(id).strip()}'
        and a2.TITULO_NC like '%{str(titulo_nc).strip()}%'
        limit 1
        """
        
        #logging.info(f"Executando query: {query}")
        
        result = execute_query(query)
        
        if not result or len(result) == 0:
            return jsonify({'error': 'Arquivo não encontrado'}), 404

        # O JSON já vem como objeto Python do BigQuery
        json_object = result[0]['conteudo']
        #logging.info(f"json_object: {json_object}")
        
    except Exception as e:
        logging.error(f"Erro ao obter JSON: {e}")
        return jsonify({"error": "Erro ao processar o JSON"}), 400

    # Chamar a função para gerar o vídeo
    try:
        video_url = await gerar_video_template_3_roteiro(json_object, busca_imagem, avatar_number, id, theme, titulo_nc)
        if video_url:
            clean_temp_directories()
            return jsonify({'video_url': video_url}), 200
        else:
            return jsonify({'error': 'Falha na geração do vídeo'}), 500
    except Exception as e:
        logging.error(f"Erro ao gerar vídeo: {e}")
        return jsonify({"error": "Erro interno ao gerar vídeo"}), 500


@video_bp.route('/list', methods=['GET'])
def get_videos():
    """
    Busca todos os vídeos disponíveis no banco de dados.

    Retorna:
    - JSON com os vídeos encontrados
    - 200: Se os vídeos foram encontrados com sucesso
    - 404: Se nenhum vídeo for encontrado
    - 500: Se ocorrer um erro ao buscar os vídeos
    """
    try:
        logger.info("Buscando todos os vídeos disponíveis")

        # Query para buscar todos os vídeos no banco
        query = """
        SELECT TITULO_NC, URL, CREATE_DATE 
        FROM `conteudo-autenticare.poc_dataset.VIDEOS` where TYPE_VIDEO = 'HEYGEN'
        """

        # Executa a query
        result = execute_query(query)

        if not result or len(result) == 0:
            logger.error("Nenhum vídeo encontrado")
            return jsonify({'error': 'Nenhum vídeo encontrado'}), 404

        # Formata o resultado
        videos = []
        for row in result:
            videos.append({
                'titulo': row['TITULO_NC'],
                'url': row['URL'],
                'data_criacao': row['CREATE_DATE']
            })

        logger.info(f"Encontrados {len(videos)} vídeos")
        return jsonify(videos), 200

    except Exception as e:
        logger.error(f"Erro ao buscar vídeos: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500