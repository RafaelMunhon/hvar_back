import datetime
import json
import uuid
from google.cloud import bigquery
from app.core.logger_config import setup_logger
import os
import logging
from datetime import datetime, timedelta

logger = setup_logger(__name__)

# Corrigir esta linha
create_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

def get_bigquery_client():
    """Retorna um cliente do BigQuery"""
    try:
        return bigquery.Client()
    except Exception as e:
        logger.error(f"Erro ao criar cliente BigQuery: {str(e)}")
        return None

def execute_query(query, params=None):
    """
    Executa uma query no BigQuery com parâmetros
    Args:
        query: string com a query SQL
        params: dicionário com os parâmetros da query
    Returns:
        lista de resultados ou None em caso de erro
    """
    try:
        client = get_bigquery_client()
        if not client:
            return None

        job_config = bigquery.QueryJobConfig()

        # Configura os parâmetros se existirem
        if params:
            job_config.query_parameters = [
                bigquery.ScalarQueryParameter(key, "STRING", value)
                for key, value in params.items()
            ]

        # Executa a query
        query_job = client.query(query, job_config=job_config)

        # Obtém os resultados
        results = query_job.result()

        # Converte para lista de dicionários
        return [dict(row.items()) for row in results]

    except Exception as e:
        logger.error(f"Erro ao executar query: {str(e)}")
        logger.error(f"Query: {query}")
        logger.error(f"Parâmetros: {params}")
        return None

def inserir_bigquery(NAME, TEMA):
    client = bigquery.Client()
    tabela_id = "conteudo-autenticare.poc_dataset.ARQUIVOS"

    # Gerar UUID no Python
    generated_id = str(uuid.uuid4())
    logger.info(f"Data de criação: {create_date}, ID: {generated_id}")

    query = f"""
        INSERT INTO `{tabela_id}` (ID, NAME, THEME, CREATE_DATE)
        VALUES ('{generated_id}', '{NAME}', '{TEMA}', PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E3SZ', '{create_date}'))
    """

    try:
        query_job = client.query(query)
        query_job.result()  # Aguarda a conclusão da query

        logger.info(f"Registro inserido com sucesso. ID gerado: {generated_id}")
        return generated_id

    except Exception as e:
        logger.error(f"Erro ao inserir o registro: {str(e)}")
        return None


def consultar_nome_arquivo(id=None, name=None, titulo_nc=None):
    """Consulta nomes de arquivos no BigQuery com opção de filtros"""
    try:
        query = """
        SELECT
            a1.ID,
            a1.NAME,
            a2.THEME,
            a2.TITULO_NC,
            a2.MODULO,
            a1.CREATE_DATE,
            a2.NUCLEO
        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS` a1
        INNER JOIN `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` a2
        ON a1.ID = a2.ID
        WHERE 1=1
        """
        
        params = {}
        
        # Adiciona condições de filtro se fornecidas
        if id:
            query += " AND a1.ID LIKE @id"
            params['id'] = f"%{id}%"
            
        if name:
            query += " AND a1.NAME LIKE @name"
            params['name'] = f"%{name}%"
            
        if titulo_nc:
            query += " AND a2.TITULO_NC LIKE @titulo_nc"
            params['titulo_nc'] = f"%{titulo_nc}%"
            
        query += " ORDER BY a1.CREATE_DATE DESC"
        
        return execute_query(query, params)

    except Exception as e:
        logger.error(f"Erro ao consultar nomes de arquivos: {str(e)}")
        return None



