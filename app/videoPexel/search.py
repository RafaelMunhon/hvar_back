import re
import random
import os
import requests
from app import settings
from app.config.gemini_client import get_gemini_manager
from app.config.vertexAi import generate_content
from app.videoPexel.config import (
    VIDEO_FORMATS, PEXELS_API_KEY,
    PEXELS_API_URL, MIN_DURATION, MAX_DURATION
)
from app.config.ffmpeg import get_temp_files_path
from app.utils.verificaImagemVideo import analisar_video
from app.core.logger_config import setup_logger

logger = setup_logger(__name__)

ENVATO_API_KEY = "7BGGwCRsTuQCucq2Vq3yfqJodv3Rer4H"  # Substitua pela sua chave real

def is_video_orientation_valid(video, format_type):
    """
    Verifica se a orientação do vídeo é válida para o formato solicitado
    Args:
        video: dados do vídeo do Pexels
        format_type: 'desktop' ou 'mobile'
    Returns:
        bool: True se a orientação for válida, False caso contrário
    """
    for video_file in video.get('video_files', []):
        width = video_file.get('width', 0)
        height = video_file.get('height', 0)
        
        if width == 0 or height == 0:
            continue
            
        # Para desktop: largura deve ser maior que altura (horizontal/landscape)
        if format_type == 'desktop' and width <= height:
            return False
            
        # Para mobile: altura deve ser maior que largura (vertical/portrait)
        if format_type == 'mobile' and height <= width:
            return False
            
        return True
    
    return False

def extract_keywords(text):
    """
    Extrai palavras-chave relevantes de um texto, removendo stopwords e palavras duplicadas.

    Args:
        text (str): O texto do qual extrair as palavras-chave

    Returns:
        list: Lista de palavras-chave extraídas do texto, em minúsculas e sem duplicatas
    """
    # Lista de palavras para ignorar
    stopwords = {'o', 'a', 'os', 'as', 'um', 'uma', 'e', 'é', 'são', 'para', 'com', 'seu', 'sua', 'seus', 'suas'}

    # Remove pontuação e converte para minúsculas
    text = re.sub(r'[^\w\s]', ' ', text.lower())

    # Divide em palavras e remove stopwords
    words = [word for word in text.split() if word not in stopwords]

    # Identifica palavras-chave importantes (substantivos e adjetivos)
    keywords = []
    for word in words:
        if word not in keywords:  # Evita duplicatas
            keywords.append(word)

    return keywords

async def generate_search_queries(prompt, num_scenes=6):
    """
    Gera termos de busca em inglês para encontrar vídeos relacionados ao tema fornecido.

    Utiliza o Gemini para gerar termos de busca otimizados para encontrar vídeos stock
    que correspondam ao prompt fornecido. Gera múltiplos termos para permitir diferentes
    tentativas de busca.

    Args:
        prompt (str): O texto/tema para gerar os termos de busca
        num_scenes (int, optional): Número de termos de busca a serem gerados. Padrão é 6.

    Returns:
        list: Lista de strings contendo os termos de busca em inglês.
              Em caso de falha, retorna uma lista de termos padrão.
    """
    try:
        # Prompt para gerar as queries
        system_prompt = f"""
        Gere {num_scenes} termos de busca em inglês para encontrar vídeos relacionados ao tema:
        "{prompt}"
        
        Requisitos:
        - Termos curtos e diretos (2-5 palavras)
        - Relacionados ao tema principal
        - Sem aspas ou caracteres especiais
        - Apenas em inglês
        - Um termo por linha
        - Sem numeração
        - Incluir termos genéricos que tenham mais chance de encontrar vídeos (como 'business meeting', 'office work', 'people technology')
        - Variar entre termos específicos e genéricos
        - Incluir termos relacionados a pessoas, ambientes corporativos e tecnologia
        - Evitar termos muito específicos que possam limitar os resultados
        """

        manager = get_gemini_manager()
        response = await manager.generate_content(system_prompt, model=settings.GEMINI)
        if not response or not response:
            # Queries padrão em caso de falha
            default_queries = [
                "business technology",
                "office work",
                "corporate meeting",
                "professional team",
                "digital innovation",
                "modern workplace",
                "business presentation",
                "technology people",
                "office collaboration",
                "corporate success"
            ]
            return default_queries[:num_scenes]

        # Processa a resposta
        queries = [
            line.strip() for line in response.split('\n')
            if line.strip() and not line.strip().isdigit()
        ]

        # Garante que temos queries suficientes
        while len(queries) < num_scenes:
            if not queries:
                queries = default_queries
            queries.extend(queries)  # Duplica as queries existentes se precisar de mais

        return queries[:num_scenes]

    except Exception as e:
        print(f"Erro ao gerar queries: {str(e)}")
        # Retorna queries padrão em caso de erro
        default_queries = [
            "business technology",
            "office work",
            "corporate meeting",
            "professional team",
            "digital innovation",
            "modern workplace"
        ]
        return default_queries[:num_scenes]
    

