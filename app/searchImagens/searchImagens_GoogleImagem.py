from vertexai.preview.vision_models import ImageGenerationModel
import vertexai
import os
from PIL import Image as PIL_Image
from PIL import ImageOps as PIL_ImageOps
from app.config.ffmpeg import get_temp_files_path
from app.settings import LOCATION, PROJECT_ID
from datetime import datetime
from dotenv import load_dotenv
from app.config.gcp_config import get_credentials_path
from google.oauth2 import service_account
from app.core.logger_config import setup_logger

logger = setup_logger(__name__)

def save_generated_image(image, filename_imagem):
    """
    Salva a imagem gerada no diretório especificado
    """
    try:        
        # Gera um nome único para o arquivo usando timestamp
        filepath = os.path.join(get_temp_files_path(), filename_imagem)
        
        # Converte e salva a imagem
        pil_image = image._pil_image
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
            
        pil_image.save(filepath)
        print(f"Imagem salva em: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"Erro ao salvar imagem: {e}")
        return None

def generate(lista_imagens, prompt, filename_imagem, path_name, momentoChave):
    """
    Gera uma imagem baseada no prompt fornecido
    """
    try:
        # Carrega as credenciais corretamente
        credentials_path = get_credentials_path()
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        
        # Inicializa o Vertex AI com as credenciais carregadas
        vertexai.init(
            project=PROJECT_ID, 
            location=LOCATION,
            credentials=credentials
        )
        
        print(f"Vertex AI inicializado com sucesso usando credenciais de: {credentials_path}")
        
        # Lista de modelos para tentar, em ordem de preferência
        models = [
            "imagen-3.0-fast-generate-001",
            "imagen-3.0-generate-002"
        ]
        
        last_error = None
        for model_name in models:
            try:
                print(f"Tentando usar o modelo: {model_name}")
                generation_model = ImageGenerationModel.from_pretrained(model_name)
                
                # Gera as imagens
                images = generation_model.generate_images(
                    prompt=prompt,
                    number_of_images=1,
                    aspect_ratio="4:3",
                    negative_prompt="",
                    person_generation="",
                    safety_filter_level="",
                    add_watermark=True,
                )
                
                if images:
                    print(f"Imagem gerada com sucesso usando o modelo: {model_name}")
                    save_generated_image(images[0], filename_imagem)

                    lista_imagens.append({
                        "nomeArquivo": filename_imagem,
                        "momentoChave": momentoChave,
                        "caminho": path_name
                    })
                    logger.info(f"lista_imagens dentro do if {lista_imagens}")
                    return lista_imagens
                    
            except Exception as e:
                print(f"Erro ao usar o modelo {model_name}: {str(e)}")
                last_error = e
                if "quota" not in str(e).lower():  # Se não for erro de quota, não tenta outro modelo
                    raise e
                continue
        
        if last_error:
            raise last_error  # Re-lança o último erro se nenhum modelo funcionou
        
        return None
        
    except Exception as e:
        print(f"Erro ao gerar imagem: {e}")
        import traceback
        print(f"Traceback completo:\n{traceback.format_exc()}")
        return None

# Exemplo de uso
# if __name__ == "__main__":
#     prompt = "ilustração de um homem com cabelo preto e barba"
#     filepath = generate_image(prompt)
#     if filepath:
#         print(f"Imagem gerada e salva com sucesso em: {filepath}")
#     else:
#         print("Falha ao gerar ou salvar a imagem")