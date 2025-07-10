from app.config.gemini_client import get_gemini_manager
from flask import Blueprint, jsonify, request
from app.bd.bd import execute_query
from app.core.logger_config import setup_logger
import json

logger = setup_logger(__name__)
mental_map_bp = Blueprint('mental_map', __name__)

def create_mental_map_prompt(titulo_nc, json_conteudo_str):
    """
    Cria o prompt para a IA gerar o mapa mental em Markdown.
    """
    prompt = f"""
Com base no seguinte conteúdo JSON, gere um mapa mental em formato Markdown.
O nó central deve ser o 'TITULO_NC' fornecido abaixo.
Os tópicos principais devem ser representados por cabeçalhos de nível 1 (ex: # Tópico Principal).
Subtópicos devem ser listas aninhadas (ex: - Subtópico) ou cabeçalhos de níveis inferiores (## Subtópico de Nível 2).
Estruture a informação de forma clara e hierárquica.
Evite introduções ou conclusões fora do mapa mental em si.

TITULO_NC: "{titulo_nc}"

CONTEÚDO JSON:
{json_conteudo_str}

Responda APENAS com o mapa mental em formato Markdown.
"""
    return prompt

@mental_map_bp.route("/generate", methods=['POST'])
async def generate_mental_map(): # Marcado como async se generate_content for assíncrono
    logger.info("Recebendo solicitação para /api/mental_map/generate")
    try:
        data = request.get_json()
        if not data:
            logger.error("Nenhum dado JSON recebido na requisição.")
            return jsonify({"error": "Nenhum dado JSON recebido"}), 400

        file_id = data.get('id')
        titulo_nc = data.get('titulo_nc')

        if not file_id or not titulo_nc:
            logger.error(f"Parâmetros ausentes: ID={file_id}, Titulo NC={titulo_nc}")
            return jsonify({"error": "Parâmetros 'id' e 'titulo_nc' são obrigatórios"}), 400

        logger.info(f"Buscando conteúdo para ID: {file_id} e Título NC: {titulo_nc}")

        query = """
        SELECT JSON_CONTEUDO
        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO`
        WHERE ID = @id AND TITULO_NC = @titulo_nc
        LIMIT 1
        """
        params = {
            'id': file_id,
            'titulo_nc': titulo_nc
        }

        result_db = execute_query(query, params) # Renomeado para evitar conflito

        if not result_db or len(result_db) == 0:
            logger.error(f"Nenhum conteúdo encontrado para ID: {file_id} e Título NC: {titulo_nc}")
            return jsonify({"error": "Conteúdo não encontrado no banco de dados"}), 404

        json_conteudo = result_db[0].get('JSON_CONTEUDO')

        if not json_conteudo:
            logger.error(f"Campo JSON_CONTEUDO está vazio para ID: {file_id} e Título NC: {titulo_nc}")
            return jsonify({"error": "Conteúdo JSON está vazio no banco de dados"}), 500

        json_conteudo_str_for_prompt = json.dumps(json_conteudo, indent=2, ensure_ascii=False)

        
        prompt_ia = create_mental_map_prompt(titulo_nc, json_conteudo_str_for_prompt)
        logger.info(f"Prompt enviado para IA: {prompt_ia[:500]}...")

        manager= get_gemini_manager()
        markdown_content_response = await manager.generate_content(prompt_ia, model="gemini-2.5-flash-preview-04-17")

        if not markdown_content_response:
            logger.error("A IA não retornou conteúdo para o mapa mental.")
            return jsonify({"error": "Falha ao gerar mapa mental pela IA: resposta vazia"}), 500

        # A resposta da IA pode vir com ```markdown no início e ``` no fim. Vamos tentar remover.
        cleaned_markdown = markdown_content_response.strip()
        if cleaned_markdown.startswith("```markdown"):
            cleaned_markdown = cleaned_markdown[len("```markdown"):].strip()
        if cleaned_markdown.endswith("```"):
            cleaned_markdown = cleaned_markdown[:-len("```")].strip()
        
        logger.info(f"Markdown gerado pela IA (após limpeza): {cleaned_markdown[:500]}...")
        
        return jsonify({
            "message": "Mapa mental em Markdown gerado com sucesso.",
            "markdown_content": cleaned_markdown,
            "id_recebido": file_id,
            "titulo_nc_recebido": titulo_nc
        }), 200

    except Exception as e:
        logger.error(f"Erro ao gerar mapa mental: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro interno do servidor ao gerar mapa mental: {str(e)}"}), 500