def download_video(query, format_type, downloaded_ids, max_attempts=3, site=None):
    """
    Baixa um vídeo com base na query fornecida e no site especificado.

    Tenta baixar um vídeo com base na query fornecida e no site especificado.

    Retorna:
        str: URL do vídeo baixado
    """
    # Garantir que max_attempts seja inteiro
    max_attempts = int(max_attempts)
    
    if site and site.lower() == 'envato':
        return download_video_envato(query, format_type, downloaded_ids, max_attempts)
    else:
        return download_video_pexels(query, format_type, downloaded_ids, max_attempts)

def download_video_pexels(query, format_type, downloaded_ids, max_attempts=3):
    """
    Baixa um vídeo do Pexels com base nos parâmetros fornecidos.

    Args:
        query (str): Termo de busca para encontrar vídeos
        format_type (str): Formato do vídeo ('mobile' ou 'desktop')
        downloaded_ids (set): Conjunto de IDs de vídeos já baixados para evitar duplicatas
        max_attempts (int): Número máximo de tentativas de download

    Returns:
        str: Caminho do arquivo de vídeo baixado em caso de sucesso, None em caso de falha
    """
    # Garantir que max_attempts seja inteiro
    max_attempts = int(max_attempts)
    headers = {"Authorization": PEXELS_API_KEY}
    original_query = query
    attempt = 0
    cached_videos = []

    while attempt < max_attempts:
        try:
            if not cached_videos:
                print(f"\nBuscando vídeos no Pexels para: '{query}'")
                url = PEXELS_API_URL.format(query=query)
                print(f"URL da requisição: {url}")
                
                response = requests.get(url, headers=headers)
                print(f"Status da requisição: {response.status_code}")
                
                if response.status_code != 200:
                    raise Exception(f"Erro na requisição: {response.status_code}")
                    
                data = response.json()
                cached_videos = data.get('videos', [])
                print(f"Total de vídeos encontrados: {len(cached_videos)}")
                
                if not cached_videos:
                    attempt += 1
                    if attempt < max_attempts:
                        new_queries = generate_search_queries(original_query, 1)
                        if new_queries:
                            query = new_queries[0]
                            print(f"Tentando nova query: '{query}'")
                            continue
                    raise Exception("Nenhum vídeo encontrado")

            valid_videos = [
                video for video in cached_videos 
                if (
                    video.get('id') not in downloaded_ids and
                    MIN_DURATION <= video.get('duration', 0) <= MAX_DURATION and
                    is_video_orientation_valid(video, format_type)
                )
            ]
            
            if valid_videos:
                video = random.choice(valid_videos)
                return download_pexels_video(video, format_type)
                
            cached_videos = []
            attempt += 1
            
        except Exception as e:
            print(f"Erro ao baixar vídeo do Pexels: {str(e)}")
            attempt += 1
            
    return None

