import os
from google.cloud import texttospeech
from app.core.logger_config import setup_logger
from app.config.ffmpeg import get_temp_files_path

logger = setup_logger(__name__)

def generate_voiceover(text, voice='pt-BR-Standard-A', language_code='pt-BR'):
    """
    Gera narração usando Google Cloud Text-to-Speech
    
    Args:
        text: Texto para narração
        voice: Nome da voz ou ID da voz (default: pt-BR-Standard-A)
        language_code: Código do idioma (default: pt-BR)
    
    Returns:
        str: Caminho do arquivo de áudio gerado
    """
    try:
        logger.info("Iniciando geração de narração com Google TTS")
        logger.info(f"Usando voz: {voice}")
        
        # Se receber apenas um número, busca o nome real da voz
        if voice.isdigit():
            voices = get_available_voices()
            if voice in voices:
                voice = voices[voice]['name']
            else:
                voice = 'pt-BR-Standard-A'  # Voz padrão
        
        # Inicializa o cliente
        client = texttospeech.TextToSpeechClient()
        
        # Configura o texto de entrada
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Configura a voz
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice
        )
        
        # Configura o áudio
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
            pitch=0.0
        )
        
        # Realiza a síntese
        logger.info("Sintetizando áudio...")
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config
        )
        
        # Define o caminho do arquivo de saída
        output_path = os.path.join(get_temp_files_path(), "narration.wav")
        
        # Salva o arquivo de áudio
        with open(output_path, "wb") as out:
            out.write(response.audio_content)
            
        logger.info(f"Narração gerada com sucesso: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Erro ao gerar narração: {str(e)}")
        return None
    

def get_available_voices():
    """
    Obtém lista de vozes disponíveis no Google Cloud TTS com nomes brasileiros familiares.  

    Retorna:
        dict: Dicionário com as vozes disponíveis e seus detalhes   
    """
    try:
        client = texttospeech.TextToSpeechClient()
        response = client.list_voices(language_code='pt-BR')
        
        # Mapeamento de vozes para nomes brasileiros
        voice_names = {
            'pt-BR-Standard-A': {'name': 'Ana', 'gender': 'feminina'},
            'pt-BR-Standard-B': {'name': 'Bruno', 'gender': 'masculina'},
            'pt-BR-Standard-C': {'name': 'Carla', 'gender': 'feminina'},
            'pt-BR-Wavenet-A': {'name': 'Amanda', 'gender': 'feminina'},
            'pt-BR-Wavenet-B': {'name': 'Bernardo', 'gender': 'masculina'},
            'pt-BR-Wavenet-C': {'name': 'Clara', 'gender': 'feminina'},
            'pt-BR-Neural2-A': {'name': 'Alice', 'gender': 'feminina'},
            'pt-BR-Neural2-B': {'name': 'Beto', 'gender': 'masculina'},
            'pt-BR-Neural2-C': {'name': 'Carolina', 'gender': 'feminina'},
            # Adicione mais mapeamentos conforme necessário
        }
        
        available_voices = {}
        index = 1
        
        for voice in response.voices:
            # Verifica se a voz suporta português
            if any('pt-BR' in language_code for language_code in voice.language_codes):
                # Determina o tipo de voz
                voice_type = 'Natural'  # Padrão
                if 'WaveNet' in voice.name:
                    voice_type = 'Premium'
                elif 'Neural' in voice.name:
                    voice_type = 'Neural'
                
                # Busca informações do nome brasileiro
                voice_info = voice_names.get(voice.name, {
                    'name': voice.name.replace('pt-BR-', '').replace('-', ' '),
                    'gender': "feminina" if texttospeech.SsmlVoiceGender(voice.ssml_gender).name == "FEMALE" else "masculina"
                })
                
                voice_info = {
                    "name": voice.name,  # Nome original para API
                    "display": f"{voice_info['name']} ({voice_type})",  # Nome amigável com tipo
                    "gender": voice_info['gender']
                }
                
                available_voices[str(index)] = voice_info
                index += 1
        
        logger.info(f"Encontradas {len(available_voices)} vozes em português")
        return available_voices
        
    except Exception as e:
        logger.error(f"Erro ao listar vozes disponíveis: {str(e)}")
        return {}