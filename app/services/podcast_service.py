from google.cloud import texttospeech
import logging
from datetime import datetime
from app.services.vertexai_service import melhorar_texto_com_gemini
from app.common import podcastprompt
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

def podcast(data, content_id, theme):
    try:
        logging.info("Iniciando processo de criação do Podcast.")
        texto = extrair_texto_do_json(data)
        if not texto:
            raise ValueError("JSON de entrada inválido ou sem conteúdo suficiente.")

        nome_arquivo_saida = gerar_nome_arquivo()
        audio_content = gerar_podcast(texto)

        relative_path = data.get('relative_path')
        output_dir = data.get('output_dir')
        if not relative_path or not output_dir:
            return {"success": False, "error": "relative_path ou output_dir não fornecidos"}

        url = salvar_arquivo_audio(nome_arquivo_saida, audio_content, relative_path, output_dir)

        if not url:
            return {"success": False, "error": "Erro ao salvar arquivo no bucket."}

        logging.info(f"Tentando salvar no banco de dados: ID={content_id}, URL={url}")
        if inserir_audio(content_id, url, "podcast", theme, nome_arquivo_saida):
            logging.info("Podcast salvo com sucesso no banco de dados")
            return {"success": True, "message": "Podcast gerado com sucesso!", "file_url": url}
        else:
            logging.warning("Podcast gerado mas não foi salvo no banco de dados")
            return {"success": True, "message": "Podcast gerado mas não salvo no BD", "file_url": url}

    except Exception as e:
        logging.error(f"Erro no processo de criação do Podcast: {str(e)}")
        return {"success": False, "error": "Erro interno ao criar Podcast."}

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
    return f"podcast_{timestamp}_{unique_id}.mp3"

def gerar_podcast(texto):
    try:
        logging.info("Criando o podcast.")
        client = texttospeech.TextToSpeechClient()

        logging.info("Gerando roteiro com Gemini.")
        prompt_roteiro = podcastprompt.cria_roteiro_prompt(texto)
        roteiro = melhorar_texto_com_gemini(prompt_roteiro)
        logging.info(f"Texto após Gemini:\n{roteiro}")
        logging.info("Roteiro gerado com sucesso.")

        audio_content = conversas_podcast(roteiro)
        return audio_content

    except Exception as e:
        logging.error(f"Erro ao criar podcast: {str(e)}")
        raise

# Define as vozes do professor e da aluna
def configurar_voz_professor():
    return texttospeech.VoiceSelectionParams(
        language_code="pt-BR",
        name="pt-BR-Standard-E"
    )

def configurar_voz_aluna():
    return texttospeech.VoiceSelectionParams(
        language_code="pt-BR",
        name="pt-BR-Wavenet-D"
    )

def configurar_audio():
    return texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0
    )

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

def conversas_podcast(roteiro):
    logging.info(f"Roteiro recebido:\n{roteiro}")
    # Extrai as falas do professor e da aluna
    linhas = roteiro.split('\n')
    falas = []
    for linha in linhas:
        linha = linha.strip()
        logging.info(f"Linha: {linha}")

        if linha.replace("**", "").startswith("Professor:"):
            texto_fala = linha[len("Professor:"):].strip()
            texto_ssml = formatar_texto_ssml(texto_fala)
            falas.append({"tipo": "Professor", "texto": texto_ssml})
        elif linha.replace("**", "").startswith("Aluno:"):
            texto_fala = linha[len("Aluno:"):].strip()
            texto_ssml = formatar_texto_ssml(texto_fala)
            falas.append({"tipo": "Aluno", "texto": texto_ssml})

    logging.info(f"Falas extraídas: {falas}")
    audio_content = b""
    for fala in falas:
        if fala["tipo"] == "Professor":
            voice = configurar_voz_professor()
            audio = audioclient(voice, fala["texto"], ssml=True)
            logging.info(f"Audio Professor Gerado: {len(audio)}")
            audio_content += audio
        elif fala["tipo"] == "Aluno":
            voice = configurar_voz_aluna()
            audio = audioclient(voice, fala["texto"], ssml=True)
            logging.info(f"Audio Aluno Gerado: {len(audio)}")
            audio_content += audio

    logging.info(f"Tamanho do audio_content: {len(audio_content)}")
    return audio_content

def formatar_texto_ssml(texto):
    texto_sem_asteriscos = texto.replace("*", "")
    texto_com_pausas = texto_sem_asteriscos.replace("[pausa]", '<break time="500ms"/>')
    return f"<speak>{texto_com_pausas}</speak>"

def audioclient(voice, texto, ssml = False):
    logging.info(f"Voz: {voice}, Texto: {texto}")
    client = texttospeech.TextToSpeechClient()
    if ssml:
        input_text = texttospeech.SynthesisInput(ssml=texto)
    else:
        input_text = texttospeech.SynthesisInput(text=texto)
    try:
        response = client.synthesize_speech(
            input=input_text,
            voice=voice,
            audio_config=configurar_audio()
        )
        logging.info(f"Tamanho do audio_content retornado: {len(response.audio_content)}")
        return response.audio_content
    except Exception as e:
        logging.error(f"Erro ao chamar synthesize_speech: {str(e)}")
        return b""