import asyncio
from flask import Blueprint, jsonify, request
from app.bd.bd import execute_query, inserir_contextualizacao
import logging
from app.config.ffmpeg import clean_temp_directories
from app.core.logger_config import setup_logger
from app.services.contextualizacao_service import process_single_nc
from app.utils.enviar_email import GoogleEmailSender
from ..services.cloud_tasks_service import CloudTasksService
import os

logger = setup_logger(__name__)

contextualizacao_bp = Blueprint('contextualizacao', __name__)
cloud_tasks_service = CloudTasksService()

def process_contextualizacao_background(data, user_emails):
    """
    Função que processa a contextualização em background e envia email ao finalizar
    """
    try:
        theme = data.get('theme')
        content_id = data.get('id')
        areaConhecimento = data.get('knowledge_area')
        tema_code = data.get('name')
        context_type = data.get('context_type')
        tema_code = ''.join(char for char in tema_code if char.isdigit())

        # Query para buscar por tema
        query = f"""
            SELECT JSON_CONTEUDO as conteudo, THEME as theme, nucleo, TITULO_NC, id, modulo 
            FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` A2
            WHERE 1=1
            and theme = '{theme}'
            and id = '{content_id}'
            and modulo is not null
            order by MODULO, NUCLEO
        """

        logger.info(f"Query: {query}")
        
        query_results = execute_query(query)
        results_list = list(query_results)
        
        resultados = []
        folder_link = None
        all_processed = True
        
        # Lista para armazenar documentos que falharam
        failed_docs = []
        # Lista para armazenar documentos processados com sucesso
        successful_docs = []

        for i, result in enumerate(results_list):
            try:
                conteudo = result.get('conteudo')
                theme = result.get('theme')
                nucleo = result.get('nucleo')
                titulo_atual = result.get('TITULO_NC')
                modulo = result.get('modulo')
                content_id = result.get('id')

                json_parametros = {
                    "id": content_id,
                    "theme": theme,
                    "areaConhecimento": areaConhecimento,
                    "tema_code": tema_code,
                    "context_type": context_type,
                    "nucleo": nucleo,
                    "modulo": modulo,
                    "titulo_atual": titulo_atual
                }

                if not conteudo or nucleo in ["conteudo_inicial.json", "estrutura.json"]:
                    continue

                logger.info(f"Processando JSON {i + 1} de {len(results_list)}")
                response = asyncio.run(process_single_nc(result['conteudo'], json_parametros=json_parametros))
                
                # Verificar se os documentos foram criados no Google Drive
                if not response.data or not response.folder_link:
                    logger.warning(f"Documento não foi salvo corretamente: Módulo {modulo}, Título {titulo_atual}")
                    failed_docs.append({
                        'modulo': modulo,
                        'titulo': titulo_atual,
                        'nucleo': nucleo,
                        'conteudo': conteudo,
                        'json_parametros': json_parametros
                    })
                    all_processed = False
                else:
                    folder_link = response.folder_link
                    successful_docs.append({
                        'modulo': modulo,
                        'titulo': titulo_atual,
                        'nucleo': nucleo
                    })
                
                clean_temp_directories()

            except Exception as e:
                logger.error(f"Erro ao processar JSON {i + 1}: {str(e)}", exc_info=True)
                resultados.append({"error": f"Erro ao processar JSON: {str(e)}"})
                failed_docs.append({
                    'modulo': modulo,
                    'titulo': titulo_atual,
                    'nucleo': nucleo,
                    'conteudo': conteudo,
                    'json_parametros': json_parametros
                })
                all_processed = False

        # Tentar reprocessar os documentos que falharam
        if failed_docs:
            logger.info(f"Tentando reprocessar {len(failed_docs)} documentos que falharam")
            for doc in failed_docs[:]:  # Usando uma cópia da lista para poder modificá-la
                try:
                    # Query específica para o documento que falhou
                    retry_query = f"""
                        SELECT JSON_CONTEUDO as conteudo, THEME as theme, nucleo, TITULO_NC, id, modulo 
                        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` A2
                        WHERE MODULO = '{doc['modulo']}'
                        AND TITULO_NC = '{doc['titulo']}'
                    """
                    retry_results = execute_query(retry_query)
                    retry_list = list(retry_results)

                    if retry_list:
                        retry_result = retry_list[0]
                        logger.info(f"Reprocessando documento: Módulo {doc['modulo']}, Título {doc['titulo']}")
                        response = asyncio.run(process_single_nc(retry_result['conteudo'], json_parametros=doc['json_parametros']))
                        
                        if response.data and response.folder_link:
                            logger.info(f"Reprocessamento bem sucedido para: Módulo {doc['modulo']}, Título {doc['titulo']}")
                            folder_link = response.folder_link
                            successful_docs.append({
                                'modulo': doc['modulo'],
                                'titulo': doc['titulo'],
                                'nucleo': doc['nucleo']
                            })
                            failed_docs.remove(doc)  # Remove da lista de falhas se foi bem sucedido
                        else:
                            logger.error(f"Reprocessamento falhou novamente para: Módulo {doc['modulo']}, Título {doc['titulo']}")
                    
                    clean_temp_directories()

                except Exception as e:
                    logger.error(f"Erro no reprocessamento: {str(e)}", exc_info=True)

        # Insere a contextualização no banco de dados se houver pelo menos um documento processado com sucesso
        if folder_link and successful_docs:
            # Faz apenas uma inserção, independente do número de emails
            inserir_contextualizacao(folder_link, theme, areaConhecimento)

        # Prepara e envia um único email consolidado
        sender = GoogleEmailSender()
        
        # Constrói o corpo do email
        email_body = f"""
        <h1>Relatório de Processamento de Contextualização</h1>
        <p><strong>Status:</strong> {"Concluído com ressalvas" if failed_docs else "Concluído com sucesso"}</p>
        
        <h2>Detalhes do Processamento:</h2>
        <ul>
            <li>Tema: {theme}</li>
            <li>Área de Conhecimento: {areaConhecimento}</li>
            <li>Total de documentos: {len(successful_docs) + len(failed_docs)}</li>
            <li>Documentos processados com sucesso: {len(successful_docs)}</li>
            <li>Documentos com falha: {len(failed_docs)}</li>
        </ul>
        """

        if folder_link:
            email_body += f"""
            <p><strong>Link da pasta:</strong> <a href="{folder_link}">{folder_link}</a></p>
            """

        if successful_docs:
            email_body += """
            <h2>Documentos Processados com Sucesso:</h2>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left;">Módulo</th>
                    <th style="padding: 8px; text-align: left;">Núcleo</th>
                    <th style="padding: 8px; text-align: left;">Título</th>
                </tr>
            """
            for doc in successful_docs:
                email_body += f"""
                <tr>
                    <td style="padding: 8px;">{doc['modulo']}</td>
                    <td style="padding: 8px;">{doc['nucleo']}</td>
                    <td style="padding: 8px;">{doc['titulo']}</td>
                </tr>
                """
            email_body += "</table>"

        if failed_docs:
            email_body += """
            <h2 style="color: #d9534f;">Documentos que Falharam:</h2>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px; text-align: left;">Módulo</th>
                    <th style="padding: 8px; text-align: left;">Núcleo</th>
                    <th style="padding: 8px; text-align: left;">Título</th>
                </tr>
            """
            for doc in failed_docs:
                email_body += f"""
                <tr>
                    <td style="padding: 8px;">{doc['modulo']}</td>
                    <td style="padding: 8px;">{doc['nucleo']}</td>
                    <td style="padding: 8px;">{doc['titulo']}</td>
                </tr>
                """
            email_body += "</table>"

        is_local = os.getenv('ENVIRONMENT', 'local') == 'local'
        if not is_local:
            subject_email = f"Relatório de Contextualização - {theme}"
        else:
            subject_email = f"Relatório de Contextualização - {theme}"
            
        # Envia o email consolidado para todos os destinatários
        for user_email in user_emails:
            sender.send_email(
                to_email=user_email,
                subject=subject_email,
                body=email_body,
                is_html=True
            )

    except Exception as e:
        logger.error(f"Erro no processamento em background: {str(e)}", exc_info=True)
        # Envia email de erro geral
        try:
            sender = GoogleEmailSender()
            error_body = f"""
            <h1>Erro no Processamento de Contextualização</h1>
            <p>Ocorreu um erro durante o processamento da sua contextualização.</p>
            <p><strong>Detalhes do erro:</strong> {str(e)}</p>
            """
            for user_email in user_emails:
                sender.send_email(
                    to_email=user_email,
                    subject=f"Erro na Contextualização - {theme}",
                    body=error_body,
                    is_html=True
                )
        except Exception as email_error:
            logger.error(f"Erro ao enviar email de erro: {str(email_error)}", exc_info=True)
    
