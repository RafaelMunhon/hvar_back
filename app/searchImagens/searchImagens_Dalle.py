import openai
import requests

# Configuração da API da OpenAI
openai.api_key = "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"  # Substitua pela sua chave da OpenAI

# Função para gerar imagem usando DALL·E
def gerar_imagem(texto):
    try:
        # Solicita a geração da imagem
        resposta = openai.Image.create(
            prompt=texto,  # Texto fornecido pelo usuário
            n=1,          # Número de imagens a serem geradas
            size="1024x1024"  # Tamanho da imagem
        )
        
        # Obtém a URL da imagem gerada
        url_imagem = resposta['data'][0]['url']
        print(f"Imagem gerada com sucesso! URL: {url_imagem}")
        
        # Faz o download da imagem
        nome_arquivo = "imagem_gerada.png"
        resposta_download = requests.get(url_imagem)
        with open(nome_arquivo, "wb") as arquivo:
            arquivo.write(resposta_download.content)
        print(f"Imagem salva como '{nome_arquivo}'.")
        
    except Exception as e:
        print(f"Erro ao gerar a imagem: {e}")

# Solicita o texto do usuário
texto_usuario = input("Digite o que você deseja gerar como imagem: ")

# Gera a imagem
gerar_imagem(texto_usuario)