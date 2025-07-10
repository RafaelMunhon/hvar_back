import json
import os
import re
import zipfile
from flask import Blueprint, jsonify, request
from app.bd.bd import inserir_bigquery, inserir_arquivos_conteudo
from app.common.json_zip_prompt import generate_new_script, generate_new_script_json
from app.config import ffmpeg
from app.config.vertexAi import generate_content
from app.core import file_manager

from app.core.logger_config import setup_logger

logger = setup_logger(__name__)

process_bp = Blueprint('process', __name__)

@process_bp.route("", methods=['POST'])
def processar_arquivos_zip():
    logger.info("Requisição de processamento recebida.")
    if 'file' not in request.files:
        logger.error("Erro: Nenhum arquivo enviado.")
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    new_context_prompt = request.form.get('theme')

    if file.filename == '':
        logger.error("Erro: Nome de arquivo inválido.")
        return jsonify({'error': 'Nome de arquivo inválido'}), 400
    
    pasta_output_json_zip = ffmpeg.get_json_output_zip_path()
    file_manager.criar_diretorio_se_nao_existir(pasta_output_json_zip)
    
    if file and file.filename.endswith('.zip'):
        temp_zip_path = 'temp.zip'
        file.save(temp_zip_path)
        logger.info(f"Arquivo ZIP salvo temporariamente: {temp_zip_path}")

        json_files, id_arquivo = extract_json_from_zip(temp_zip_path, pasta_output_json_zip , new_context_prompt)

        if not json_files:
            logger.info("Nenhum arquivo JSON encontrado no ZIP.")
            return jsonify({'message': 'Nenhum arquivo JSON encontrado no ZIP'}), 200

        for file_name, json_data in json_files.items():
            if json_data:
               
               #salvar_dados_big_query(json_data, id_arquivo)

               new_json_data = transform_json(json_data, new_context_prompt, file_name)
               if new_json_data: 
                   output_file_path = os.path.join(pasta_output_json_zip, file_name)
                   salvar_dados_big_query(new_json_data, id_arquivo, output_file_path, new_context_prompt)
                   save_json_file(output_file_path, new_json_data)

        os.remove(temp_zip_path)
        logger.info("Arquivo ZIP temporário removido.")
        logger.info("Processamento concluído com sucesso.")
        # aqui que 
        return jsonify({'message': 'Arquivos JSON processados com sucesso'}), 200
    logger.error("Erro: Arquivo inválido. Envie um arquivo .zip")
    return jsonify({'error': 'Arquivo inválido. Envie um arquivo .zip'}), 400

def extract_json_from_zip(zip_file_path, output_dir, new_context_prompt):
    logger.info(f"Iniciando extração de JSONs do arquivo: {zip_file_path}")
    json_files = {}
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        for file_name in zip_ref.namelist():
            if file_name.endswith(".json"):
                try:
                    with zip_ref.open(file_name) as file:
                         json_content = json.load(file)
                         json_files[file_name] = json_content
                         output_path = os.path.join(output_dir, file_name)
                         os.makedirs(os.path.dirname(output_path), exist_ok=True)
                         logger.info(f"  JSON extraído: {file_name}")
                except json.JSONDecodeError as e:
                    logger.error(f"  Erro ao decodificar JSON em: {file_name} - {e}")
    logger.info("Extração de JSONs concluída.")
    
    id_arquivo = inserir_bigquery(file_name, new_context_prompt)

    return json_files, id_arquivo

