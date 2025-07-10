from flask import Blueprint, jsonify, request 
import logging
import os
import zipfile
import json
from app.bd.bd import execute_query
from app.services.audiobook_service import audiobook
import tempfile
import shutil
from google.cloud import storage

audiobook_bp = Blueprint('audiobook', __name__)

BUCKET_NAME = "yduqs-audio-web"

# Verificação das credenciais
credential_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if credential_path:
    logging.info(f"Credenciais do GCS encontradas em: ") # Removido o split
else:
    logging.error("Variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não definida!")


@audiobook_bp.route("/generate", methods=['POST'])
async def create_audiobook():
    logging.info("Recebendo requisição para gerar audiobook")

    if not request.is_json:
        return jsonify({"error": "Requisição deve conter JSON"}), 400

    try:
        data = request.get_json()
        mode = data.get('mode')

        if mode == 'tema':
            theme = data.get('theme')
            content_id = data.get('id')

            logging.info(f"Recebendo requisição para gerar audiobook por tema:  com ID: ")
            if not theme or not content_id:
                return jsonify({"error": "Theme ou ID não fornecido"}), 400

            # Query para buscar por tema
            query = f"""
                SELECT JSON_CONTEUDO as conteudo, THEME as theme, nucleo, TITULO_NC, id, modulo
                FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2
                WHERE 1=1
                and a2.ID like '%{str(content_id).strip()}%'
                and a2.THEME like '%{str(theme).strip()}%'
                order by a2.modulo, a2.nucleo
            """

            logging.info(f"Executando query: ")
            query_results = execute_query(query)
            logging.info(f"Número de resultados encontrados: {len(query_results) if query_results else 0}")

            # Converte para lista para poder acessar índices
            results_list = list(query_results)

            resultados = []
            for i, result in enumerate(results_list):
                try:
                    logging.info(f"Processando resultado {i + 1} de {len(results_list)}")
                    conteudo = result.get('conteudo', {})
                    theme = result.get('theme')
                    nucleo = result.get('nucleo')
                    titulo_atual = result.get('TITULO_NC')
                    modulo = result.get('modulo')
                    content_id = result.get('id')

                    logging.info(f"Processando núcleo: , título: ")

                    if not conteudo:
                        logging.error("Conteúdo vazio no resultado da query")
                        continue

                    # Verifica o núcleo do conteúdo
                    if nucleo == "Estrutura do Tema.json":
                        logging.info("Pulando 'Estrutura do Tema.json'")
                        continue

                    # Define flag para conteúdo inicial
                    is_conteudo_inicial = nucleo == "conteudo_inicial.json"

                    # Pega o título do próximo item, se existir
                    next_titulo_nc = None
                    if i < len(results_list) - 1:
                        next_titulo_nc = results_list[i + 1].get('TITULO_NC')
                        logging.info(f"Próximo título será: ")

                    logging.info(f"Iniciando geração do audiobook para ")
                    try:

                        resultado = await audiobook(
                            conteudo,
                            relative_path=f"audios/",
                            output_dir=f"audiobooks",
                            next_titulo_nc=next_titulo_nc,
                            is_conteudo_inicial=is_conteudo_inicial,
                            titulo_atual=titulo_atual, modulo=modulo, nucleo=nucleo, content_id=content_id, theme=theme
                        )
                        logging.info(f"Audiobook gerado com sucesso para ")
                        resultados.append(resultado)
                    except Exception as e_audiobook:
                        logging.error(f"Erro ao gerar audiobook para : {str(e_audiobook)}", exc_info=True)
                        resultados.append({"error": f"Erro ao gerar audiobook: {str(e_audiobook)}"})

                except Exception as e:
                    logging.error(f"Erro ao processar JSON {i + 1}: {str(e)}", exc_info=True)
                    resultados.append({"error": f"Erro ao processar JSON: {str(e)}"})
                continue

            logging.info(f"Conteúdo de 'resultados' ANTES do jsonify: {resultados}") # Log para ver o CONTEÚDO de 'resultados'
            logging.info(f"Tipo de 'resultados': {type(resultados)}") # Log para ver o TIPO de 'resultados' (lista, etc.)
            return jsonify({"message": "Audiobooks gerados sequencialmente", "results": resultados}), 200

        elif mode == 'titulo':
            logging.info(f"Recebendo requisição para gerar audiobook por título")
            titulo_nc = data.get('titulo_nc')
            content_id = data.get('id')
            nucleo = data.get('nucleo')
            modulo = data.get('modulo')
            logging.info(f"Tipo de 'resultados' do modulo e nucleo {modulo} {nucleo} ")

            if not titulo_nc or not content_id:
                return jsonify({"error": "Título NC ou ID não fornecido"}), 400

            # Query para buscar por título (atual)
            query_atual = f"""
                SELECT JSON_CONTEUDO as conteudo, THEME as theme, nucleo, TITULO_NC, id, modulo, TITULO_NC_PROXIMA_AULA
                FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2
                WHERE 1=1
                and a2.ID = '{str(content_id).strip()}'
                and a2.TITULO_NC like '%{str(titulo_nc).strip()}%'
                and a2.nucleo like '%{str(nucleo).strip()}%'
                AND (a2.modulo LIKE '%{str(modulo).strip()}%' OR a2.modulo IS NULL AND '{str(modulo).strip()}' = 'None')
                limit 1
            """

            logging.info(f"Executando query para o título atual: ")
            result_atual = execute_query(query_atual)
            logging.info(f"Resultado da query para o título atual: ")

            if not result_atual or len(result_atual) == 0:
                return jsonify({'error': 'Arquivo não encontrado'}), 404

            # Pega o conteúdo e theme do resultado atual
            conteudo = result_atual[0].get('conteudo', {})
            theme = result_atual[0].get('theme')
            titulo_atual = result_atual[0].get('TITULO_NC')
            modulo = result_atual[0].get('modulo')
            nucleo = result_atual[0].get('nucleo')
            content_id = data.get('id')
            next_titulo_nc = result_atual[0].get('TITULO_NC_PROXIMA_AULA')


            if not conteudo:
                return jsonify({'error': 'Conteúdo vazio'}), 400
            if not theme:
                return jsonify({'error': 'Theme não encontrado'}), 400

            if nucleo == "Estrutura do Tema.json":
                logging.info("Pulando 'Estrutura do Tema.json'")
                return jsonify({'error': 'esse tema não pode ser gerado'}), 400

            # Define flag para conteúdo inicial
            is_conteudo_inicial = nucleo == "conteudo_inicial.json"

            try:
                resultado = await audiobook(conteudo,
                                      relative_path=f"audios/",
                                      output_dir="audiobooks",
                                      next_titulo_nc=next_titulo_nc, # Passa o next_titulo_nc para audiobook()
                                      is_conteudo_inicial=is_conteudo_inicial,
                                      titulo_atual=titulo_atual,
                                      modulo=modulo,
                                      nucleo=nucleo,
                                      content_id=content_id,
                                      theme=theme)
                return jsonify(resultado), 200
            except Exception as e:
                logging.error(f"Erro ao processar JSON: {str(e)}", exc_info=True)
                return jsonify({"error": "Erro ao processar o JSON"}), 400

        else:
            return jsonify({"error": "Mode inválido - deve ser 'tema' ou 'titulo'"}), 400

    except Exception as e:
        logging.error(f"Erro ao processar requisição: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar a requisição"}), 500


