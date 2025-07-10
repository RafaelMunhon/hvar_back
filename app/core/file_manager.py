import os
from app.core.logger_config import setup_logger


logger = setup_logger(__name__)

def criar_diretorio_se_nao_existir(caminho):
    """Cria um diretório se não existir."""
    try:
        os.makedirs(caminho, exist_ok=True)
        logger.info(f"Diretório criado/existente: {caminho}")
    except Exception as e:
        logger.error(f"Erro ao criar diretório: {e}")


def deletar_arquivos_temporarios(pasta_temporaria):
    """Exclui arquivos temporários."""
    logger.info("Deletando arquivos temporários.")
    for arquivo in os.listdir(pasta_temporaria):
        arquivo_path = os.path.join(pasta_temporaria, arquivo)
        try:
            os.remove(arquivo_path)
            logger.debug(f"Arquivo deletado: {arquivo_path}")
        except Exception as e:
            logger.error(f"Erro ao deletar arquivo: {e}")