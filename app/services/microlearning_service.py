from google.cloud import texttospeech
import logging
from datetime import datetime
from app.services.vertexai_service import melhorar_texto_com_gemini
from app.common import microlearningprompt
import uuid
import re
import os
from app.services.speech_service import upload_audio_to_bucket
from app.bd.bd import inserir_audio

# Configuração do logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurações do GCS
PROJECT_ID = "conteudo-autenticare"
BUCKET_NAME = "conteudo-autenticare-audios"

def microlearning(data, content_id, theme):
    try:
        logging.info("Iniciando processo de criação do Microlearning.")
        texto = extrair_texto_do_json(data)
        if not texto:
            raise ValueError("JSON de entrada inválido ou sem conteúdo suficiente.")

        nome_arquivo_saida = gerar_nome_arquivo()
        audio_content = gerar_audiomicrolearning(texto)

        relative_path = data.get('relative_path')
        output_dir = data.get('output_dir')
        if not relative_path or not output_dir:
            return {"success": False, "error": "relative_path ou output_dir não fornecidos"}

        url = salvar_arquivo_audio(nome_arquivo_saida, audio_content, relative_path, output_dir)

        if not url:
            return {"success": False, "error": "Erro ao salvar arquivo no bucket."}

        logging.info(f"Tentando salvar no banco de dados: ID={content_id}, URL={url}")
        if inserir_audio(content_id, url, "microlearning", theme, nome_arquivo_saida):
            logging.info("Microlearning salvo com sucesso no banco de dados")
            return {"success": True, "message": "Microlearning gerado com sucesso!", "file_url": url}
        else:
            logging.warning("Microlearning gerado mas não foi salvo no banco de dados")
            return {"success": True, "message": "Microlearning gerado mas não salvo no BD", "file_url": url}

    except Exception as e:
        logging.error(f"Erro no processo de criação do Microlearning: {str(e)}")
        return {"success": False, "error": "Erro interno ao criar Microlearning."}

def extrair_texto_do_json(data):
    """Extrai o texto do JSON no formato do Strapi"""
    try:
        # Verifica se data é um JSON válido
        if not isinstance(data, dict):
            logging.error("Input não é um JSON válido")
            return None

        # Pega o conteúdo - ajustando a estrutura correta
        conteudo = data.get('conteudo', [])
        if not conteudo:
            logging.error("Array de conteúdo vazio")
            return None

        texto_completo = []

        # Processa cada componente
        for item in conteudo:
            # Processa qualquer componente que tenha texto ou conteúdo
            texto = None

            # Tenta obter o texto do campo 'texto' ou 'conteudo'
            if 'texto' in item:
                texto = item.get('texto', '')
            elif 'conteudo' in item:
                texto = item.get('conteudo', '')

            # Se encontrou texto, processa e adiciona
            if texto:
                # Remove tags HTML
                texto = re.sub(r'<[^>]+>', '', texto)
                if texto.strip():
                    texto_completo.append(texto.strip())

        # Junta todo o texto com espaços
        texto_final = ' '.join(texto_completo)

        if not texto_final:
            logging.error("Nenhum texto extraído do JSON")
            return None

        return texto_final

    except Exception as e:
        logging.error(f"Erro ao extrair texto do JSON: {str(e)}")
        return None

def gerar_nome_arquivo():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    return f"microlearning_{timestamp}_{unique_id}.mp3"

def gerar_audiomicrolearning(texto):
    try:
        logging.info("Criando o microlearning.")
        client = texttospeech.TextToSpeechClient()

        voice = configurar_voz()
        audio_config = configurar_audio()

        logging.info("Gerando roteiro com Gemini.")
        prompt_roteiro = microlearningprompt.microlearningprompt(texto)
        roteiro = melhorar_texto_com_gemini(prompt_roteiro)
        logging.info("Roteiro gerado com sucesso.")

        audio_content = sintetizar_audio(roteiro, client, voice, audio_config)
        return audio_content

    except Exception as e:
        logging.error(f"Erro ao criar Microlearning: {str(e)}")
        raise

def configurar_voz():
    return texttospeech.VoiceSelectionParams(
        language_code="pt-BR",
        name="pt-BR-Standard-E"
    )

def configurar_audio():
    return texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0
    )

def sintetizar_audio(roteiro, client, voice, audio_config):
    try:
        blocos = roteiro.split('[pausa]')
        audio_content = b""

        for bloco in blocos:
            if bloco.strip():
                logging.info(f"Processando bloco: {bloco.strip()}")
                ssml_text = f'<speak>{bloco.strip()}<break time="500ms"/></speak>'
                input_text = texttospeech.SynthesisInput(ssml=ssml_text)
                response = client.synthesize_speech(
                    input=input_text,
                    voice=voice,
                    audio_config=audio_config
                )
                audio_content += response.audio_content

        return audio_content
    except Exception as e:
        logging.error(f"Erro ao sintetizar áudio: {str(e)}")
        raise

def salvar_arquivo_audio(nome_arquivo_saida, audio_content, relative_path, output_dir):
    """Salva o arquivo de áudio no GCS."""
    try:
        # Limpa o nome do arquivo para evitar caracteres inválidos
        nome_arquivo_limpo = re.sub(r'[<>:"/\\|?*]', '', nome_arquivo_saida)

        # Define o caminho no bucket
        destination_blob_name = os.path.join(output_dir, relative_path, nome_arquivo_limpo).replace("\\", "/")

        # Cria um nome de arquivo temporário local
        temp_file_path = nome_arquivo_saida

        # Salva o conteúdo do áudio no arquivo temporário
        if audio_content:
            with open(temp_file_path, "wb") as out:
                out.write(audio_content)

        # Usa a mesma função que funciona para vídeos
        public_url = upload_audio_to_bucket(temp_file_path)

        # Remove o arquivo temporário local
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if public_url:
            logging.info(f"Arquivo {nome_arquivo_saida} foi uploadado para {destination_blob_name}")
            logging.info(f"URL pública: {public_url}")
            return public_url
        else:
            return None

    except Exception as e:
        logging.error(f"Erro ao fazer upload para o GCS: {str(e)}")
        return None