@contextualizacao_bp.route("/generate", methods=['POST'])
def create_contextualizacao():
    """
    Inicia o processamento da contextualização
    """
    try:
        data = request.get_json()
        logger.info(f"Recebida requisição para contextualização com dados: {data}")
        
        user_emails = data.get('user_emails', ['rafael@autenticare.com.br','jones@autenticare.com.br'])
        
        if not user_emails:
            return jsonify({"error": "Lista de e-mails não fornecida"}), 400

        # Garante que user_emails seja uma lista
        if isinstance(user_emails, str):
            user_emails = [user_emails]

        # Verifica se está em ambiente local
        is_local = os.getenv('ENVIRONMENT', 'local') == 'local'
        logger.info(f"Ambiente atual: {'local' if is_local else 'produção'}")
        logger.info(f"Variáveis de ambiente:")
        logger.info(f"- GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
        logger.info(f"- CLOUD_TASKS_QUEUE: {os.getenv('CLOUD_TASKS_QUEUE')}")
        logger.info(f"- CLOUD_TASKS_LOCATION: {os.getenv('CLOUD_TASKS_LOCATION')}")
        logger.info(f"- SERVICE_URL: {os.getenv('SERVICE_URL')}")
        logger.info(f"- CLOUD_TASKS_SERVICE_ACCOUNT: {os.getenv('CLOUD_TASKS_SERVICE_ACCOUNT')}")
        
        if is_local:
            logger.info("Ambiente local detectado. Iniciando processamento direto...")
            # Em ambiente local, processa diretamente
            process_contextualizacao_background(data, user_emails)
            return jsonify({
                "message": "Processamento iniciado com sucesso (modo local)",
                "status": "processing",
                "details": "Você receberá um email quando o processamento for concluído"
            }), 202
        else:
            logger.info("Ambiente de produção detectado. Iniciando processamento com Cloud Tasks...")

            # Em produção, usa Cloud Tasks
            task_result = cloud_tasks_service.create_contextualization_task(data, user_emails)
            
            logger.info(f"Resultado da criação da task: {task_result}")
            
            if not task_result['success']:
                logger.error(f"Falha ao criar task: {task_result['error']}")
                raise Exception(task_result['error'])

            response = jsonify({
                "message": "Processamento iniciado com sucesso",
                "status": "processing",
                "details": "Você receberá um email quando o processamento for concluído",
                "task_name": task_result['task_name']
            })
            
            # Força o envio imediato da resposta
            response.direct_passthrough = False
            return response, 202

    except Exception as e:
        logger.error(f"Erro ao iniciar processamento: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@contextualizacao_bp.route('/list', methods=['GET'])
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
        SELECT THEME_ORIGIN, THEME_DESTINY, URL, CREATE_DATE
        FROM `conteudo-autenticare.poc_dataset.CONTEXTUALIZACAO`
        """

        # Executa a query
        result = execute_query(query)

        if not result or len(result) == 0:
            logger.error("Nenhuma contextualização encontrada")

        # Formata o resultado
        contextualizacoes = []
        for row in result:
            contextualizacoes.append({
                'theme_origin': row['THEME_ORIGIN'],
                'theme_destiny': row['THEME_DESTINY'],
                'url': row['URL'],
                'create_date': row['CREATE_DATE']
            })
            
        query_areas = """
        SELECT nome
        FROM `conteudo-autenticare.poc_dataset.AREA_CONHECIMENTO`
        """

        result_areas = execute_query(query_areas)
        logger.info(f"Encontradas {len(result_areas)} áreas de conhecimento")

        areas = []
        for row in result_areas:
            areas.append({
                'nome': row['nome']
            })

        # Criar objeto JSON estruturado
        response_data = {
            "contextualizacoes": contextualizacoes,
            "areas_conhecimento": areas
        }

        logger.info(f"Encontradas {len(contextualizacoes)} contextualizações")
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Erro ao buscar contextualizações: {str(e)}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@contextualizacao_bp.route("/process", methods=['POST'])
def process_contextualizacao():
    """
    Endpoint que processa a contextualização quando chamado pelo Cloud Tasks
    """
    try:
        task_data = request.get_json()
        data = task_data['data']
        user_emails = task_data['user_emails']
        
        # Executa o processamento
        process_contextualizacao_background(data, user_emails)
        
        return jsonify({
            "message": "Processamento concluído com sucesso"
        }), 200
        
    except Exception as e:
        logger.error(f"Erro no processamento da task: {str(e)}", exc_info=True)
        # Retorna 500 para que o Cloud Tasks tente novamente
        return jsonify({"error": str(e)}), 500