import sys
import types
import logging
import os
import requests
import random
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from app.utils.verificaImagemVideo import analisar_imagem
from app.config.ffmpeg import get_temp_files_path
from googleapiclient.discovery import build
import urllib.parse
import json

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def busca_imagens(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao):
    """
    Função principal que tenta buscar imagens de múltiplas fontes
    """
    # Lista de fontes de imagens para tentar
    fontes = [
        busca_imagens_unsplash,
        busca_imagens_pexels,
        busca_imagens_pixabay,
        busca_imagens_google
    ]
    
    # Tenta cada fonte até encontrar uma imagem
    for fonte in fontes:
        try:
            resultado = fonte(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao)
            if resultado and len(resultado) > len(lista_imagens):
                # Se a fonte adicionou uma imagem, retorna o resultado
                return resultado
        except Exception as e:
            logger.error(f"Erro ao buscar imagem usando {fonte.__name__}: {str(e)}")
    
    # Se nenhuma fonte funcionou, cria uma imagem genérica
    logger.warning(f"Todas as fontes de imagens falharam. Criando imagem genérica para: {descricao_busca}")
    criar_imagem_generica(path_name, descricao_busca)
    lista_imagens.append({
        "nomeArquivo": filename_imagem,
        "momentoChave": momento_chave
    })
    return lista_imagens

def busca_imagens_google(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao, tentativa=0, max_tentativas=2):
    """
    Busca imagens no Google com mais tentativas e melhores termos de busca.
    Se falhar, cria uma imagem genérica.
    """
    try:
        # Verifica se já temos muitas imagens (limite para evitar sobrecarga)
        if len(lista_imagens) >= 20:
            logger.info(f"Limite de imagens atingido (20). Pulando busca para: {descricao_busca}")
            return lista_imagens
            
        # Verifica se o arquivo já existe
        if os.path.exists(path_name):
            logger.info(f"Imagem já existe: {path_name}")
            lista_imagens.append({
                "nomeArquivo": filename_imagem,
                "momentoChave": momento_chave
            })
            return lista_imagens
        
        # Tenta usar a API do Google
        try:
            # Melhora o termo de busca com base na tentativa
            termo_busca = melhorar_termo_busca(descricao_busca, tentativa)
            
            logger.info(f"Iniciando busca de imagens no Google com descrição: {termo_busca} (Tentativa {tentativa+1}/{max_tentativas})")
            
            # Verifica se as variáveis de ambiente estão configuradas
            #api_key = os.getenv("GOOGLE_API_KEY")
            #cse_id = os.getenv("GOOGLE_CSE_ID")

            api_key = 'AIzaSyAnPji2yfpk_CHxzjv8GVNeGY0i0AAkjSI'
            cse_id = 'e20fca32bd1874116'  # ID do mecanismo de pesquisa personalizado
            
            if not api_key or not cse_id:
                logger.error("Chave de API do Google ou ID CSE não configurados. Criando imagem genérica.")
                criar_imagem_generica(path_name, descricao_busca)
                lista_imagens.append({
                    "nomeArquivo": filename_imagem,
                    "momentoChave": momento_chave
                })
                return lista_imagens
            
            # Configuração da API de pesquisa personalizada do Google
            service = build("customsearch", "v1", developerKey=api_key)
            
            # Realiza a busca
            result = service.cse().list(
                q=termo_busca,
                cx=cse_id,
                searchType="image",
                num=1,
                imgType="photo",
                safe="active"
            ).execute()
            
            # Processa os resultados
            if "items" in result:
                for idx, item in enumerate(result["items"]):
                    image_url = item["link"]
                    try:
                        logger.info(f"Baixando imagem {idx+1} de {image_url} para: {path_name}")
                        response = requests.get(image_url, timeout=10)
                        
                        if response.status_code == 200:
                            with open(path_name, "wb") as file:
                                file.write(response.content)
                            
                            # Verifica se a imagem é adequada
                            analise = analisar_imagem(path_name, descricao_busca, transcricao)
                            
                            if analise.get("corresponde", False) or tentativa >= max_tentativas - 1:
                                logger.info(f"Imagem baixada com sucesso: {path_name}")
                                lista_imagens.append({
                                    "nomeArquivo": filename_imagem,
                                    "momentoChave": momento_chave
                                })
                                return lista_imagens
                            else:
                                logger.warning(f"Imagem {filename_imagem} não é adequada: {analise.get('detalhes', 'Sem detalhes')}")
                                # Continua para o próximo resultado
                        else:
                            logger.error(f"Erro ao baixar imagem {idx+1}: {response.status_code}")
                    except Exception as e:
                        logger.error(f"Erro ao processar imagem {idx+1}: {str(e)}")
            
            # Se chegou aqui, nenhuma imagem foi adequada ou não há resultados
            raise Exception("Nenhuma imagem adequada encontrada")
            
        except Exception as e:
            logger.error(f"Erro na API do Google: {str(e)}")
            # Se falhar na API do Google, tenta novamente ou cria uma imagem genérica
            if tentativa < max_tentativas - 1:
                return busca_imagens_google(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao, tentativa + 1, max_tentativas)
            else:
                logger.warning(f"Criando imagem genérica para: {descricao_busca}")
                criar_imagem_generica(path_name, descricao_busca)
                lista_imagens.append({
                    "nomeArquivo": filename_imagem,
                    "momentoChave": momento_chave
                })
                return lista_imagens
                
    except Exception as e:
        logger.error(f"Erro ao buscar imagem: {str(e)}")
        # Cria uma imagem genérica como último recurso
        logger.warning(f"Criando imagem genérica para: {descricao_busca}")
        criar_imagem_generica(path_name, descricao_busca)
        lista_imagens.append({
            "nomeArquivo": filename_imagem,
            "momentoChave": momento_chave
        })
        return lista_imagens

