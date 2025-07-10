from flask import Blueprint, request, jsonify
import logging
from app.services.podcast_service import podcast
from app.bd.bd import execute_query

podcast_bp = Blueprint('podcast', __name__, url_prefix='/api/podcast')

@podcast_bp.route("/generate", methods=['POST'])
def create_podcast():
    logging.info("Recebendo requisição para gerar Podcast")

    if not request.is_json:
        return jsonify({"error": "Requisição deve conter JSON"}), 400

    try:
        data = request.get_json()
        mode = data.get('mode')

        if mode == 'tema':
            theme = data.get('theme')
            content_id = data.get('id')

            logging.info(f"Recebendo requisição para gerar Podcast por tema: {theme}")
            if not theme or not content_id:
                return jsonify({"error": "Theme e ID não fornecidos"}), 400

            # Query para buscar por tema
            query = f"""
                SELECT JSON_CONTEUDO as conteudo, THEME as theme
                FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2
                WHERE 1=1
                and a2.ID = '{str(content_id).strip()}'
                and a2.THEME like '%{str(theme).strip()}%'
                limit 1
            """
        elif mode == 'titulo':
            titulo_nc = data.get('titulo_nc')
            content_id = data.get('id')

            logging.info(f"Recebendo requisição para gerar Podcast por título: {titulo_nc}")
            if not titulo_nc or not content_id:
                return jsonify({"error": "Título NC e ID não fornecidos"}), 400

            # Query para buscar por título
            query = f"""
                SELECT JSON_CONTEUDO as conteudo, THEME as theme
                FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2
                WHERE 1=1
                and a2.ID = '{str(content_id).strip()}'
                and a2.TITULO_NC like '%{str(titulo_nc).strip()}%'
                limit 1
            """
        else:
            return jsonify({"error": "Mode inválido - deve ser 'tema' ou 'titulo'"}), 400

        logging.info(f"Executando query: {query}")
        result = execute_query(query)
        logging.info(f"Resultado da query: {result}")

        if not result or len(result) == 0:
            return jsonify({'error': 'Arquivo não encontrado'}), 404

        # Pega o conteúdo e theme
        conteudo = result[0].get('conteudo', {})
        theme = result[0].get('theme')

        if not conteudo:
            return jsonify({'error': 'Conteúdo vazio'}), 400
        if not theme:
            return jsonify({'error': 'Theme não encontrado'}), 400

        # Adiciona os paths necessários para salvar no GCS
        conteudo['relative_path'] = f"audios/"
        conteudo['output_dir'] = "podcasts"
        conteudo['content_id'] = content_id  # Passa o content_id para o serviço
        conteudo['theme'] = theme

        try:
            resultado = podcast(conteudo, content_id, theme)
            return jsonify(resultado), 200
        except Exception as e:
            logging.error(f"Erro ao processar JSON: {str(e)}")
            return jsonify({"error": "Erro ao processar o JSON"}), 400

    except Exception as e:
        logging.error(f"Erro ao processar requisição: {str(e)}")
        return jsonify({"error": "Erro ao processar a requisição"}), 500