async def transform_json(json_data, new_context_prompt, file_name):
    logger.info(f"  Iniciando transformação do JSON: {file_name}")
    context = " ".join(extract_text_from_json(json_data))
    logger.info(f"    Contexto extraído: {context}")

    new_script = generate_new_script(context, new_context_prompt)
    logger.info(f"Novo roteiro gerado: {new_script}")


    prompt_json = generate_new_script_json({json.dumps(json_data, indent=4)}, new_script)

    response = await generate_content(prompt_json)

    logger.info(f"  Resposta do Gemini ao gerar novo JSON: {response}")

    try:
        new_json_data = response.strip()
        new_json_data = re.sub(r'```json', '', new_json_data).strip()
        new_json_data = re.sub(r'```', '', new_json_data).strip()

        try:
            logger.info(f"  JSON transformado com sucesso: {file_name}")
            return json.loads(new_json_data)
        except json.JSONDecodeError as e:
             logger.error(f"  Erro ao decodificar JSON retornado pelo Gemini após limpeza: {file_name} - {e}")
             logger.error(f"  Resposta do Gemini após limpeza: {new_json_data}")
             return json_data
    except Exception as e:
        logger.error(f"  Erro ao processar resposta do Gemini: {file_name} - {e}")
        return json_data
    
def extract_text_from_json(json_data):
    if isinstance(json_data, dict):
        text_parts = []
        for key, value in json_data.items():
            text_parts.extend(extract_text_from_json(value))
        return text_parts
    elif isinstance(json_data, list):
        text_parts = []
        for item in json_data:
            text_parts.extend(extract_text_from_json(item))
        return text_parts
    elif isinstance(json_data, str):
        return [json_data]
    else:
        return []
    
def save_json_file(file_path, json_data):
    try:
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            logger.info(f"  Arquivo salvo em: {file_path}")
    except Exception as e:
        logger.error(f"  Erro ao salvar arquivo: {file_path} - {e}")

def extrair_titulos_do_json(json_string):
    try:
        data = json.loads(json_string)
        titulos = {"titulo_tema": None, "titulo_nc": None, "modulo": None}

        # Caso 1: JSON com "titulo_tema" diretamente
        if "titulo_tema" in data:
            titulos["titulo_tema"] = data.get("titulo_tema")

        # Caso 2: JSON com "modulos" e "nucleosConceituais"
        if "modulos" in data:
           for modulo in data.get("modulos", []):
             titulos["modulo"] = modulo.get("titulo_modulo")
        # Caso 3: JSON com "titulo_nc" diretamente
        if "titulo_nc" in data:
          titulos["titulo_nc"] = data.get("titulo_nc")
        return titulos
    except json.JSONDecodeError:
        print("Erro: JSON inválido.")
        return None
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return None
    

def salvar_dados_big_query(JSON_DATA, ID, OUTPUT_FILE_PATH=None, THEME=None):
    try:
        if not JSON_DATA:
            raise ValueError("JSON_DATA não pode ser vazio ou None.")
        if not ID:
            raise ValueError("ID não pode ser vazio ou None.")

        # Extrair títulos do JSON, garantindo que seja uma string JSON válida
        try:
            titulo_data = extrair_titulos_do_json(json.dumps(JSON_DATA))
        except Exception as e:
            raise ValueError(f"Erro ao extrair títulos do JSON: {e}")

        # Obter valores do JSON
        modulo_value = titulo_data.get("modulo")
        nucleo_value = "Teste" if modulo_value else titulo_data.get("titulo_nc")

        if not modulo_value:
            modulo_value = "Teste"
        
        if not nucleo_value:
            raise ValueError("Não foi possível determinar o valor de 'nucleo'. Verifique o JSON de entrada.")

        # Inserção dos dados no BigQuery
        try:
            inserir_arquivos_conteudo(ID, THEME, modulo_value, "NUCLEO", nucleo_value, OUTPUT_FILE_PATH, JSON_DATA)
        except Exception as e:
            raise RuntimeError(f"Erro ao inserir dados no BigQuery: {e}")

        return {"status": "sucesso", "ID": ID}

    except ValueError as ve:
        logger.error(f"Erro de valor: {ve}")
        return {"status": "erro", "mensagem": str(ve)}

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return {"status": "erro", "mensagem": "Ocorreu um erro inesperado durante a execução."}

