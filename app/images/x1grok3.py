import requests
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def generate_image_grok(prompt: str) -> Optional[str]:
    """
    Gera uma imagem usando a API do Grok baseado em um prompt.
    
    Args:
        prompt (str): O texto descritivo para gerar a imagem
        
    Returns:
        Optional[str]: URL da imagem gerada ou None em caso de erro
    """
    try:
        url = "https://api.x.ai/v1/images/generations"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer xai-UWI69sHhmvodSwFfNUQBiBzdAe5QtfLdah6iby5Tqnx03rO9tt3IGG77stCAvnKlGezlzxTCis7t6hpN"
        }
        
        payload = {
            "prompt": prompt,
            "model": "dall-e-3",
            "n": 1,
            "size": "1024x1024"
        }

        logger.info(f"Fazendo requisição para X.AI com prompt: {prompt}")
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        logger.info("Resposta recebida do X.AI com sucesso")
        
        if "data" in result and len(result["data"]) > 0:
            return result["data"][0]["url"]
        else:
            logger.warning(f"Resposta inesperada da API: {result}")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na requisição para API X.AI: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao gerar imagem: {str(e)}")
        return None

if __name__ == "__main__":
    prompt = "gere uma imagem da formula de baskara "
    image_url = generate_image_grok(prompt)
    print(f"URL da imagem gerada: {image_url}")

