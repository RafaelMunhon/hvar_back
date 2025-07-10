from diffusers import StableDiffusionPipeline
import torch

# Carrega o modelo Stable Diffusion
modelo = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5", torch_dtype=torch.float16)
modelo = modelo.to("cuda")  # Use GPU para melhor desempenho

# Função para gerar imagem
def gerar_imagem(texto):
    try:
        # Gera a imagem
        imagem = modelo(texto).images[0]
        
        # Salva a imagem
        nome_arquivo = "imagem_gerada.png"
        imagem.save(nome_arquivo)
        print(f"Imagem salva como '{nome_arquivo}'.")
        
    except Exception as e:
        print(f"Erro ao gerar a imagem: {e}")

# Solicita o texto do usuário
texto_usuario = input("Digite o que você deseja gerar como imagem: ")

# Gera a imagem
gerar_imagem(texto_usuario)