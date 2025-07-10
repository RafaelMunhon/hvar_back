import asyncio
import os
from app.config import ffmpeg
import requests
import logging
from translate import Translator
from app.core import file_manager

# Token da API do Envato (substitua pelo seu)
API_TOKEN = "7BGGwCRsTuQCucq2Vq3yfqJodv3Rer4H"

# URL da API do Envato
API_URL = "https://api.envato.com/v1/discovery/search/search/item"

# Configurar cabeçalhos de autenticação
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def translate_text(text, src='pt', dest='en'):
    try:
        translator = Translator(from_lang=src, to_lang=dest)
        return translator.translate(text)
    except Exception as e:
        logging.error(f"Erro na tradução: {str(e)}")
        return text  # Retorna o texto original em caso de erro

async def traduzir_termo(termo):
    """Traduz o termo de busca para inglês."""
    traduzido = translate_text(termo)
    print(f"Traduzido para inglês: {traduzido}")
    return traduzido

def buscar_imagens(term):
    """Faz uma busca por imagens na API do Envato."""
    params = {
        "term": term,
        "site": "photodune.net",
        "price_min": 1,
        "sort_by": "relevance",  # Ordenar por relevância para obter os melhores resultados
        "sort_direction": "asc"
    }

    try:
        response = requests.get(API_URL, headers=HEADERS, params=params)
        response.raise_for_status()  # Levanta erro se houver falha HTTP
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar imagens: {e}")
        return None

def selecionar_melhor_imagem(data, termo_busca):
    """Seleciona a melhor imagem baseada na descrição e qualidade.
    Se nenhuma imagem correspondente for encontrada, retorna a primeira disponível."""
    for item in data.get('matches', []):
        # Tentar encontrar uma imagem que tenha o termo de busca na descrição
        if termo_busca.lower() in item.get('description', '').lower():
            image_urls = item.get("image_urls", [])
            if image_urls:
                melhor_imagem = max(image_urls, key=lambda img: img["width"])  # Escolher maior resolução
                return melhor_imagem['url'], item['name']
    
    # Caso nenhuma imagem tenha correspondido, pegar a primeira imagem disponível
    if data.get('matches'):
        primeiro_item = data['matches'][0]
        image_urls = primeiro_item.get("image_urls", [])
        if image_urls:
            return image_urls[0]['url'], primeiro_item['name']

    return None, None

def baixar_imagem(image_url, nome_arquivo):
    """Baixa uma imagem a partir da URL fornecida."""
    try:
        img_response = requests.get(image_url, stream=True)
        img_response.raise_for_status()

        pasta_imagens_envato = ffmpeg.get_envato_images_path()

        file_manager.criar_diretorio_se_nao_existir(pasta_imagens_envato)

        file_name = os.path.join(pasta_imagens_envato,nome_arquivo) 
        
        with open(f"{file_name}.jpg", "wb") as img_file:
            for chunk in img_response.iter_content(1024):
                img_file.write(chunk)
        print(f"Imagem salva como '{file_name}.jpg'")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar a imagem: {e}")

if __name__ == "__main__":
    termo = input("Digite o termo de busca (ex: 'Mãe e filha'): ").strip()
    termo_traduzido = asyncio.run(traduzir_termo(termo))

    print(f"Buscando imagens para '{termo}' (Traduzido: '{termo_traduzido}')...")

    resultado = buscar_imagens(termo_traduzido)
    if resultado:
        imagem_url, nome_arquivo = selecionar_melhor_imagem(resultado, termo_traduzido)
        if imagem_url:
            print(f"Imagem encontrada: {imagem_url}")
            baixar_imagem(imagem_url, termo.replace(" ", "_"))
        else:
            print(f"Nenhuma imagem encontrada para '{termo}', mas baixando a primeira imagem disponível.")
            imagem_url, nome_arquivo = selecionar_melhor_imagem(resultado, termo_traduzido)  # Fallback
            if imagem_url:
                baixar_imagem(imagem_url, nome_arquivo)
            else:
                print("Erro: Nenhuma imagem disponível para download.")
    else:
        print("Erro na busca ou sem resultados.")