@audiobook_bp.route('/list', methods=['GET'])
def list_files():
    try:
        query = """
            SELECT
                ID,
                URL,
                TIPO_AUDIO,
                CREATE_DATE,
                THEME,
                TITULO_NC
            FROM `conteudo-autenticare.poc_dataset.AUDIOS`
        """

        results = execute_query(query)

        logging.info(f"Resultado da query: ")

        file_list = []
        for row in results:
            file_list.append({
                "id": row['ID'],
                "url": row['URL'],
                "tipo_audio": row['TIPO_AUDIO'],
                "create_date": row['CREATE_DATE'].isoformat() if row['CREATE_DATE'] else None,
                "theme": row['THEME'],
                "titulo_nc": row['TITULO_NC']
            })

        logging.info(f"Lista de arquivos montada: ")

        response = jsonify({"files": file_list})
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'  # Disable caching
        response.headers['Pragma'] = 'no-cache'  # for older browsers
        response.headers['Expires'] = '0'  # for older browsers

        return response, 200
    except Exception as e:
        logging.error(f"Erro ao listar arquivos do banco de dados: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar arquivos do banco de dados"}), 500


@audiobook_bp.route('/delete', methods=['DELETE'])
def delete_audios():
    audio_ids = request.get_json()  # Espera receber uma lista de IDs no corpo da requisição

    if not audio_ids or not isinstance(audio_ids, list):
        return jsonify({"error": "IDs de áudio inválidos"}), 400

    try:
        # Construir a query para deletar múltiplos áudios
        query = f"""
            DELETE FROM `conteudo-autenticare.poc_dataset.AUDIOS`
            WHERE ID IN ({', '.join([f"'{audio_id}'" for audio_id in audio_ids])})
        """
        execute_query(query)  # Execute a query para deletar os áudios do banco de dados

        logging.info(f"Audiobooks com IDs  deletados com sucesso do banco de dados.")
        return jsonify({"message": f"Audiobooks com IDs  deletados com sucesso."}), 200
    except Exception as e:
        logging.error(f"Erro ao deletar audiobooks com IDs  do banco de dados: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao deletar audiobooks do banco de dados"}), 500