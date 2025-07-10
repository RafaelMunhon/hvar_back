import os
import requests
import logging
from app.config.config import ENVATO_API_URL, ENVATO_HEADERS
from app.config.ffmpeg import get_envato_images_path, get_temp_files_path
from app.config.vertexAi import generate_content
from app.core.logger_config import setup_logger
from app.utils.verificaImagemVideo import analisar_imagem
import tempfile
from urllib.parse import urlparse
import uuid
import glob
import shutil
import traceback
import random
from app.videoPexel.search import generate_search_queries
from concurrent.futures import ThreadPoolExecutor
import threading

logger = setup_logger(__name__)

ENVATO_API_KEY = "7BGGwCRsTuQCucq2Vq3yfqJodv3Rer4H"  # Substitua pela sua chave real

# Lock para thread-safety ao adicionar imagens à lista
lista_imagens_lock = threading.Lock()

def reformular_termo_busca(termo):
    """Reformula o termo de busca para melhor resultado"""
    # Remove palavras que podem atrapalhar a busca
    termo = termo.lower()
    palavras_remover = ['o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas', 'de', 'da', 'do', 'das', 'dos']
    palavras = [p for p in termo.split() if p not in palavras_remover]
    
    # Adiciona palavras-chave que melhoram os resultados
    sufixos = ['illustration', 'concept', 'visual', 'design', 'modern']
    
    # Tenta diferentes combinações
    termo = ' '.join(palavras[:3])  # Usa no máximo 3 palavras principais
    termo += ' ' + random.choice(sufixos)  # Adiciona um sufixo aleatório
    
    logger.info(f"Termo reformulado: {termo}")
    return termo