def download_video_envato(query, format_type, downloaded_ids, max_attempts=3):
    """
    Baixa um vídeo do Envato com base nos parâmetros fornecidos.

    Args:
        query (str): Termo de busca para encontrar vídeos
        format_type (str): Formato do vídeo ('mobile' ou 'desktop')
        downloaded_ids (set): Conjunto de IDs de vídeos já baixados para evitar duplicatas
        max_attempts (int): Número máximo de tentativas de download

    Returns:
        str: Caminho do arquivo de vídeo baixado em caso de sucesso, None em caso de falha
    """
    headers = {
                'Authorization': f'Bearer {ENVATO_API_KEY}',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0'
    }

    attempt = 0
    
    while attempt < max_attempts:
        try:
            print(f"\nBuscando vídeos no Envato para: '{query}'")
            
            response = requests.get(
                "https://api.envato.com/v1/discovery/search/search/item",
                headers=headers,
                params={
                    "term": query,
                    "site": "videohive.net",
                    "page": 1,
                    "page_size": 20,
                    "sort_by": "relevance"
                }
            )
            response.raise_for_status()
            
            resultados = response.json().get('matches', [])
            print(f"Total de vídeos encontrados no Envato: {len(resultados)}")
            
            if not resultados:
                attempt += 1
                if attempt < max_attempts:
                    new_queries = generate_search_queries(query, 1)
                    if new_queries:
                        query = new_queries[0]
                        print(f"Tentando nova query no Envato: '{query}'")
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
                    print(f"Nenhum preview de vídeo encontrado para o item {video_id}")
                    continue
                
                # Baixa o vídeo
                try:
                    video_filename = f"envato_{video_id}.mp4"
                    output_path = os.path.join(get_temp_files_path(), video_filename)
                    
                    print(f"Tentando baixar vídeo de: {preview_url}")
                    response = requests.get(preview_url, stream=True)
                    response.raise_for_status()
                    
                    with open(output_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    downloaded_ids.add(video_id)
                    print(f"Vídeo baixado com sucesso: {video_filename}")
                    return output_path
                    
                except Exception as e:
                    print(f"Erro ao baixar vídeo {video_id}: {str(e)}")
                    continue
            
            # Se chegou aqui, nenhum vídeo foi baixado com sucesso
            attempt += 1
            if attempt < max_attempts:
                new_queries = generate_search_queries(query, 1)
                if new_queries:
                    query = new_queries[0]
                    print(f"Tentando nova query no Envato: '{query}'")
                    
        except Exception as e:
            print(f"Erro ao buscar vídeos no Envato: {str(e)}")
            attempt += 1
            
    return None

def is_envato_video_valid(video, format_type):
    """
    Verifica se um vídeo do Envato atende aos critérios de formato e duração.

    Args:
        video (dict): Dicionário contendo os dados do vídeo do Envato
        format_type (str): Tipo de formato desejado ('mobile' ou 'desktop')

    Returns:
        bool: True se o vídeo é válido, False caso contrário
    """
    try:
        # Verificar atributos do vídeo
        attributes = video.get('attributes', [])
        duration = None
        width = None
        height = None
        
        for attr in attributes:
            if attr['name'] == 'duration':
                duration = float(attr['value'])
            elif attr['name'] == 'width':
                width = int(attr['value'])
            elif attr['name'] == 'height':
                height = int(attr['value'])
                
        if not all([duration, width, height]):
            return False
            
        # Verificar duração
        if not (MIN_DURATION <= duration <= MAX_DURATION):
            return False
            
        # Verificar orientação
        if format_type == 'mobile':
            return height > width  # Vertical
        else:
            return width > height  # Horizontal
            
    except Exception as e:
        print(f"Erro ao validar vídeo do Envato: {str(e)}")
        return False

def download_envato_video(video, format_type):
    """
    Baixa um vídeo do Envato com base nos parâmetros fornecidos.

    Args:
        video (dict): Dicionário contendo os dados do vídeo do Envato
        format_type (str): Tipo de formato desejado ('mobile' ou 'desktop')

    Returns:
        str: Caminho do arquivo de vídeo baixado em caso de sucesso, None em caso de falha
    """
    try:
        # Obter URL do preview do vídeo
        preview_url = None
        for preview in video.get('previews', []):
            if preview.get('type') == 'video':
                preview_url = preview.get('url')
                break
                
        if not preview_url:
            return None
            
        # Criar nome do arquivo
        video_filename = f"envato_{video['id']}.mp4"
        output_path = os.path.join(get_temp_files_path(), video_filename)
        
        # Baixar vídeo
        response = requests.get(preview_url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return output_path
        
    except Exception as e:
        print(f"Erro ao baixar vídeo do Envato: {str(e)}")
        return None

def search_videos(query, max_tentativas=5):
    """
    Busca vídeos no Pexels com verificação de qualidade e relevância.
    
    Args:
        query (str): Termo de busca
        max_tentativas (int): Número máximo de tentativas para encontrar um vídeo adequado
        
    Returns:
        dict: Informações do vídeo encontrado ou None se falhar
    """
    tentativas = 0
    videos_tentados = set()  # Para evitar repetições

    while tentativas < max_tentativas:
        tentativas += 1
        logger.info(f"Tentativa {tentativas} de {max_tentativas} para buscar vídeo")

        try:
            # Faz a busca no Pexels
            response = requests.get(
                f"{PEXELS_API_URL}/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={
                    "query": query,
                    "per_page": 30,
                    "orientation": "landscape",
                    "size": "large"
                }
            )
            response.raise_for_status()
            data = response.json()

            # Itera sobre os vídeos encontrados
            for video in data.get('videos', []):
                video_url = get_best_video_url(video)
                
                if not video_url or video_url in videos_tentados:
                    continue

                videos_tentados.add(video_url)
                
                # Analisa o vídeo
                analise = analisar_video(video_url, query)
                
                logger.info("Resultado da análise do vídeo:")
                logger.info(f"Descrição Gemini: {analise['descricao_gemini']}")
                logger.info(f"Corresponde: {analise['corresponde']}")
                logger.info(f"Confiança: {analise['confianca']*100}%")
                logger.info(f"Detalhes: {analise['detalhes']}")

                # Verifica se o vídeo é adequado
                if analise['corresponde'] and analise['confianca'] > 0.7:
                    logger.info("Vídeo validado e selecionado")
                    return {
                        'video_url': video_url,
                        'video_id': video['id'],
                        'duration': video['duration'],
                        'width': video['width'],
                        'height': video['height'],
                        'analise': analise
                    }
                else:
                    logger.warning("Vídeo não corresponde à descrição esperada ou confiança muito baixa")

            # Se chegou aqui, precisa reformular a busca
            query = reformular_termo_busca(query)

        except Exception as e:
            logger.error(f"Erro na busca: {e}")
            tentativas += 1

    logger.error(f"Todas as {max_tentativas} tentativas falharam para encontrar um vídeo adequado")
    return None

async def reformular_termo_busca(termo):
    """
    Reformula um termo de busca para melhorar os resultados na busca de vídeos.

    Utiliza o Gemini para gerar uma versão mais específica e profissional do termo de busca,
    otimizada para encontrar vídeos stock de alta qualidade.

    Args:
        termo (str): O termo de busca original que precisa ser reformulado

    Returns:
        str: O termo de busca reformulado e otimizado para busca de vídeos profissionais
    """
    prompt = f"""
    Preciso reformular o seguinte termo de busca para encontrar VÍDEOS PROFISSIONAIS: "{termo}"
    
    Por favor, sugira uma reformulação do termo que:
    1. Mantenha o significado principal
    2. Seja mais específico e descritivo
    3. Use termos que funcionem bem para busca de VÍDEOS STOCK
    4. Inclua detalhes visuais importantes
    5. Adicione termos como "professional video", "stock footage", "high quality"
    
    Retorne apenas o novo termo reformulado, sem explicações adicionais.
    """
    
    manager = get_gemini_manager()
    conteudo = await manager.generate_content(prompt, model=settings.GEMINI)
    novo_termo = conteudo.text
    logger.info(f"Termo reformulado pelo Gemini: {novo_termo}")
    return novo_termo

def get_best_video_url(video):
    """
    Obtém a URL do vídeo com a melhor qualidade disponível.

    Analisa os arquivos de vídeo disponíveis e retorna a URL do vídeo com a maior resolução.

    Args:
        video (dict): Dicionário contendo os dados do vídeo do Pexels, incluindo a lista de 'video_files'

    Returns:
        str: URL do vídeo com a melhor qualidade disponível, ou None se não houver vídeos disponíveis
    """
    if not video or 'video_files' not in video:
        return None
    # Ordena por qualidade (resolução) e pega o melhor
    video_files = sorted(
        video['video_files'],
        key=lambda x: (x.get('width', 0) * x.get('height', 0)),
        reverse=True
    )
    
    return video_files[0]['link'] if video_files else None

def download_pexels_video(video, format_type):
    """
    Baixa um vídeo do Pexels com base nos parâmetros fornecidos.

    Args:
        video (dict): Dicionário contendo os dados do vídeo do Pexels, incluindo a lista de 'video_files'
        format_type (str): Formato do vídeo ('mobile' ou 'desktop')

    Returns:
        str: Caminho do arquivo de vídeo baixado em caso de sucesso, None em caso de falha
    """
    try:
        # Encontra o melhor formato disponível
        best_format = None
        target_width = VIDEO_FORMATS[format_type]['width']
        target_height = VIDEO_FORMATS[format_type]['height']
        min_width = VIDEO_FORMATS[format_type]['min_width']
        min_height = VIDEO_FORMATS[format_type]['min_height']
        
        for video_file in video['video_files']:
            if (video_file['width'] >= min_width and video_file['height'] >= min_height):
                if not best_format or (
                    abs(video_file['width'] - target_width) < abs(best_format['width'] - target_width)
                ):
                    best_format = video_file
        
        if not best_format:
            raise Exception("Nenhum formato adequado encontrado")
            
        # Download do vídeo
        video_url = best_format['link']
        response = requests.get(video_url)
        response.raise_for_status()
        
        # Define o caminho para salvar o vídeo
        video_filename = f"pexels_{video['id']}.mp4"
        output_path = os.path.join(get_temp_files_path(), video_filename)
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
            
        return output_path
        
    except Exception as e:
        print(f"Erro ao baixar vídeo do Pexels: {str(e)}")
        return None