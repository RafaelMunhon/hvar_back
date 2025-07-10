from flask import Blueprint, jsonify, send_file, request
from app.bd.bd import consultar_nome_arquivo, execute_query
from app.core.logger_config import setup_logger
import json
import os
from io import BytesIO
from uuid import UUID

logger = setup_logger(__name__)

# Mudando o nome do Blueprint para algo mais genérico
app_bp = Blueprint('front_app', __name__)

@app_bp.route("/get_data", methods=['GET'])  # Mudando a rota para incluir get_data
def get_data():
    logger.info("Recebendo solicitação para /api/get_data")
    
    # Obter parâmetros de filtro da query string
    id_filter = request.args.get('id')
    name_filter = request.args.get('name')
    titulo_nc_filter = request.args.get('titulo_nc')
    
    logger.info(f"Parâmetros de filtro recebidos: ID={id_filter}, Nome={name_filter}, Título NC={titulo_nc_filter}")
    
    # Passar os parâmetros para a função de consulta
    rows = consultar_nome_arquivo(id=id_filter, name=name_filter, titulo_nc=titulo_nc_filter)
    
    if not rows:
        return jsonify({"error": "Nenhum dado encontrado ou erro na consulta"}), 500
    
    return jsonify(rows)

@app_bp.route('/download/<uuid:id>/<path:titulo_nc>', methods=['GET'])
def download_json(id, titulo_nc):
    logger.info(f"Recebendo solicitação de download para ID: {id}, Título: {titulo_nc}")
    try:
        # Converte UUID para string para usar na query
        id_str = str(id)
        
        # Query para buscar o JSON no banco
        query = """
        SELECT a2.JSON_CONTEUDO as JSON, a2.TITULO_NC, a1.NAME
        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS` a1
        INNER JOIN `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2 
        ON a1.ID = a2.ID
        WHERE a1.ID = @id
        AND a2.TITULO_NC = @titulo_nc
        """
        
        params = {
            'id': id_str,
            'titulo_nc': titulo_nc
        }
        
        logger.info(f"Buscando arquivo com ID: {id_str} e Título: {titulo_nc}")
        
        # Executa a query
        result = execute_query(query, params)
        
        if not result or len(result) == 0:
            logger.error(f"Arquivo não encontrado para ID: {id_str} e Título: {titulo_nc}")
            return jsonify({'error': 'Arquivo não encontrado'}), 404
            
        # Pega o primeiro resultado
        json_data = result[0]['JSON']
        titulo = result[0]['TITULO_NC']
        name = result[0]['NAME']
        
        logger.info(f"Arquivo encontrado: {name}_{titulo}.json")
        logger.info(f"json_data: {json_data}")
        
        # Cria um arquivo temporário em memória
        json_bytes = json.dumps(json_data, ensure_ascii=False, indent=2).encode('utf-8')
        mem_file = BytesIO(json_bytes)
        
        # Define o nome do arquivo
        filename = f"{name}_{titulo}.json"
        
        # Envia o arquivo
        return send_file(
            mem_file,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        logger.error(f"Erro ao fazer download do JSON: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500