def baixar_e_verificar_imagem(img_url, termo, headers=None):
    """Baixa a imagem e verifica se é adequada"""
    try:
        # Criar nome único para arquivo temporário
        temp_filename = f"temp_{str(uuid.uuid4())[:8]}.jpg"
        temp_path = os.path.join("app", "arquivosTemporarios", temp_filename)
        
        # Baixar imagem
        response = requests.get(img_url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Salvar temporariamente
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verificar adequação
        if analisar_imagem(temp_path, termo):
            return temp_path
        else:
            os.remove(temp_path)
            return None
            
    except Exception as e:
        logger.error(f"Erro ao baixar/verificar imagem {img_url}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def buscar_no_envato(termo):
    """Busca imagens no Envato"""
    try:
        headers = {
            'Authorization': f'Bearer {ENVATO_API_KEY}',
            'Accept': 'application/json',
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = requests.get(
            "https://api.envato.com/v1/discovery/search/search/item",
            headers=headers,
            params={
                "term": termo,
                "site": "photodune.net",
                "page": 1,
                "page_size": 30,
                "sort_by": "relevance"
            }
        )
        response.raise_for_status()
        
        resultados = response.json().get('matches', [])
        logger.info(f"Encontradas {len(resultados)} imagens para o termo: {termo}")
        return resultados
        
    except Exception as e:
        logger.error(f"Erro na busca Envato: {str(e)}")
        return []

def buscar_imagens_envato(lista_imagens, termo, fileName, path_name, momento_chave):
    """Busca imagens no Envato e retorna a primeira adequada"""
    try:
        logger.info("\n=== Iniciando busca de imagem ===")
        logger.info(f"Termo de busca: {termo}")
        logger.info(f"Nome do arquivo: {fileName}")
        logger.info(f"Caminho destino: {path_name}")
        logger.info(f"Momento chave: {momento_chave}")

        # Primeiro tenta com o termo original
        termo_atual = termo
        tentativas = 3
        max_tentativas = 10
        
        # Lista de palavras do termo original
        palavras = termo_atual.split()
        num_palavras = len(palavras)
        
        while tentativas < max_tentativas:
            logger.info(f"Tentando busca com termo: {termo_atual}")
            
            # Tenta buscar imagens
            resultados = buscar_no_envato(termo_atual)
            
            if not resultados:
                # Se não encontrou resultados, tenta reduzir o número de palavras
                if num_palavras > 2:  # Mantém pelo menos 2 palavras
                    num_palavras -= 1
                    termo_atual = ' '.join(palavras[:num_palavras])
                    logger.info(f"Reduzindo termo para: {termo_atual}")
                    continue
                
                # Se já tentou com 2 palavras, reformula o termo
                termo_atual = reformular_termo_busca(termo)
                palavras = termo_atual.split()
                num_palavras = len(palavras)
                tentativas += 1
                continue
            
            # Se encontrou resultados, processa a primeira imagem
            for resultado in resultados:
                image_urls = resultado.get('image_urls', [])
                
                # Encontrar melhor resolução disponível
                for resolucao in ['w1600', 'w1550', 'w1500', 'w1450', 'w1400', 'w1350', 'w1300', 
                                 'w1250', 'w1200', 'w1150', 'w1100', 'w1050', 'w1000', 'w900']:
                    for image in image_urls:
                        if image.get('name') == resolucao:
                            img_url = image.get('url')
                            if not img_url:
                                continue
                            
                            logger.info(f"Baixando e verificando imagem: {img_url}")
                            
                            # Baixar e verificar imagem
                            temp_path = baixar_e_verificar_imagem(img_url, termo)
                            
                            if temp_path:
                                logger.info("\n=== Imagem encontrada e verificada ===")
                                logger.info(f"URL da imagem: {img_url}")
                                logger.info(f"Caminho temporário: {temp_path}")
                                logger.info(f"Movendo para: {path_name}")

                                # Mover para destino final
                                os.makedirs(os.path.dirname(path_name), exist_ok=True)
                                os.rename(temp_path, path_name)
                                
                                # Adicionar à lista com os campos necessários
                                imagem_info = {
                                    "urlImg": img_url,
                                    "caminho": path_name,
                                    "momentoChave": momento_chave,
                                    "nomeArquivo": fileName,
                                    "x": 0,
                                    "y": 0,
                                    "start": 0,
                                    "end": 0
                                }
                                lista_imagens.append(imagem_info)
                                
                                logger.info("\n=== Dados da imagem adicionados ===")
                                logger.info(f"Informações da imagem: {imagem_info}")
                                logger.info(f"Total de imagens na lista: {len(lista_imagens)}")

                                return lista_imagens
                            else:
                                logger.info(f"Imagem não aprovada na verificação: {img_url}")
                                continue
            
            # Se chegou aqui, não encontrou imagem adequada com o termo atual
            if tentativas == 0:
                logger.info(f"Nenhuma imagem adequada encontrada para '{termo_atual}'. Reformulando termo...")
                termo_atual = reformular_termo_busca(termo)
                tentativas += 1
            else:
                tentativas += 1
                logger.info(f"Tentativa {tentativas} falhou. Reformulando termo novamente...")
                termo_atual = reformular_termo_busca(termo)
                
        return lista_imagens
        
    except Exception as e:
        logger.error(f": {e}")
        return lista_imagens

async def pre_processar_termos(cenas):
    """
    Pré-processa todos os termos de busca de uma vez usando VertexAI.
    
    Args:
        cenas (list): Lista de cenas do vídeo
        
    Returns:
        dict: Dicionário com termos originais e reformulados
    """
    termos = []
    for cena in cenas:
        if momento_chave := cena.get('momentoChave'):
            termos.append(momento_chave)
    
    if not termos:
        return {}
        
    prompt = f"""
    Reformule os seguintes termos para busca de imagens no Envato:
    {termos}
    
    Para cada termo:
    1. Traduza para inglês
    2. Use termos específicos para FOTOGRAFIAS REAIS
    3. Evite termos como "illustration", "drawing", "art"
    4. Adicione "photo" ou "photography" quando relevante
    5. Mantenha 3-7 palavras por termo
    
    Retorne apenas os termos reformulados, um por linha.
    """
    
    try:
        reformulados = await generate_content(prompt).text.strip().split('\n')
        return dict(zip(termos, reformulados))
    except Exception as e:
        logger.error(f"Erro no pré-processamento de termos: {e}")
        return {termo: termo for termo in termos}  # Fallback para termos originais

def processar_imagem_paralelo(termo_original, termo_reformulado, file_name, path_name):
    """
    Processa uma única imagem de forma paralela.
    
    Args:
        termo_original (str): Termo original da busca
        termo_reformulado (str): Termo reformulado para busca
        file_name (str): Nome do arquivo
        path_name (str): Caminho para salvar a imagem
    
    Returns:
        dict: Informações da imagem encontrada ou None
    """
    try:
        # Tenta primeiro com o termo reformulado
        resultado = buscar_imagens_envato([], termo_reformulado, file_name, path_name, termo_original)
        
        if not resultado:
            # Se não encontrar, tenta com o termo original
            resultado = buscar_imagens_envato([], termo_original, file_name, path_name, termo_original)
            
        return resultado[-1] if resultado else None
        
    except Exception as e:
        logger.error(f"Erro ao processar imagem para termo '{termo_original}': {e}")
        return None

def list_imagem_envato_otimizado(dados, lista_imagens):
    """
    Versão otimizada do processamento de imagens com pré-processamento e paralelismo.
    
    Args:
        dados (dict): Dados do JSON com as cenas
        lista_imagens (list): Lista atual de imagens
        
    Returns:
        list: Lista atualizada de imagens
    """
    try:
        # 1. Pré-processamento dos termos
        termos_reformulados = pre_processar_termos(dados.get('cenas', []))
        logger.info(f"Termos reformulados: {termos_reformulados}")
        
        # 2. Preparar tarefas para processamento paralelo
        tarefas = []
        for i, cena in enumerate(dados.get('cenas', [])):
            if momento_chave := cena.get('momentoChave'):
                file_name = f"envato_img_{len(lista_imagens) + i + 1}"
                path_name = os.path.join(get_envato_images_path(), f"{file_name}.jpg")
                
                termo_reformulado = termos_reformulados.get(momento_chave, momento_chave)
                tarefas.append((momento_chave, termo_reformulado, file_name, path_name))
        
        # 3. Processamento paralelo
        resultados = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(processar_imagem_paralelo, 
                              termo_original, termo_reformulado, 
                              file_name, path_name)
                for termo_original, termo_reformulado, file_name, path_name in tarefas
            ]
            
            for future in futures:
                try:
                    resultado = future.result()
                    if resultado:
                        with lista_imagens_lock:
                            lista_imagens.append(resultado)
                except Exception as e:
                    logger.error(f"Erro ao processar tarefa paralela: {e}")
        
        logger.info(f"Total de imagens encontradas: {len(lista_imagens)}")
        return lista_imagens
        
    except Exception as e:
        logger.error(f"Erro no processamento otimizado de imagens: {e}")
        return lista_imagens

def download_imagem(url, path, headers=None):
    """Faz o download da imagem"""
    try:
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info(f"Imagem baixada com sucesso: {path}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao baixar imagem {url}: {e}")
        return False

def busca_imagens_envato(lista_imagens, termo, fileName, path_name, momento_chave):
    """
    Função de compatibilidade para manter a API antiga funcionando.
    Apenas um alias para buscar_imagens_envato para manter compatibilidade.
    """
    return buscar_imagens_envato(lista_imagens, termo, fileName, path_name, momento_chave)

def buscar_videos_envato(query, format_type, downloaded_ids, max_attempts=3):
    """Busca vídeos no Envato usando a mesma lógica que funciona para imagens"""
    try:
        logger.info(f"Buscando vídeos no Envato para: '{query}'")
        
        # Configuração da API do Envato
        token = os.getenv('ENVATO_TOKEN')
        if not token:
            logger.error("Token do Envato não encontrado")
            return None

        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }

        # URL e parâmetros da busca
        url = "https://api.envato.com/v1/discovery/search/search/item"
        params = {
            'term': query,
            'site': 'videohive.net',
            'page': 1,
            'page_size': 20,
            'sort_by': 'relevance'
        }

        attempt = 0
        while attempt < max_attempts:
            try:
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                resultados = response.json().get('matches', [])
                logger.info(f"Total de vídeos encontrados no Envato: {len(resultados)}")
                
                if not resultados:
                    attempt += 1
                    if attempt < max_attempts:
                        new_queries = generate_search_queries(query, 1)
                        if new_queries:
                            query = new_queries[0]
                            logger.info(f"Tentando nova query no Envato: '{query}'")
                        continue
                    return None
                
                # Tenta cada vídeo encontrado
                for video in resultados:
                    video_id = str(video.get('id'))
                    if video_id in downloaded_ids:
                        continue
                    
                    # Verifica se tem preview de vídeo
                    preview_url = None
                    previews = video.get('previews', {}).get('icon_with_video_preview', {})
                    
                    # Tenta obter a URL do vídeo
                    preview_url = previews.get('video_preview_download_url')
                    if not preview_url:
                        preview_url = previews.get('video_url')
                    
                    if not preview_url:
                        logger.info(f"Nenhum preview de vídeo encontrado para o item {video_id}")
                        continue
                    
                    # Baixa o vídeo
                    try:
                        video_filename = f"envato_{video_id}.mp4"
                        output_path = os.path.join(get_temp_files_path(), video_filename)
                        
                        logger.info(f"Tentando baixar vídeo de: {preview_url}")
                        if download_video_envato(preview_url, output_path):
                            downloaded_ids.add(video_id)
                            logger.info(f"Vídeo baixado com sucesso: {video_filename}")
                            return output_path
                            
                    except Exception as e:
                        logger.error(f"Erro ao baixar vídeo {video_id}: {str(e)}")
                        continue
                
                # Se chegou aqui, nenhum vídeo foi baixado com sucesso
                attempt += 1
                if attempt < max_attempts:
                    new_queries = generate_search_queries(query, 1)
                    if new_queries:
                        query = new_queries[0]
                        logger.info(f"Tentando nova query no Envato: '{query}'")
                        
            except Exception as e:
                logger.error(f"Erro ao buscar vídeos no Envato: {str(e)}")
                attempt += 1
                
        return None

    except Exception as e:
        logger.error(f"Erro ao buscar vídeos no Envato: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def download_video_envato(video_url, output_path):
    """Faz download do vídeo do Envato"""
    try:
        token = os.getenv('ENVATO_TOKEN')
        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }

        # Faz o download do vídeo
        response = requests.get(video_url, headers=headers, stream=True)
        response.raise_for_status()

        # Salva o vídeo
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Vídeo baixado com sucesso: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Erro ao baixar vídeo do Envato: {str(e)}")
        return False

def get_videos_for_theme(theme, num_videos=6):
    """Obtém vídeos para o tema usando a nova implementação"""
    try:
        videos = buscar_videos_envato(theme)
        if not videos:
            logger.warning(f"Nenhum vídeo encontrado para '{theme}', tentando fallback")
            return get_fallback_videos()
            
        return videos[:num_videos]
        
    except Exception as e:
        logger.error(f"Erro ao obter vídeos: {str(e)}")
        return get_fallback_videos()

def get_fallback_videos():
    """Retorna lista de vídeos locais para fallback"""
    # Implemente a lógica de fallback aqui
    return []