from app.bd.bd import inserir_video_pexel
from app.videoPexel.video_processing import process_videos
from app.videoPexel.config import DEFAULT_PROMPT
import os
from dotenv import load_dotenv
from app.videoPexel.text_processor import add_preserved_word
from app.core.logger_config import setup_logger
import asyncio
import edge_tts
import time
# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configurar logger
logger = setup_logger(__name__)


def get_music_style_name(style_number):
    """
    Converte o número do estilo musical para o nome correspondente.

    Tenta converter o número do estilo musical para o nome correspondente.

    Retorna:
        str: Nome do estilo musical
    """
    music_styles = {
        "1": "rock",
        "2": "electronic",
        "3": "jazz",
        "4": "classical",
        "5": "ambient",
        "6": "pop",
        "7": "funk",
        "8": "hiphop",
        "9": "reggae",
        "10": "latin",
        "11": "world",
        "12": "lounge",
        "13": "folk",
        "14": "blues"
    }
    return music_styles.get(str(style_number))

async def generate_video(format_type, theme_text, num_scenes, music_type, voice=None, site=None):
    """
    Gera um vídeo com os parâmetros especificados.
    
    Args:
        format_type (str): 'desktop' ou 'mobile'
        theme_text (str): Texto/tema do vídeo
        num_scenes (int): Número de cenas
        music_type (str): Tipo de música
        voice (str, optional): ID da voz para narração
        site (str, optional): Site de origem das imagens

    Retorna:
        dict: Dicionário com o resultado da geração do vídeo
    """
    logger.info("Iniciando geração do vídeo")
    logger.info(f"Formato: {format_type}")
    logger.info(f"Tema: {theme_text}")
    logger.info(f"Número de cenas: {num_scenes}")
    logger.info(f"Tipo de música (número): {music_type}")
    logger.info(f"Buscar no site: {site}")
    
    # Converte o número do estilo musical para o nome
    music_style = get_music_style_name(music_type)
    logger.info(f"Estilo musical convertido: {music_style}")

    try:
        # Configura o formato do vídeo
        os.environ["VIDEO_FORMAT"] = format_type

        # Define voz padrão se não especificada
        if not voice:
            voice = "pt-BR-FranciscaNeural"

        # Processa o vídeo e obtém a URL do bucket
        bucket_url = await process_videos(
            custom_prompt=theme_text,
            voice=voice,
            music_style=music_style,
            num_scenes=num_scenes,
            site=site
        )

        if bucket_url and isinstance(bucket_url, str):
            # Insere o registro no banco com a URL do bucket
            video_id = inserir_video_pexel(bucket_url, 'PEXEL')
            
            if video_id:
                return {
                    "status": "success",
                    "video_url": bucket_url,
                    "video_id": video_id,
                    "message": "Vídeo gerado e armazenado com sucesso"
                }
            else:
                return {
                    "status": "error",
                    "message": "Vídeo gerado mas falhou ao registrar no banco"
                }
        else:
            return {
                "status": "error",
                "message": "Falha ao gerar vídeo"
            }

    except Exception as e:
        logger.error(f"Erro ao gerar vídeo: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Erro ao gerar vídeo: {str(e)}"
        }

if __name__ == "__main__":
    generate_video()