import json
import logging
from flask import Blueprint, jsonify, request, current_app
import os
from app.core.logger_config import setup_logger
from app.bd.bd import inserir_arquivos_conteudo, inserir_bigquery, verificar_arquivo_existe, atualizar_arquivo, atualizar_conteudo_completo
from unidecode import unidecode

logger = setup_logger(__name__)
import_file_bp = Blueprint('import_file', __name__)


# Rota relativa pelo blueprint
@import_file_bp.route("/check_file_exists", methods=['GET'])
# Rota absoluta para compatibilidade com o código anterior
@import_file_bp.route("/api/check_file_exists", methods=['GET'])
def check_file_exists():
    """Verifica se um arquivo já existe no banco de dados"""
    try:
        file_name = request.args.get('name')
        logger.info(f"Verificando existência do arquivo: {file_name}")
        
        if not file_name:
            return jsonify({"error": "Nome do arquivo não fornecido"}), 400
            
        # Verifica se o arquivo existe
        result = verificar_arquivo_existe(file_name)
        
        if result:
            logger.info(f"Arquivo encontrado: ID={result.get('ID')}, THEME={result.get('THEME')}")
            return jsonify({
                "exists": True,
                "id": result.get("ID"),
                "theme": result.get("THEME")
            }), 200
        else:
            logger.info(f"Arquivo não encontrado: {file_name}")
            return jsonify({"exists": False}), 200
            
    except Exception as e:
        logger.error(f"Erro ao verificar arquivo: {str(e)}")
        return jsonify({"error": f"Erro ao verificar arquivo: {str(e)}"}), 500


