import requests
import asyncio
import os
from translate import Translator
import logging
from app.config.config import UNSPLASH_API_KEY
from app.config.ffmpeg import get_unsplash_images_path

# Chave de acesso da API do Unsplash
API_KEY = "eWtKnUZrf-Y9Co8vcrVOxZ36IZmZpBfESFXNR_7Q8-I"
APP_ID = "702400"
SECRET_KEY = "8XrRJex4BWZhSraYpibaIgGwzatc6PVWk3ddGd7Fsao"

# URL da API do Unsplash
API_URL = "https://api.unsplash.com/photos/random"

# Cabeçalhos de autenticação
HEADERS = {
    "Authorization": f"Client-ID {API_KEY}"
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
    """Faz uma busca por imagens na API do Unsplash."""
    params = {
        "query": term,
        "orientation": "landscape",  # Exemplo de filtro: orientação paisagem
        "count": 10  # Número de imagens para retornar (aqui estamos pedindo 1)
    }

    try:
        response = requests.get(API_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        print(f"Resposta da API: {response.json()}")  # Adicionado para verificar a estrutura
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar imagens: {e}")
        return None


def selecionar_melhor_imagem(data, termo_busca):
    """Seleciona a melhor imagem baseada na descrição e qualidade."""
    print(f"Processando dados da API para '{termo_busca}'...")

    termo_busca_lower = termo_busca.lower()
    melhor_opcao = None

    for item in data:
        descricao = item.get('description', '').lower() if item.get('description') else ''
        print(f"Verificando item: {descricao}")

        # Verificar se o termo traduzido está na descrição
        if termo_busca_lower in descricao:
            print(f"Encontrado: ID = {item['id']}, Nome = {item['alt_description']}")
            return item['id'], item['alt_description'], item['user']['name'], item['urls']['regular']

        # Caso nenhuma descrição corresponda, salvar a primeira imagem como fallback
        if not melhor_opcao:
            melhor_opcao = (item['id'], item['alt_description'], item['user']['name'], item['urls']['regular'])

    if melhor_opcao:
        print("Nenhuma correspondência exata encontrada. Usando a primeira imagem disponível.")
        return melhor_opcao

    print("Nenhuma imagem encontrada com ou sem correspondência.")
    return None


def baixar_imagem(url_imagem, nome_arquivo):
    """Baixa a imagem do Unsplash e salva no arquivo."""
    try:
        img_response = requests.get(url_imagem, stream=True)
        img_response.raise_for_status()

        with open(nome_arquivo, "wb") as img_file:
            for chunk in img_response.iter_content(1024):
                img_file.write(chunk)
        print(f"Imagem baixada e salva como '{nome_arquivo}'")
    except requests.exceptions.RequestException as e:
        print(f"Erro ao baixar a imagem: {e}")


if __name__ == "__main__":
    termo = input("Digite o termo de busca (ex: 'Mãe e filha'): ").strip()
    #termo_traduzido = asyncio.run(traduzir_termo(termo))

    #print(f"Buscando imagens para '{termo}' (Traduzido: '{termo_traduzido}')...")

    resultado = buscar_imagens(termo)
    if resultado:
        imagem_id, nome_arquivo, autor, url_imagem = selecionar_melhor_imagem(resultado, termo)
        if imagem_id:
            print(f"Imagem encontrada: ID = {imagem_id}, Nome = {nome_arquivo}, Autor = {autor}")
            baixar_imagem(url_imagem, f"{nome_arquivo.replace(' ', '_')}.jpg")
        else:
            print("Nenhuma imagem encontrada para download.")
    else:
        print("Erro na busca ou sem resultados.")