def melhorar_termo_busca(descricao_original, tentativa):
    """
    Melhora o termo de busca com base no número da tentativa
    """
    if tentativa == 0:
        return f"{descricao_original} high quality photo"
    elif tentativa == 1:
        return f"{descricao_original} professional photography -stock"
    elif tentativa == 2:
        return f"{descricao_original} illustration concept"
    elif tentativa == 3:
        return f"{descricao_original} vector graphic"
    else:
        return f"{descricao_original} {tentativa} high resolution"

def criar_imagem_generica(path_name, descricao_busca):
    """
    Cria uma imagem genérica com texto e elementos visuais quando não é possível encontrar uma imagem adequada.
    """
    try:
        # Cria uma imagem com gradiente
        width, height = 1280, 720
        image = Image.new('RGB', (width, height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Escolhe um estilo aleatório para variar as imagens
        estilo = random.choice(['gradiente', 'padrão', 'minimalista', 'geométrico'])
        
        if estilo == 'gradiente':
            # Cria um gradiente de fundo
            for y in range(height):
                # Varia as cores para criar diferentes gradientes
                r = int(40 + (y / height) * 20)
                g = int(10 + (y / height) * 40)
                b = int(60 + (y / height) * 80)
                
                for x in range(width):
                    draw.point((x, y), fill=(r, g, b))
                    
            # Adiciona uma borda decorativa
            draw.rectangle([(20, 20), (width-20, height-20)], outline=(255, 255, 255), width=2)
            
        elif estilo == 'padrão':
            # Cria um padrão de fundo com formas geométricas
            for i in range(0, width, 50):
                for j in range(0, height, 50):
                    # Varia as cores para criar um padrão interessante
                    r = (i * j) % 100 + 20
                    g = (i + j) % 80 + 10
                    b = (i - j) % 120 + 40
                    
                    # Desenha formas aleatórias
                    forma = random.choice(['círculo', 'quadrado', 'triângulo'])
                    
                    if forma == 'círculo':
                        draw.ellipse([(i, j), (i+30, j+30)], fill=(r, g, b, 100))
                    elif forma == 'quadrado':
                        draw.rectangle([(i, j), (i+30, j+30)], fill=(r, g, b, 100))
                    else:
                        draw.polygon([(i, j), (i+30, j), (i+15, j+30)], fill=(r, g, b, 100))
                        
        elif estilo == 'minimalista':
            # Fundo sólido com uma linha horizontal
            draw.rectangle([(0, 0), (width, height)], fill=(20, 20, 30))
            draw.rectangle([(0, height//2-2), (width, height//2+2)], fill=(255, 255, 255, 150))
            
        else:  # geométrico
            # Cria formas geométricas grandes
            for _ in range(5):
                x1 = random.randint(0, width)
                y1 = random.randint(0, height)
                x2 = random.randint(0, width)
                y2 = random.randint(0, height)
                
                r = random.randint(20, 100)
                g = random.randint(20, 100)
                b = random.randint(40, 150)
                
                forma = random.choice(['linha', 'retângulo', 'círculo'])
                
                if forma == 'linha':
                    draw.line([(x1, y1), (x2, y2)], fill=(r, g, b), width=5)
                elif forma == 'retângulo':
                    draw.rectangle([(x1, y1), (x2, y2)], outline=(r, g, b), width=3)
                else:
                    raio = min(abs(x2-x1), abs(y2-y1)) // 2
                    draw.ellipse([(x1, y1), (x1+raio*2, y1+raio*2)], outline=(r, g, b), width=3)
        
        # Adiciona o texto da descrição
        texto = descricao_busca
        
        # Adiciona um título
        titulo = "CONCEITO VISUAL"
        draw.text((width//2 - 100, 100), titulo, fill=(255, 255, 255))
        
        # Divide o texto em linhas para caber na imagem
        palavras = texto.split()
        linhas = []
        linha_atual = ""
        
        for palavra in palavras:
            if len(linha_atual + " " + palavra) <= 40:  # Limite de caracteres por linha
                linha_atual += " " + palavra if linha_atual else palavra
            else:
                linhas.append(linha_atual)
                linha_atual = palavra
        
        if linha_atual:
            linhas.append(linha_atual)
        
        # Desenha o texto centralizado
        y_text = height // 2 - (len(linhas) * 30) // 2
        
        for linha in linhas:
            # Calcula a posição x para centralizar o texto
            text_width = len(linha) * 15  # Estimativa grosseira
            x_text = (width - text_width) // 2
            
            # Desenha o texto com um contorno para melhor legibilidade
            # Sombra
            draw.text((x_text+2, y_text+2), linha, fill=(0, 0, 0))
            # Texto principal
            draw.text((x_text, y_text), linha, fill=(255, 255, 255))
            y_text += 30
        
        # Salva a imagem
        image.save(path_name)
        logger.info(f"Imagem genérica criada com sucesso: {path_name}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar imagem genérica: {str(e)}")
        # Tenta criar uma imagem ainda mais simples como último recurso
        try:
            image = Image.new('RGB', (1280, 720), color=(0, 0, 0))
            draw = ImageDraw.Draw(image)
            draw.text((640, 360), descricao_busca, fill=(255, 255, 255))
            image.save(path_name)
            return True
        except:
            return False

def modificar_descricao_busca(descricao_original, tentativa, analise=None):
    """
    Modifica a descrição de busca com base na tentativa atual e na análise da imagem anterior.
    
    Args:
        descricao_original: Descrição original
        tentativa: Número da tentativa atual
        analise: Resultado da análise da imagem anterior (opcional)
        
    Returns:
        Nova descrição de busca
    """
    # Se temos uma análise da imagem anterior, usamos para melhorar a busca
    if analise and 'detalhes' in analise and analise['detalhes']:
        logger.info(f"Modificando descrição com base na análise: {analise['detalhes']}")
        
        # Adicionar especificações com base nas discrepâncias
        discrepancias = analise['detalhes'].lower()
        
        # Adicionar termos específicos com base nas discrepâncias
        if "marca d'água" in discrepancias or "watermark" in discrepancias:
            return f"{descricao_original} -watermark -stock -shutterstock -getty -istock"
        
        if "ilustração" in discrepancias or "desenho" in discrepancias:
            return f"{descricao_original} real photo -illustration -drawing -cartoon"
        
        # Adicionar termos específicos com base na descrição do Gemini
        if 'descricao_gemini' in analise and analise['descricao_gemini']:
            elementos_faltantes = []
            for palavra in descricao_original.split():
                if len(palavra) > 3 and palavra.lower() not in analise['descricao_gemini'].lower():
                    elementos_faltantes.append(palavra)
            
            if elementos_faltantes:
                elementos_str = " ".join(elementos_faltantes)
                return f"{descricao_original} {elementos_str} high quality"
    
    # Modificações genéricas baseadas no número da tentativa
    if tentativa == 0:
        return f"{descricao_original} high quality photo"
    elif tentativa == 1:
        return f"{descricao_original} professional photography -stock"
    else:
        return f"{descricao_original} real photo high resolution {tentativa}"

def busca_imagens_unsplash(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao):
    """
    Busca imagens no Unsplash
    """
    try:
        # Verifica se já temos muitas imagens
        if len(lista_imagens) >= 20:
            return lista_imagens
            
        # Verifica se o arquivo já existe
        if os.path.exists(path_name):
            lista_imagens.append({
                "nomeArquivo": filename_imagem,
                "momentoChave": momento_chave
            })
            return lista_imagens
        
        # Chave de API do Unsplash (você precisa se registrar para obter uma)
        api_key = os.getenv("UNSPLASH_API_KEY")
        
        if not api_key:
            logger.warning("Chave de API do Unsplash não configurada")
            return lista_imagens
        
        # Prepara a consulta
        query = urllib.parse.quote(descricao_busca)
        url = f"https://api.unsplash.com/search/photos?query={query}&per_page=5&client_id={api_key}"
        
        # Faz a requisição
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if "results" in data and len(data["results"]) > 0:
                for result in data["results"]:
                    image_url = result["urls"]["regular"]
                    
                    try:
                        # Baixa a imagem
                        img_response = requests.get(image_url, timeout=10)
                        
                        if img_response.status_code == 200:
                            with open(path_name, "wb") as file:
                                file.write(img_response.content)
                            
                            # Verifica se a imagem é adequada
                            analise = analisar_imagem(path_name, descricao_busca, transcricao)
                            
                            if analise.get("corresponde", False):
                                logger.info(f"Imagem do Unsplash baixada com sucesso: {path_name}")
                                lista_imagens.append({
                                    "nomeArquivo": filename_imagem,
                                    "momentoChave": momento_chave
                                })
                                return lista_imagens
                    except Exception as e:
                        logger.error(f"Erro ao processar imagem do Unsplash: {str(e)}")
        
        return lista_imagens
    
    except Exception as e:
        logger.error(f"Erro ao buscar imagem no Unsplash: {str(e)}")
        return lista_imagens

def busca_imagens_pexels(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao):
    """
    Busca imagens no Pexels
    """
    try:
        # Verifica se já temos muitas imagens
        if len(lista_imagens) >= 20:
            return lista_imagens
            
        # Verifica se o arquivo já existe
        if os.path.exists(path_name):
            lista_imagens.append({
                "nomeArquivo": filename_imagem,
                "momentoChave": momento_chave
            })
            return lista_imagens
        
        # Chave de API do Pexels (você precisa se registrar para obter uma)
        api_key = os.getenv("PEXELS_API_KEY")
        
        if not api_key:
            logger.warning("Chave de API do Pexels não configurada")
            return lista_imagens
        
        # Prepara a consulta
        query = urllib.parse.quote(descricao_busca)
        url = f"https://api.pexels.com/v1/search?query={query}&per_page=5"
        
        # Faz a requisição
        headers = {
            "Authorization": api_key
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if "photos" in data and len(data["photos"]) > 0:
                for photo in data["photos"]:
                    image_url = photo["src"]["large"]
                    
                    try:
                        # Baixa a imagem
                        img_response = requests.get(image_url, timeout=10)
                        
                        if img_response.status_code == 200:
                            with open(path_name, "wb") as file:
                                file.write(img_response.content)
                            
                            # Verifica se a imagem é adequada
                            analise = analisar_imagem(path_name, descricao_busca, transcricao)
                            
                            if analise.get("corresponde", False):
                                logger.info(f"Imagem do Pexels baixada com sucesso: {path_name}")
                                lista_imagens.append({
                                    "nomeArquivo": filename_imagem,
                                    "momentoChave": momento_chave
                                })
                                return lista_imagens
                    except Exception as e:
                        logger.error(f"Erro ao processar imagem do Pexels: {str(e)}")
        
        return lista_imagens
    
    except Exception as e:
        logger.error(f"Erro ao buscar imagem no Pexels: {str(e)}")
        return lista_imagens

def busca_imagens_pixabay(lista_imagens, descricao_busca, filename_imagem, path_name, momento_chave, transcricao):
    """
    Busca imagens no Pixabay.
    """
    try:
        # Verifica se já temos muitas imagens
        if len(lista_imagens) >= 20:
            return lista_imagens
            
        # Verifica se o arquivo já existe
        if os.path.exists(path_name):
            lista_imagens.append({
                "nomeArquivo": filename_imagem,
                "momentoChave": momento_chave
            })
            return lista_imagens
        
        # Chave de API do Pixabay (você precisa se registrar para obter uma)
        api_key = os.getenv("PIXABAY_API_KEY")
        
        if not api_key:
            logger.warning("Chave de API do Pixabay não configurada")
            return lista_imagens
        
        # Prepara a consulta
        query = urllib.parse.quote(descricao_busca)
        url = f"https://pixabay.com/api/?key={api_key}&q={query}&image_type=photo&per_page=5"
        
        # Faz a requisição
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if "hits" in data and len(data["hits"]) > 0:
                for hit in data["hits"]:
                    try:
                        image_url = hit["largeImageURL"]
                        
                        # Baixa a imagem
                        img_response = requests.get(image_url, timeout=10)
                        
                        if img_response.status_code == 200:
                            with open(path_name, "wb") as file:
                                file.write(img_response.content)
                            
                            # Verifica se a imagem é adequada
                            analise = analisar_imagem(path_name, descricao_busca, transcricao)
                            
                            if analise.get("corresponde", False):
                                logger.info(f"Imagem do Pixabay baixada com sucesso: {path_name}")
                                lista_imagens.append({
                                    "nomeArquivo": filename_imagem,
                                    "momentoChave": momento_chave
                                })
                                return lista_imagens
                    except Exception as e:
                        logger.error(f"Erro ao processar imagem do Pixabay: {str(e)}")
        
        return lista_imagens
    
    except Exception as e:
        logger.error(f"Erro ao buscar imagem no Pixabay: {str(e)}")
        return lista_imagens


    
    