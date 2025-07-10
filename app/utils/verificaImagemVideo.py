from app import settings
from app.config.ffmpeg import get_temp_files_path
from app.config.vertexAi import generate_content
import vertexai
from vertexai.generative_models import GenerativeModel, Image
import logging
from app.core.logger_config import setup_logger
import os
from PIL import Image as PILImage
import io
import cv2

logger = setup_logger(__name__)

async def analisar_imagem(imagem_path, descricao_esperada, transcricao):
    """
    Analisa uma imagem usando o Google Gemini e verifica se ela corresponde à descrição esperada.
    
    Args:
        imagem_path (str): Caminho para o arquivo de imagem
        descricao_esperada (str): Descrição que esperamos encontrar na imagem
        
    Returns:
        dict: Dicionário com o resultado da análise
            {
                'corresponde': bool,  # True se a imagem corresponde à descrição
                'descricao_gemini': str,  # Descrição da imagem feita pelo Gemini
                'confianca': float,  # Nível de confiança (0-1)
                'detalhes': str  # Detalhes adicionais da análise
            }
    """
    try:
        # Verifica se o arquivo existe
        if not os.path.exists(imagem_path):
            logger.error(f"Arquivo não encontrado: {imagem_path}")
            return {
                'corresponde': False,
                'descricao_gemini': None,
                'confianca': 0,
                'detalhes': "Arquivo de imagem não encontrado"
            }

        # Carrega e prepara a imagem
        with PILImage.open(imagem_path) as img:
            # Converte para RGB se necessário
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Redimensiona se a imagem for muito grande
            max_size = (1024, 1024)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size)
            
            # Converte para bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()

        # Inicializa o modelo Gemini
        model = GenerativeModel(settings.GEMINI_VISION)
        
        # Prepara a imagem para o Gemini
        image = Image.from_bytes(img_byte_arr)

        # Prompt para o Gemini
        prompt = f"""
        Analise esta imagem em detalhes e responda:
        1. Esta é uma foto real ou uma ilustração/desenho/arte digital?
        2. Descreva os elementos principais da imagem.
        3. A imagem corresponde à seguinte descrição? "{descricao_esperada}"
        4. A imagem corresponde à seguinte a todo o contexto da transcrição? "{transcricao}"
        5. Qual o nível de confiança (0-100%) de que a imagem corresponde à descrição?
        6. Liste quaisquer discrepâncias entre a imagem e a descrição esperada.
        7. Não usar os termos: 'Ilustração:'
        8. Se tiver marca d'água e/ou site de origem, retorne 'Não corresponde'.

        Responda no seguinte formato:
        TIPO: [Foto Real/Ilustração]
        ELEMENTOS: [descrição dos elementos principais]
        CORRESPONDE: [Sim/Não]
        CONFIANÇA: [porcentagem]
        DISCREPÂNCIAS: [lista de discrepâncias, se houver]
        """

        # Faz a requisição ao Gemini
        response = model.generate_content(
            contents=[prompt, image],
            generation_config=settings.generation_config,
            safety_settings=settings.safety_settings
        )
        response_text = response.text if response else ""

        # Processa a resposta
        tipo_imagem = "Foto Real"  # valor padrão
        elementos = ""
        corresponde = False
        confianca = 0
        discrepancias = ""

        for linha in response_text.split('\n'):
            if linha.startswith('TIPO:'):
                tipo_imagem = linha.replace('TIPO:', '').strip()
            elif linha.startswith('ELEMENTOS:'):
                elementos = linha.replace('ELEMENTOS:', '').strip()
            elif linha.startswith('CORRESPONDE:'):
                corresponde = 'sim' in linha.lower()
            elif linha.startswith('CONFIANÇA:'):
                confianca = float(linha.replace('CONFIANÇA:', '').strip().replace('%', '')) / 100
            elif linha.startswith('DISCREPÂNCIAS:'):
                discrepancias = linha.replace('DISCREPÂNCIAS:', '').strip()

        # Se não for foto real, retorna não correspondência
        if "ilustração" in tipo_imagem.lower() or "desenho" in tipo_imagem.lower():
            return {
                'corresponde': False,
                'descricao_gemini': elementos,
                'confianca': 0,
                'detalhes': "A imagem é uma ilustração/desenho, mas precisamos de uma foto real"
            }

        return {
            'corresponde': corresponde,
            'descricao_gemini': elementos,
            'confianca': confianca,
            'detalhes': discrepancias
        }

    except Exception as e:
        logger.error(f"Erro ao analisar imagem: {str(e)}", exc_info=True)
        return {
            'corresponde': False,
            'descricao_gemini': None,
            'confianca': 0,
            'detalhes': f"Erro ao analisar imagem: {str(e)}"
        }

async def analisar_video(video_url, descricao_esperada):
    """
    Analisa um vídeo usando o Google Gemini e verifica se ele corresponde à descrição esperada.
    
    Args:
        video_url (str): URL do vídeo ou caminho do arquivo
        descricao_esperada (str): Descrição que esperamos encontrar no vídeo
        
    Returns:
        dict: Dicionário com o resultado da análise
    """
    try:
        # Extrai um frame do vídeo para análise
        cap = cv2.VideoCapture(video_url)
        success, frame = cap.read()
        if not success:
            return {
                'corresponde': False,
                'descricao_gemini': None,
                'confianca': 0,
                'detalhes': "Não foi possível extrair frame do vídeo"
            }

        # Salva o frame temporariamente
        temp_frame_path = os.path.join(get_temp_files_path(), f"{descricao_esperada}.jpg")
        
        cv2.imwrite(temp_frame_path, frame)
        cap.release()

        resultado = await analisar_imagem(temp_frame_path, descricao_esperada, '')
        os.remove(temp_frame_path)  # Remove o arquivo temporário

        return resultado

    except Exception as e:
        logger.error(f"Erro ao analisar vídeo: {str(e)}", exc_info=True)
        return {
            'corresponde': False,
            'descricao_gemini': None,
            'confianca': 0,
            'detalhes': f"Erro ao analisar vídeo: {str(e)}"
        }