@import_file_bp.route("", methods=['POST'])
def import_json_to_db():
    try:
        # Verifica se o arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        file = request.files['file']
        logger.info(f"Iniciando o processamento do arquivo: {file.filename}")

        # Verifica se é um arquivo ZIP ou JSON
        if not (file.filename.endswith('.zip') or file.filename.endswith('.json') or file.filename.endswith('.txt')):
            return jsonify({"error": "Arquivo deve ser ZIP, JSON ou TXT"}), 400

        # Verifica se é uma atualização
        is_update = request.form.get('update') == 'true'
        file_id = request.form.get('file_id')

        if is_update and file_id:
            logger.info(f"Atualizando arquivo existente: {file_id}")
            return atualizar_conteudo(file, file_id)
        else:
            # Processo normal de importação
            if file.filename.endswith('.json') or file.filename.endswith('.txt'):
                logger.info("Processando arquivo JSON/TXT único")
                # Processa arquivo JSON único
                file_content = file.read()

                if file.filename.endswith('.txt'):
                    # Tenta interpretar o conteúdo do arquivo TXT como JSON
                    try:
                        data = json.loads(file_content.decode('utf-8'))
                    except json.JSONDecodeError as e:
                        logger.error(f"Erro ao decodificar JSON do arquivo TXT: {str(e)}")
                        return jsonify({"error": "Erro ao decodificar JSON do arquivo TXT"}), 400
                else:
                    data = json.loads(file_content)

                if not isinstance(data, list):
                    data = [data]

                for item in data:
                    if not isinstance(item, dict):
                        logger.error("Item não é um dicionário JSON válido")
                        continue

                    generated_id = inserir_bigquery(
                        NAME=file.filename,
                        TEMA=item.get('THEME', 'Tema Padrão')
                    )

                    if not generated_id:
                        return jsonify({"error": "Erro ao gerar ID no BigQuery"}), 500

                    inserir_arquivos_conteudo(
                        ID=generated_id,
                        THEME=item.get('THEME'),
                        MODULO=item.get('MODULO'),
                        NUCLEO=item.get('NUCLEO'),
                        TITULO_NC=item.get('titulo_nc'),
                        PATH=item.get('PATH'),
                        JSON=json.dumps(item),
                        JSON_CONTEUDO=data
                    )

            else:
                # Processa arquivo ZIP
                logger.info("Processando arquivo ZIP")
                import zipfile
                from io import BytesIO

                zip_content = BytesIO(file.read())

                with zipfile.ZipFile(zip_content) as zip_file:
                    # Lista arquivos e procura conteudo inicial
                    logger.info("Arquivos encontrados no ZIP:")
                    for zip_info in zip_file.filelist:
                        logger.info(f"- {zip_info.filename}")

                    # Procura o arquivo conteudo inicial
                    conteudo_inicial_path = None
                    # Lista para armazenar os nomes normalizados do conteudo_inicial
                    conteudo_inicial_normalizado = None
                    
                    for file_info in zip_file.filelist:
                        # Normaliza o nome do arquivo removendo acentos e convertendo para minúsculo
                        filename = unidecode(file_info.filename.strip().lower())
                        logger.info(f"Verificando arquivo: {filename}")

                        # Lista de possíveis nomes para o arquivo de conteúdo inicial
                        possible_names = [
                            'conteudo-inicial.json',
                            'conteudo-inicial.txt',
                            'conteudo inicial.txt',
                            'conteudo_inicial.txt',
                            'conteudo_inicial.json',
                            'conteudoinicial.txt',
                            'conteudoinicial.json',
                            'conteudo inicial.json',
                            'conteúdo inicial.txt',  # Adiciona variações com acento
                            'conteúdo-inicial.txt'
                        ]

                        # Verifica se o nome normalizado do arquivo corresponde a algum dos possíveis nomes
                        normalized_filename = filename.replace(' ', '').replace('-', '').replace('_', '')
                        if any(name.replace(' ', '').replace('-', '').replace('_', '') in normalized_filename for name in possible_names):
                            conteudo_inicial_path = file_info.filename
                            # Armazena a versão normalizada para comparação posterior
                            conteudo_inicial_normalizado = normalized_filename
                            logger.info(f"Arquivo de conteúdo inicial encontrado: {conteudo_inicial_path}")
                            break

                    if not conteudo_inicial_path:
                        logger.error("Arquivo de conteúdo inicial não encontrado")
                        return jsonify({"error": "Arquivo de conteúdo inicial não encontrado"}), 400

                    # Lê o arquivo usando o nome original
                    try:
                        file_content = zip_file.read(conteudo_inicial_path)

                        if conteudo_inicial_path.endswith('.txt'):
                            conteudo_inicial_path = conteudo_inicial_path.replace('.txt', '.json')
                            try:
                                json_content = file_content.decode('utf-8')
                                conteudo_inicial = json.loads(json_content)
                            except json.JSONDecodeError as e:
                                logger.error(f"Erro ao decodificar JSON do arquivo TXT: {str(e)}")
                                return jsonify({"error": "Erro ao decodificar JSON do arquivo TXT"}), 400
                        else:
                            json_content = file_content.decode('utf-8')
                            conteudo_inicial = json.loads(json_content)

                        tema = conteudo_inicial.get('titulo_tema')
                        logger.info(f"Tema encontrado: {tema}")

                        if not tema:
                            logger.error("Campo 'titulo_tema' não encontrado no conteudo_inicial.json")
                            return jsonify({"error": "Campo 'titulo_tema' não encontrado no conteudo_inicial.json"}), 400

                        # Log dos valores antes de inserir no BigQuery
                        logger.info(f"Nome do arquivo (NAME): {file.filename}")
                        logger.info(f"Tema (TEMA): {tema}")

                        # Gera um único ID para todo o conteúdo
                        generated_id = inserir_bigquery(
                            NAME=file.filename,
                            TEMA=tema
                        )

                        if not generated_id:
                            return jsonify({"error": "Erro ao gerar ID no BigQuery"}), 500

                        logger.info(f"ID gerado para todo o conteúdo: {generated_id}")

                        # Salva o conteudo_inicial.json no banco
                        inserir_arquivos_conteudo(
                            ID=generated_id,
                            THEME=tema,
                            MODULO=None,  # conteudo_inicial não tem módulo específico
                            NUCLEO='conteudo_inicial.json',
                            TITULO_NC=conteudo_inicial.get('titulo_tema'),
                            PATH=conteudo_inicial_path,
                            JSON=json.dumps(conteudo_inicial),
                            JSON_CONTEUDO=conteudo_inicial,
                            TITULO_NC_PROXIMA_AULA=None  # Conteúdo inicial não deve ter próxima aula
                        )

                    except Exception as e:
                        logger.error(f"Erro ao ler conteudo_inicial.json: {str(e)}")
                        return jsonify({"error": "Erro ao ler arquivo conteudo_inicial.json"}), 400

                    # Processa todos os arquivos no ZIP usando o mesmo ID
                    arquivos_conteudo = []  # Inicializa a lista para armazenar os dados

                    for file_info in zip_file.filelist:
                        # Normaliza o nome do arquivo e ignora "Estrutura do Tema.txt"
                        filename = file_info.filename.strip().lower()
                        
                        # Normaliza para comparar com o conteudo_inicial já processado
                        normalized_filename = unidecode(filename).replace(' ', '').replace('-', '').replace('_', '')
                        
                        # Ignora o arquivo de conteúdo inicial que já foi processado
                        if conteudo_inicial_normalizado and normalized_filename == conteudo_inicial_normalizado:
                            logger.info(f"Ignorando arquivo de conteúdo inicial já processado: {file_info.filename}")
                            continue
                            
                        if "estrutura do tema" in filename:
                            logger.info(f"Ignorando arquivo: {file_info.filename}")
                            continue

                        # Processa apenas arquivos .txt ou .json
                        if filename.endswith('.txt') or filename.endswith('.json'):
                            try:
                                # Lê o conteúdo do arquivo
                                file_content = zip_file.read(file_info.filename)

                                # Converte o conteúdo para JSON
                                try:
                                    json_data = json.loads(file_content.decode('utf-8'))
                                except json.JSONDecodeError as e:
                                    logger.error(f"Erro ao decodificar JSON do arquivo {file_info.filename}: {str(e)}")
                                    continue

                                # Normaliza o nome do arquivo para .json
                                normalized_filename = file_info.filename.replace('.txt', '.json')

                                # Extrai o nome do módulo do caminho do arquivo
                                path_parts = normalized_filename.split('/')
                                modulo = None
                                if len(path_parts) > 1:
                                    for part in path_parts:
                                        # Normaliza removendo acentos e padronizando para minúsculo
                                        normalized_part = unidecode(part.lower().strip())
                                        if normalized_part.startswith('modulo'):
                                            modulo = part.strip()  # Mantém o nome original do módulo, mas remove espaços
                                            logger.info(f"Módulo encontrado: {modulo} (normalizado: {normalized_part})")
                                            break

                                if modulo is None:
                                    logger.warning(f"Módulo não encontrado em: {normalized_filename}")
                                    logger.warning(f"Partes do caminho: {path_parts}")

                                nome_arquivo = normalized_filename.split('/')[-1]

                                # Adiciona os dados na lista
                                arquivos_conteudo.append({
                                    'MODULO': modulo,
                                    'NUCLEO': nome_arquivo,
                                    'TITULO_NC': json_data.get('titulo_nc'),
                                    'PATH': normalized_filename,
                                    'JSON': json_data,
                                    'JSON_CONTEUDO': json_data,
                                })

                            except json.JSONDecodeError:
                                logger.error(f"Erro ao decodificar JSON do arquivo {file_info.filename}")
                                continue

                    # Ordena a lista de arquivos_conteudo por MODULO e NUCLEO
                    arquivos_conteudo.sort(key=lambda x: (x['MODULO'] or '', x['NUCLEO']))  # Ordena considerando MODULO vazio como menor

                    # Itera sobre a lista ordenada para inserir no banco e determinar a próxima aula
                    for i, conteudo_atual in enumerate(arquivos_conteudo):
                        titulo_nc_proxima_aula = None
                        if i < len(arquivos_conteudo) - 1:  # Verifica se não é o último item
                            titulo_nc_proxima_aula = arquivos_conteudo[i + 1]['TITULO_NC']

                        # Usa o mesmo ID gerado anteriormente
                        inserir_arquivos_conteudo(
                            ID=generated_id,
                            THEME=tema,
                            MODULO=conteudo_atual['MODULO'],
                            NUCLEO=conteudo_atual['NUCLEO'],
                            TITULO_NC=conteudo_atual['TITULO_NC'],
                            PATH=conteudo_atual['PATH'],
                            JSON=json.dumps(conteudo_atual['JSON']),
                            JSON_CONTEUDO=conteudo_atual['JSON_CONTEUDO'],
                            TITULO_NC_PROXIMA_AULA=titulo_nc_proxima_aula  # Passa o TITULO_NC_PROXIMA_AULA
                        )

            return jsonify({"message": "Dados importados com sucesso"}), 200

    except Exception as e:
        logger.error(f"Erro ao importar arquivo: {str(e)}")
        return jsonify({"error": "Erro ao processar o arquivo"}), 500