def inserir_arquivos_conteudo(ID, THEME, MODULO, NUCLEO, TITULO_NC, PATH, JSON, JSON_CONTEUDO, TITULO_NC_PROXIMA_AULA=None): # Adicionado TITULO_NC_PROXIMA_AULA
    client = bigquery.Client()
    tabela_id = "conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO"

    # Verificar se é o conteúdo inicial e definir TITULO_NC_PROXIMA_AULA como None
    if NUCLEO == 'conteudo_inicial.json' or NUCLEO == 'conteudo-inicial.json':
        TITULO_NC_PROXIMA_AULA = None
        logger.info("Definindo TITULO_NC_PROXIMA_AULA como None para o conteúdo inicial")

    query = f"""
        INSERT INTO `{tabela_id}` (ID, THEME, MODULO, NUCLEO, TITULO_NC, PATH, JSON, JSON_CONTEUDO, TITULO_NC_PROXIMA_AULA) # Adicionado TITULO_NC_PROXIMA_AULA na query
        VALUES (
            @id,
            @theme,
            @modulo,
            @nucleo,
            @titulo_nc,
            @path,
            @json,
            PARSE_JSON(@json_conteudo),
            @titulo_nc_proxima_aula # Adicionado parâmetro
        );
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", ID),
            bigquery.ScalarQueryParameter("theme", "STRING", THEME),
            bigquery.ScalarQueryParameter("modulo", "STRING", MODULO),
            bigquery.ScalarQueryParameter("nucleo", "STRING", NUCLEO),
            bigquery.ScalarQueryParameter("titulo_nc", "STRING", TITULO_NC),
            bigquery.ScalarQueryParameter("path", "STRING", PATH),
            bigquery.ScalarQueryParameter("json", "STRING", json.dumps(JSON)),
            bigquery.ScalarQueryParameter("json_conteudo", "STRING", json.dumps(JSON_CONTEUDO)),
            bigquery.ScalarQueryParameter("titulo_nc_proxima_aula", "STRING", TITULO_NC_PROXIMA_AULA) # Adicionado parâmetro
        ]
    )
    try:
        query_job = client.query(query, job_config=job_config)
        query_job.result()
        logger.info(f"Registro inserido com sucesso na tabela ARQUIVOS_CONTEUDO com TITULO_NC_PROXIMA_AULA={TITULO_NC_PROXIMA_AULA} para NUCLEO={NUCLEO}") # Log atualizado
    except Exception as e:
        logger.error(f"Erro ao inserir o registro na tabela ARQUIVOS_CONTEUDO: {str(e)}")



def consultar_arquivo_conteudo():
    client = bigquery.Client()

    query = """
    SELECT CAST(ID AS STRING) AS ID, THEME, MODULO, NUCLEO, TITULO_NC, PATH
    FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO`
    """

    try:
        query_job = client.query(query)  # Executa a consulta
        row = query_job.result()  # Obtém os resultados

        # Retorna uma lista de dicionários com os dados
        arquivos = [{
            "ID": row.ID,
            "TEMA": row.THEME,
            "MODULO": row.MODULO,
            "NUCLEO": row.NUCLEO,
            "TITULO_NC": row.TITULO_NC,
            "PATH": row.PATH} for row in row]
        return arquivos

    except Exception as e:
        logger.error(f"Erro ao consultar BigQuery: {str(e)}")
        return []



def inserir_video(ID, URL, THEME, TITULO_NC, TYPE_VIDEO):
    client = bigquery.Client()
    tabela_id = "conteudo-autenticare.poc_dataset.VIDEOS"


    logger.info(f"Data de criação: {create_date}")

    query = f"""
        INSERT INTO `{tabela_id}` (ID, URL, THEME, TITULO_NC, TYPE_VIDEO, CREATE_DATE)
        VALUES ('{ID}', '{URL}', '{THEME}', '{TITULO_NC}', '{TYPE_VIDEO}', PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E3SZ', '{create_date}'))
    """

    try:
        query_job = client.query(query)
        query_job.result()
        logger.info(f"Video inserido com sucesso na tabela VIDEOS.")
    except Exception as e:
        logger.error(f"Erro ao inserir o video na tabela VIDEOS: {str(e)}")


def inserir_audio(id_arquivo, url_audio, tipo_audio=None, theme=None, titulo_nc_original=None):
    """
    Insere um registro de áudio no banco de dados.
    """
    try:
        logger.info(f"Iniciando inserção do áudio no banco: ID={id_arquivo}, URL={url_audio}")
        logger.info(f"Parâmetros: content_id={id_arquivo}, theme={theme}, titulo_nc_original={titulo_nc_original}")

        if not id_arquivo:
            logger.error("ID do arquivo não fornecido")
            return False

        if not url_audio:
            logger.error("URL do áudio não fornecida")
            return False

        client = bigquery.Client()
        max_tentativas = 5
        tentativa = 0
        while tentativa < max_tentativas:
            tentativa += 1
            query_verificacao = f"""
                SELECT COUNT(*) AS count FROM `conteudo-autenticare.poc_dataset.AUDIOS` WHERE ID = '{id_arquivo}'
            """
            result = execute_query(query_verificacao)
            if result and result[0]['count'] > 0:
                logger.warning(f"ID {id_arquivo} já existe. Gerando um novo ID...")
                id_arquivo = str(uuid.uuid4())  # Gera um novo UUID
            else:
                # ID não existe, podemos inserir
                break

        if tentativa >= max_tentativas:
            logger.error("Número máximo de tentativas para gerar um ID único atingido.")
            return False

        query = """
            INSERT INTO `conteudo-autenticare.poc_dataset.AUDIOS`
            (ID, URL, TIPO_AUDIO, CREATE_DATE, THEME, TITULO_NC)
            VALUES
            (@id_arquivo, @url_audio, @tipo_audio, CURRENT_TIMESTAMP(), @theme, @titulo_nc)
        """

        logger.info(f"Executando query com parâmetros: ID={id_arquivo}, URL={url_audio}, tipo={tipo_audio}")

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id_arquivo", "STRING", id_arquivo),
                bigquery.ScalarQueryParameter("url_audio", "STRING", url_audio),
                bigquery.ScalarQueryParameter("tipo_audio", "STRING", tipo_audio),
                bigquery.ScalarQueryParameter("theme", "STRING", theme),
                bigquery.ScalarQueryParameter("titulo_nc", "STRING", titulo_nc_original),
            ]
        )

        query_job = client.query(query, job_config=job_config)
        query_job.result()

        logger.info(f"Áudio inserido com sucesso no banco de dados: ID={id_arquivo}")
        return True

    except Exception as e:
        logger.error(f"Erro ao inserir áudio no banco de dados: {str(e)}", exc_info=True)
        return False


def inserir_video_pexel(URL, TYPE_VIDEO):
    """
    Insere um registro de vídeo Pexel no banco de dados.

    Args:
        URL (str): URL do vídeo
        TYPE_VIDEO (str): Tipo de vídeo ('PEXEL')   

    Retorna:
        str: ID do vídeo inserido
    """
    client = bigquery.Client()
    tabela_id = "conteudo-autenticare.poc_dataset.VIDEOS"

    # Gerar UUID no Python
    generated_id = str(uuid.uuid4())
    logger.info(f"Data de criação: {create_date}, ID: {generated_id}")

    query = f"""
        INSERT INTO `{tabela_id}` (ID, URL, TYPE_VIDEO, CREATE_DATE)
        VALUES ('{generated_id}', '{URL}', '{TYPE_VIDEO}', PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E3SZ', '{create_date}'))
    """

    try:
        query_job = client.query(query)
        query_job.result()  # Aguarda a conclusão da query

        logger.info(f"Registro inserido com sucesso. ID gerado: {generated_id}")
        return generated_id

    except Exception as e:
        logger.error(f"Erro ao inserir o registro: {str(e)}")
        return None

def consultar_videos_pexel():
    """Consulta vídeos do tipo Pexel no banco de dados."""
    query = """
        SELECT URL, CREATE_DATE
        FROM `conteudo-autenticare.poc_dataset.VIDEOS`
        WHERE TYPE_VIDEO = 'PEXEL'
        ORDER BY CREATE_DATE DESC
        LIMIT 1000
    """

    try:
        results = execute_query(query)
        if results:
            # Formata as datas para string ISO
            for video in results:
                if 'CREATE_DATE' in video:
                    video['CREATE_DATE'] = video['CREATE_DATE'].isoformat()
            return results
        return []

    except Exception as e:
        logger.error(f"Erro ao consultar vídeos Pexel: {str(e)}")
        return []

def consultar_videos_studio():
    """Consulta vídeos do tipo Studio no banco de dados."""
    query = """
        SELECT ID, URL, CREATE_DATE
        FROM `conteudo-autenticare.poc_dataset.VIDEOS`
        WHERE TYPE_VIDEO = 'STUDIO'
        ORDER BY CREATE_DATE DESC
        LIMIT 1000
    """

    try:
        results = execute_query(query)
        if results:
            # Formata as datas para string ISO
            for video in results:
                if 'CREATE_DATE' in video:
                    video['CREATE_DATE'] = video['CREATE_DATE'].isoformat()
            return results
        return []

    except Exception as e:
        logger.error(f"Erro ao consultar vídeos Studio: {str(e)}")
        return []


def remover_audio_duplicado(id_duplicado):
    query = f"""
        DELETE FROM `conteudo-autenticare.poc_dataset.AUDIOS`
        WHERE ID = '{id_duplicado}'
        AND CREATE_DATE NOT IN (SELECT MIN(CREATE_DATE) FROM `conteudo-autenticare.poc_dataset.AUDIOS` WHERE ID = '{id_duplicado}')
    """
    execute_query(query)
    logging.info(f"Registros duplicados com ID {id_duplicado} removidos.")


def encontrar_e_remover_duplicatas():
    query_ids_duplicados = """
        SELECT ID FROM `conteudo-autenticare.poc_dataset.AUDIOS`
        GROUP BY ID
        HAVING COUNT(*) > 1
    """
    resultados = execute_query(query_ids_duplicados)
    if resultados:
        for row in resultados:
            id_duplicado = row['ID']
            remover_audio_duplicado(id_duplicado)  # Remover registros duplicados
    else:
        logging.info("Nenhum registro duplicado encontrado.")

# Script de limpeza (Execute isso UMA VEZ em um ambiente de TESTE primeiro!)
#encontrar_e_remover_duplicatas()


# Novas funções para verificação e atualização de arquivos

def verificar_arquivo_existe(nome_arquivo):
    """
    Verifica se um arquivo já existe no banco de dados pelo nome
    
    Args:
        nome_arquivo: nome do arquivo a ser verificado
        
    Returns:
        Dicionário com informações do arquivo se existir, None caso contrário
    """
    try:
        query = """
        SELECT a1.ID, a1.NAME, a1.THEME
        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS` a1
        WHERE a1.NAME = @nome
        LIMIT 1
        """
        
        result = execute_query(query, {"nome": nome_arquivo})
        
        if result and len(result) > 0:
            return result[0]
        return None
        
    except Exception as e:
        logger.error(f"Erro ao verificar existência do arquivo: {str(e)}")
        return None


def atualizar_arquivo(file_id, file_name, json_data, json_conteudo):
    """
    Atualiza um arquivo existente no banco de dados
    
    Args:
        file_id: ID do arquivo a ser atualizado
        file_name: Nome do arquivo
        json_data: Dados JSON para atualização (dicionário)
        json_conteudo: Conteúdo JSON completo (pode ser lista ou dicionário)
        
    Returns:
        True se atualizado com sucesso, False caso contrário
    """
    try:
        client = bigquery.Client()
        
        # Primeiro, verifica se o arquivo existe e obtém suas informações
        query_info = """
        SELECT ac.THEME, ac.MODULO, ac.NUCLEO, ac.TITULO_NC, ac.PATH, ac.TITULO_NC_PROXIMA_AULA
        FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO` ac
        WHERE ac.ID = @id
        LIMIT 1
        """
        
        arquivo_info = execute_query(query_info, {"id": file_id})
        
        if not arquivo_info or len(arquivo_info) == 0:
            logger.error(f"Arquivo com ID {file_id} não encontrado para atualização")
            return False
            
        # Extrai informações existentes
        arquivo_info = arquivo_info[0]
        
        # Atualiza o registro na tabela ARQUIVOS_CONTEUDO
        query_update = """
        UPDATE `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO`
        SET JSON = @json,
            JSON_CONTEUDO = PARSE_JSON(@json_conteudo),
            THEME = @theme,
            TITULO_NC = @titulo_nc,
            MODULO = @modulo
        WHERE ID = @id
        """
        
        # Determina os valores a serem atualizados, mantendo os valores existentes quando não fornecidos
        theme = json_data.get('THEME', arquivo_info.get('THEME'))
        titulo_nc = json_data.get('titulo_nc', arquivo_info.get('TITULO_NC'))
        modulo = json_data.get('MODULO', arquivo_info.get('MODULO'))
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id", "STRING", file_id),
                bigquery.ScalarQueryParameter("json", "STRING", json.dumps(json_data)),
                bigquery.ScalarQueryParameter("json_conteudo", "STRING", json.dumps(json_conteudo)),
                bigquery.ScalarQueryParameter("theme", "STRING", theme),
                bigquery.ScalarQueryParameter("titulo_nc", "STRING", titulo_nc),
                bigquery.ScalarQueryParameter("modulo", "STRING", modulo)
            ]
        )
        
        # Executa a atualização
        query_job = client.query(query_update, job_config=job_config)
        query_job.result()
        
        # Também atualiza o registro na tabela ARQUIVOS
        query_update_arquivo = """
        UPDATE `conteudo-autenticare.poc_dataset.ARQUIVOS`
        SET NAME = @name,
            THEME = @theme
        WHERE ID = @id
        """
        
        job_config_arquivo = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id", "STRING", file_id),
                bigquery.ScalarQueryParameter("name", "STRING", file_name),
                bigquery.ScalarQueryParameter("theme", "STRING", theme)
            ]
        )
        
        query_job_arquivo = client.query(query_update_arquivo, job_config=job_config_arquivo)
        query_job_arquivo.result()
        
        logger.info(f"Arquivo com ID {file_id} atualizado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao atualizar arquivo: {str(e)}")
        return False


def atualizar_conteudo_completo(file_id, tema, arquivos_conteudo):
    """
    Atualiza o conteúdo completo de um arquivo ZIP
    
    Args:
        file_id: ID do arquivo a ser atualizado
        tema: Tema do conteúdo
        arquivos_conteudo: Lista de arquivos e seus conteúdos
        
    Returns:
        True se atualizado com sucesso, False caso contrário
    """
    try:
        client = bigquery.Client()
        
        # Primeiro, atualizamos os dados básicos na tabela ARQUIVOS
        query_update_arquivo = """
        UPDATE `conteudo-autenticare.poc_dataset.ARQUIVOS`
        SET THEME = @theme
        WHERE ID = @id
        """
        
        job_config_arquivo = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id", "STRING", file_id),
                bigquery.ScalarQueryParameter("theme", "STRING", tema)
            ]
        )
        
        query_job_arquivo = client.query(query_update_arquivo, job_config=job_config_arquivo)
        query_job_arquivo.result()
        
        # Excluímos todos os registros existentes na tabela ARQUIVOS_CONTEUDO
        query_delete = """
        DELETE FROM `conteudo-autenticare.poc_dataset.ARQUIVOS_CONTEUDO`
        WHERE ID = @id
        """
        
        job_config_delete = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("id", "STRING", file_id)
            ]
        )
        
        query_job_delete = client.query(query_delete, job_config=job_config_delete)
        query_job_delete.result()
        
        # Não precisamos mais adicionar um registro de conteúdo inicial separado
        # Removido o trecho que criava um conteúdo inicial simplificado
        
        # Ordena a lista - assegure que o conteúdo inicial fique primeiro 
        arquivos_conteudo.sort(key=lambda x: (
            0 if x['NUCLEO'] == 'conteudo_inicial.json' or x['NUCLEO'] == 'conteudo-inicial.json' else 1,  # Coloca conteúdo inicial primeiro
            x['MODULO'] or '',
            x['NUCLEO']
        ))
        
        # Itera sobre a lista ordenada para inserir no banco e determinar a próxima aula
        for i, conteudo_atual in enumerate(arquivos_conteudo):
            titulo_nc_proxima_aula = None
            if i < len(arquivos_conteudo) - 1:  # Verifica se não é o último item
                titulo_nc_proxima_aula = arquivos_conteudo[i + 1]['TITULO_NC']
                
            # Verifica se é conteúdo inicial e força TITULO_NC_PROXIMA_AULA como None
            nucleo = conteudo_atual['NUCLEO']
            if nucleo == 'conteudo_inicial.json' or nucleo == 'conteudo-inicial.json':
                titulo_nc_proxima_aula = None
            
            # Usa o mesmo ID fornecido
            inserir_arquivos_conteudo(
                ID=file_id,
                THEME=tema,
                MODULO=conteudo_atual['MODULO'],
                NUCLEO=conteudo_atual['NUCLEO'],
                TITULO_NC=conteudo_atual['TITULO_NC'],
                PATH=conteudo_atual['PATH'],
                JSON=json.dumps(conteudo_atual['JSON']),
                JSON_CONTEUDO=conteudo_atual['JSON_CONTEUDO'],
                TITULO_NC_PROXIMA_AULA=titulo_nc_proxima_aula
            )
        
        logger.info(f"Conteúdo completo do arquivo com ID {file_id} atualizado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao atualizar conteúdo completo: {str(e)}")
        return False
    

def inserir_contextualizacao(URL, THEME_ORIGIN, THEME_DESTINY):
    """
    Insere um registro de vídeo Pexel no banco de dados.

    Args:
        URL (str): URL do vídeo
        TYPE_VIDEO (str): Tipo de vídeo ('PEXEL')   

    Retorna:
        str: ID do vídeo inserido
    """
    client = bigquery.Client()
    tabela_id = "conteudo-autenticare.poc_dataset.CONTEXTUALIZACAO"

    # Gerar UUID no Python
    generated_id = str(uuid.uuid4())
    logger.info(f"Data de criação: {create_date}, ID: {generated_id}")

    query = f"""
        INSERT INTO `{tabela_id}` (ID, URL, THEME_ORIGIN, THEME_DESTINY, CREATE_DATE)
        VALUES ('{generated_id}', '{URL}', '{THEME_ORIGIN}', '{THEME_DESTINY}', PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E3SZ', '{create_date}'))
    """

    try:
        query_job = client.query(query)
        query_job.result()  # Aguarda a conclusão da query

        logger.info(f"Registro inserido com sucesso. ID gerado: {generated_id}")
        return generated_id

    except Exception as e:
        logger.error(f"Erro ao inserir o registro: {str(e)}")
        return None