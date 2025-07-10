import asyncio
import os
import requests
from app import settings
from app.config.gemini_client import get_gemini_manager
from app.config.vertexAi import generate_content
from app.utils.verificaImagemVideo import analisar_imagem
import logging

logger = logging.getLogger(__name__)

# Tokens de API
PEXELS_API_KEY = 'Yuyg91HW4pxA7DPLVrJiacMnmiBcNvHgp0rT8hs00SEyJmRSANHUeuwB'  # Substitua pelo seu token do Pexels

# URLs da API
PEXELS_API_URL = "https://api.pexels.com/v1/search"

# Cabeçalhos de autenticação
PEXELS_HEADERS = {
    "Authorization": PEXELS_API_KEY
}

def buscar_imagens_pexels(term, per_page=30):
    """Faz uma busca por imagens na API do Pexels."""
    # Adiciona parâmetros para priorizar fotos reais
    params = {
        "query": term,
        "per_page": per_page,
        "orientation": "landscape",  # Formato paisagem geralmente melhor para vídeos
        "size": "large",  # Imagens grandes
        "type": "photo"  # Apenas fotos, não ilustrações
    }
    
    try:
        response = requests.get(
            PEXELS_API_URL,
            params=params,
            headers=PEXELS_HEADERS
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao buscar imagens no Pexels: {e}")
        return None

def selecionar_melhor_imagem_pexels(data):
    """Seleciona a melhor imagem do Pexels com base na resolução."""
    if data and data.get('photos'):
        best_image = max(data['photos'], key=lambda x: x['width'] * x['height'])
        return best_image['src']['original'], best_image['id']
    return None, None

def baixar_imagem(image_url, pathName):
    """Baixa uma imagem a partir da URL fornecida e verifica sua adequação."""
    try:
        img_response = requests.get(image_url, stream=True)
        img_response.raise_for_status()
        
        with open(f"{pathName}", "wb") as img_file:
            for chunk in img_response.iter_content(1024):
                img_file.write(chunk)
        logger.info(f"Imagem baixada e salva como '{pathName}'")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao baixar a imagem: {e}")
        return False

def busca_imagens_pexels(lista_imagens, termo, fileName, path_name, momento_chave):
    """Função para manter compatibilidade com código existente (sem usar Envato)."""
    return criar_lista_imagens_pexels(lista_imagens, termo, fileName, path_name, momento_chave)


def criar_lista_imagens_pexels(lista_imagens, termo, fileName, path_name, momento_chave, max_tentativas=10):
    # Modifica o termo inicial para priorizar fotos reais
    if "ilustração" in termo.lower() or "ilustracao" in termo.lower():
        termo = termo.lower().replace("ilustração", "foto").replace("ilustracao", "foto")
    termo = f"real photo of {termo}"
    
    tentativas = 0
    termo_atual = termo
    imagens_tentadas = set()  # Conjunto para rastrear URLs já tentadas
    urls_selecionadas = set()  # Conjunto para rastrear URLs já selecionadas para o vídeo
    resultado_busca = None
    indice_imagem = 0

    # Pega URLs já usadas no vídeo
    for img in lista_imagens:
        urls_selecionadas.add(img['urlImg'])

    while tentativas < max_tentativas:
        tentativas += 1
        logger.info(f"Tentativa {tentativas} de {max_tentativas} para termo: '{termo_atual}'")

        # Faz nova busca apenas se necessário
        if not resultado_busca or indice_imagem >= len(resultado_busca.get('photos', [])):
            resultado_busca = buscar_imagens_pexels(termo_atual, per_page=30)
            #resultado_busca = buscar_imagens_pexels(termo_traduzido, per_page=30)
            indice_imagem = 0
            
            if not resultado_busca or not resultado_busca.get('photos'):
                logger.error("Sem resultados na busca")
                termo_atual = reformular_termo_busca(termo)
                continue

        # Pega próxima imagem não tentada
        photos = resultado_busca['photos']
        while indice_imagem < len(photos):
            imagem = photos[indice_imagem]
            imagem_url = imagem['src']['original']
            indice_imagem += 1

            # Pula se a imagem já foi tentada ou já está sendo usada no vídeo
            if imagem_url in imagens_tentadas or imagem_url in urls_selecionadas:
                logger.info(f"Pulando imagem duplicada: {imagem_url}")
                continue

            imagens_tentadas.add(imagem_url)
            
            if baixar_imagem(imagem_url, path_name):
                analise = analisar_imagem(path_name, termo_atual, "")
                
                logger.info("Resultado da análise da imagem:")
                logger.info(f"Descrição Gemini: {analise['descricao_gemini']}")
                logger.info(f"Corresponde: {analise['corresponde']}")
                logger.info(f"Confiança: {analise['confianca']*100}%")
                logger.info(f"Detalhes: {analise['detalhes']}")

                if analise['corresponde'] and analise['confianca'] > 0.7:
                    urls_selecionadas.add(imagem_url)  # Adiciona à lista de URLs selecionadas
                    lista_imagens.append({
                        "urlImg": imagem_url,
                        "caminho": path_name,
                        "momentoChave": momento_chave,
                        "nomeArquivo": f"{fileName}",
                        "analise_gemini": analise
                    })
                    logger.info("Imagem validada e adicionada à lista")
                    return lista_imagens
                else:
                    logger.warning("Imagem não corresponde à descrição esperada ou confiança muito baixa")
            break

        termo_atual = reformular_termo_busca(termo)
        
    logger.error(f"Todas as {max_tentativas} tentativas falharam para encontrar uma imagem adequada")
    return lista_imagens

async def reformular_termo_busca(termo):
    """
    Reformula o termo de busca para melhorar os resultados.

    Args:
        termo (str): Termo original de busca

    Returns:
        str: Termo reformulado ou o termo original em caso de erro
    """
    prompt = f"""
        Preciso reformular o seguinte termo de busca para encontrar FOTOS REAIS (não ilustrações): "{termo}"
        
        Por favor, sugira uma reformulação do termo que:
        1. Mantenha o significado principal
        2. Seja mais específico e descritivo
        3. Use termos que funcionem bem para busca de FOTOGRAFIAS REAIS
        4. Inclua detalhes visuais importantes
        5. Evite termos como "ilustração", "desenho", "arte"
        6. Adicione termos como "foto", "fotografia", "real", "pessoa real"
        7. Escreva em inglês
        
        Retorne apenas o novo termo reformulado, sem explicações adicionais.
    """
    
    try:
        # generate_content retorna string diretamente
        manager = get_gemini_manager()
        novo_termo = await manager.generate_content(prompt, model=settings.GEMINI)
        
        if not novo_termo:
            logger.warning(f"Não foi possível reformular o termo: '{termo}'")
            return termo
            
        # Remove possíveis aspas e espaços extras
        novo_termo = novo_termo.strip().strip('"\'')
        logger.info(f"Termo reformulado: '{novo_termo}'")
        return novo_termo
        
    except Exception as e:
        logger.error(f"Erro ao reformular termo: {str(e)}")
        return termo  # Retorna o termo original em caso de erro

# Teste
if __name__ == "__main__":
    termo = input("Digite o termo de busca: ")
    fileName = input("Digite o nome do arquivo para salvar: ")
    path_name = f"{fileName}.jpg"  # Caminho completo com o nome do arquivo
    
    busca_imagens_pexels(termo, fileName, path_name)