def atualizar_conteudo(file, file_id):
    """Função para atualizar conteúdo existente"""
    try:
        logger.info(f"Processando atualização para o arquivo ID: {file_id}")
        
        # Se for arquivo ZIP, precisa de tratamento especial
        if file.filename.endswith('.zip'):
            logger.info("Processando atualização de arquivo ZIP")
            import zipfile
            from io import BytesIO
            
            # Lê o arquivo ZIP em um objeto BytesIO
            zip_content = BytesIO(file.read())
            
            with zipfile.ZipFile(zip_content) as zip_file:
                # Lista arquivos e procura conteudo inicial
                logger.info("Arquivos encontrados no ZIP:")
                for zip_info in zip_file.filelist:
                    logger.info(f"- {zip_info.filename}")
                
                # Procura o arquivo conteudo inicial
                conteudo_inicial_path = None
                conteudo_inicial_normalizado = None  # Para armazenar o nome normalizado
                
                for file_info in zip_file.filelist:
                    # Normaliza o nome do arquivo removendo acentos e convertendo para minúsculo
                    filename = unidecode(file_info.filename.strip().lower())
                    
                    # Lista de possíveis nomes para o arquivo de conteúdo inicial
                    possible_names = [
                        'conteudo-inicial.json',
                        'conteudo-inicial.txt',
                        'conteudo inicial.txt',
                        'conteudo_inicial.txt',
                        'conteudo_inicial.json',
                        'conteudoinicial.txt',
                        'conteudoinicial.json',
                        'conteudo inicial.json',
                        'conteúdo inicial.txt',
                        'conteúdo-inicial.txt'
                    ]
                    
                    # Verifica se o nome normalizado do arquivo corresponde a algum dos possíveis nomes
                    normalized_filename = filename.replace(' ', '').replace('-', '').replace('_', '')
                    if any(name.replace(' ', '').replace('-', '').replace('_', '') in normalized_filename for name in possible_names):
                        conteudo_inicial_path = file_info.filename
                        conteudo_inicial_normalizado = normalized_filename  # Armazena o nome normalizado
                        logger.info(f"Arquivo de conteúdo inicial encontrado: {conteudo_inicial_path}")
                        break
                
                if not conteudo_inicial_path:
                    logger.error("Arquivo de conteúdo inicial não encontrado")
                    return jsonify({"error": "Arquivo de conteúdo inicial não encontrado"}), 400
                
                # Lê o arquivo de conteúdo inicial
                try:
                    file_content = zip_file.read(conteudo_inicial_path)
                    
                    if conteudo_inicial_path.endswith('.txt'):
                        conteudo_inicial_path = conteudo_inicial_path.replace('.txt', '.json')
                        try:
                            json_content = file_content.decode('utf-8')
                            conteudo_inicial = json.loads(json_content)
                        except json.JSONDecodeError as e:
                            logger.error(f"Erro ao decodificar JSON do arquivo TXT: {str(e)}")
                            return jsonify({"error": "Erro ao decodificar JSON do arquivo TXT"}), 400
                    else:
                        json_content = file_content.decode('utf-8')
                        conteudo_inicial = json.loads(json_content)
                    
                    tema = conteudo_inicial.get('titulo_tema')
                    logger.info(f"Tema encontrado: {tema}")
                    
                    if not tema:
                        logger.error("Campo 'titulo_tema' não encontrado no conteudo_inicial.json")
                        return jsonify({"error": "Campo 'titulo_tema' não encontrado no conteudo_inicial.json"}), 400
                    
                    # Primeiro, atualiza os dados básicos do arquivo
                    success = atualizar_arquivo(
                        file_id=file_id,
                        file_name=file.filename,
                        json_data={"THEME": tema},
                        json_conteudo=conteudo_inicial
                    )
                    
                    if not success:
                        return jsonify({"error": "Erro ao atualizar informações básicas do arquivo"}), 500
                    
                    # Processa todos os arquivos no ZIP
                    arquivos_conteudo = []
                    
                    # MODIFICAÇÃO: Adiciona o conteúdo inicial à lista de arquivos
                    arquivos_conteudo.append({
                        'MODULO': None,
                        'NUCLEO': 'conteudo_inicial.json',
                        'TITULO_NC': tema,
                        'PATH': conteudo_inicial_path,
                        'JSON': conteudo_inicial,
                        'JSON_CONTEUDO': conteudo_inicial,
                    })
                    
                    for file_info in zip_file.filelist:
                        # Normaliza o nome do arquivo e ignora "Estrutura do Tema.txt"
                        filename = file_info.filename.strip().lower()
                        
                        # Normaliza para comparar com o conteudo_inicial já processado
                        normalized_filename = unidecode(filename).replace(' ', '').replace('-', '').replace('_', '')
                        
                        # Ignora o arquivo de conteúdo inicial que já foi processado anteriormente
                        if conteudo_inicial_normalizado and normalized_filename == conteudo_inicial_normalizado:
                            logger.info(f"Ignorando arquivo de conteúdo inicial já processado: {file_info.filename}")
                            continue
                            
                        if "estrutura do tema" in filename:
                            logger.info(f"Ignorando arquivo: {file_info.filename}")
                            continue
                        
                        # Processa apenas arquivos .txt ou .json
                        if filename.endswith('.txt') or filename.endswith('.json'):
                            try:
                                # Lê o conteúdo do arquivo
                                file_content = zip_file.read(file_info.filename)
                                
                                # Converte o conteúdo para JSON
                                try:
                                    json_data = json.loads(file_content.decode('utf-8'))
                                except json.JSONDecodeError as e:
                                    logger.error(f"Erro ao decodificar JSON do arquivo {file_info.filename}: {str(e)}")
                                    continue
                                
                                # Normaliza o nome do arquivo para .json
                                normalized_filename = file_info.filename.replace('.txt', '.json')
                                
                                # Extrai o nome do módulo do caminho do arquivo
                                path_parts = normalized_filename.split('/')
                                modulo = None
                                if len(path_parts) > 1:
                                    for part in path_parts:
                                        # Normaliza removendo acentos e padronizando para minúsculo
                                        normalized_part = unidecode(part.lower().strip())
                                        if normalized_part.startswith('modulo'):
                                            modulo = part.strip()  # Mantém o nome original do módulo, mas remove espaços
                                            logger.info(f"Módulo encontrado: {modulo} (normalizado: {normalized_part})")
                                            break

                                if modulo is None:
                                    logger.warning(f"Módulo não encontrado em: {normalized_filename}")
                                    logger.warning(f"Partes do caminho: {path_parts}")

                                nome_arquivo = normalized_filename.split('/')[-1]
                                
                                # Adiciona os dados na lista
                                arquivos_conteudo.append({
                                    'MODULO': modulo,
                                    'NUCLEO': nome_arquivo,
                                    'TITULO_NC': json_data.get('titulo_nc'),
                                    'PATH': normalized_filename,
                                    'JSON': json_data,
                                    'JSON_CONTEUDO': json_data,
                                })
                                
                            except json.JSONDecodeError:
                                logger.error(f"Erro ao decodificar JSON do arquivo {file_info.filename}")
                                continue
                    
                    # Chama a função para atualizar o conteúdo completo
                    success = atualizar_conteudo_completo(
                        file_id=file_id,
                        tema=tema,
                        arquivos_conteudo=arquivos_conteudo
                    )
                    
                    if success:
                        return jsonify({"message": "Arquivo ZIP atualizado com sucesso"}), 200
                    else:
                        return jsonify({"error": "Erro ao atualizar conteúdo completo"}), 500
                    
                except Exception as e:
                    logger.error(f"Erro ao processar arquivo ZIP para atualização: {str(e)}")
                    return jsonify({"error": f"Erro ao processar arquivo ZIP para atualização: {str(e)}"}), 500
        
        # Para arquivos JSON ou TXT
        elif file.filename.endswith('.json') or file.filename.endswith('.txt'):
            logger.info("Processando atualização de arquivo JSON/TXT")
            # Lê o conteúdo do arquivo
            file_content = file.read()
            
            # Decodifica o conteúdo
            if file.filename.endswith('.txt'):
                try:
                    data = json.loads(file_content.decode('utf-8'))
                except json.JSONDecodeError as e:
                    logger.error(f"Erro ao decodificar JSON do arquivo TXT: {str(e)}")
                    return jsonify({"error": "Erro ao decodificar JSON do arquivo TXT"}), 400
            else:
                data = json.loads(file_content.decode('utf-8'))
                
            if not isinstance(data, list):
                data = [data]
                
            # Atualiza o arquivo no banco de dados
            success = atualizar_arquivo(
                file_id=file_id,
                file_name=file.filename,
                json_data=data[0] if len(data) > 0 else {},
                json_conteudo=data
            )
            
            if success:
                return jsonify({"message": "Arquivo atualizado com sucesso"}), 200
            else:
                return jsonify({"error": "Erro ao atualizar arquivo"}), 500
        
        else:
            return jsonify({"error": "Tipo de arquivo não suportado para atualização"}), 400
            
    except Exception as e:
        logger.error(f"Erro ao atualizar conteúdo: {str(e)}")
        return jsonify({"error": f"Erro ao atualizar conteúdo: {str(e)}"}), 500