import os
import logging
from google.cloud import speech_v1
from google.cloud import storage
from google.protobuf.duration_pb2 import Duration
from app import settings
from app.core.logger_config import setup_logger
import uuid
import time
import traceback
from app.videoPexel.text_processor import process_text
import ffmpeg

logger = setup_logger(__name__)

def extract_audio_from_video(video_path, audio_output_path):
    """
    Extrai o áudio de um vídeo e salva em um arquivo WAV.

    Args:
        video_path (str): Caminho completo para o arquivo de vídeo.
        audio_output_path (str): Caminho completo para salvar o áudio extraído. 

    Retorna:
        str: Caminho completo para o áudio extraído.
    """
    try:
        logger.info(f"=== Iniciando extração de áudio ===")
        logger.info(f"Vídeo de entrada: {video_path}")
        logger.info(f"Áudio de saída: {audio_output_path}")
        
        # Verifica se o vídeo existe
        if not os.path.exists(video_path):
            logger.error(f"Vídeo não encontrado: {video_path}")
            return None
            
        # Verifica se o diretório de saída existe
        os.makedirs(os.path.dirname(audio_output_path), exist_ok=True)
        
        logger.info("Configurando stream ffmpeg...")
        stream = (
            ffmpeg
            .input(video_path)
            .output(audio_output_path, 
                   acodec='pcm_s16le',  # Codec PCM 16-bit
                   ac=1,                # Mono channel
                   ar=16000)            # Sample rate 16kHz
            .overwrite_output()
        )
        
        # Log do comando que será executado
        cmd = ffmpeg.compile(stream)
        logger.info(f"Comando ffmpeg a ser executado: {' '.join(cmd)}")
        
        try:
            logger.info("Executando comando ffmpeg...")
            out, err = stream.run(capture_stdout=True, capture_stderr=True)
            logger.info(f"Áudio extraído e salvo em: {audio_output_path}")
            return audio_output_path
            
        except Exception as e:
            logger.error(f"Erro durante execução do ffmpeg: {str(e)}")
            logger.error(f"Tipo do erro: {type(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            if hasattr(e, 'stderr'):
                logger.error(f"Stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
            if hasattr(e, 'stdout'):
                logger.error(f"Stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
            return None
            
    except Exception as e:
        logger.error(f"Erro ao extrair áudio: {str(e)}")
        logger.error(f"Tipo do erro: {type(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


def transcribe_with_timestamps(audio_file_path):
    """
    Transcreve um arquivo de áudio com timestamps usando o Google Cloud Speech-to-Text (LongRunningRecognize).

    Args:
        audio_file_path (str): Caminho completo para o arquivo de áudio.

    Retorna:
        list: Lista de dicionários com as palavras transcritas e seus timestamps.
    """
    try:
        # Configurar credenciais        
        logger.info(f"Iniciando transcrição do arquivo: {audio_file_path}")
        
        # Verifica se o arquivo existe
        if not os.path.exists(audio_file_path):
            logger.error(f"Arquivo de áudio não encontrado: {audio_file_path}")
            return None
            
        # Log do tamanho do arquivo
        file_size = os.path.getsize(audio_file_path)
        logger.info(f"Tamanho do arquivo de áudio: {file_size} bytes")

        # Verifica formato do áudio
        probe = ffmpeg.probe(audio_file_path)
        audio_info = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        logger.info(f"Formato do áudio: {audio_info}")

        client = speech_v1.SpeechClient()
        storage_client = storage.Client()
        
        # Corrigindo o nome do bucket e definindo o prefixo do blob
        bucket_name = "conteudo-autenticare-videos"
        blob_prefix = "transcribe_with_timestamps"
        
        try:
            # Tenta obter o bucket
            bucket = storage_client.bucket(bucket_name)
            if not bucket.exists():
                logger.error(f"Bucket não existe: {bucket_name}")
                return None

        except Exception as e:
            logger.error(f"Erro ao acessar bucket: {str(e)}")
            return None

        # Geração de nome único para o arquivo
        unique_id = uuid.uuid4().hex
        blob_name = f"{blob_prefix}/{os.path.basename(audio_file_path)}-{unique_id}.wav"
        blob = bucket.blob(blob_name)

        # Upload do arquivo
        logger.info(f"Fazendo upload do arquivo para: gs://{bucket_name}/{blob_name}")
        blob.upload_from_filename(audio_file_path)
        gcs_uri = f"gs://{bucket_name}/{blob_name}"

        audio = speech_v1.RecognitionAudio(uri=gcs_uri)
        config = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="pt-BR",
            enable_word_time_offsets=True,
        )

        logger.info("Iniciando transcrição com configuração:")
        logger.info(f"URI: {gcs_uri}")
        logger.info(f"Sample Rate: 16000")
        logger.info(f"Encoding: LINEAR16")

        operation = client.long_running_recognize(config=config, audio=audio)
        logger.info("Transcrição iniciada, aguardando resultado...")

        try:
            response = operation.result(timeout=300)
            logger.info("Resposta recebida do Speech-to-Text")
            logger.info(f"Número de resultados: {len(response.results)}")
            
            transcricao_com_tempos = []
            for i, result in enumerate(response.results):
                logger.info(f"Processando resultado {i+1}/{len(response.results)}")
                for alternative in result.alternatives:
                    for word_info in alternative.words:
                        transcricao_com_tempos.append({
                            "word": word_info.word,
                            "start_time": word_info.start_time.total_seconds(),
                            "end_time": word_info.end_time.total_seconds()
                        })

            logger.info(f"Transcrição finalizada com {len(transcricao_com_tempos)} palavras")
            
            # Delete do arquivo do bucket
            blob.delete()
            return transcricao_com_tempos

        except Exception as e:
            logger.error(f"Erro durante a transcrição: {str(e)}")
            logger.error(f"Tipo do erro: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    except Exception as e:
        logger.error(f"Erro ao transcrever o áudio: {str(e)}")
        logger.error(f"Tipo do erro: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None
    
def transcribe_with_timestamps_v2(audio_file_path):
    """Transcreve um arquivo de áudio com timestamps usando o Google Cloud Speech-to-Text."""
    try:
        client = speech_v1.SpeechClient()
        
        # Carrega o arquivo de áudio
        with open(audio_file_path, "rb") as audio_file:
            content = audio_file.read()
        
        # Configura o reconhecimento
        audio = speech_v1.RecognitionAudio(content=content)
        config = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=44100,
            language_code="pt-BR",
            enable_word_time_offsets=True,
        )
        
        # Faz a transcrição
        operation = client.long_running_recognize(config=config, audio=audio)
        response = operation.result()
        
        # Processa os resultados
        transcricao_completa = []
        transcricao_com_tempos = []
        
        for result in response.results:
            for word_info in result.alternatives[0].words:
                word = word_info.word
                start_time = word_info.start_time.total_seconds()
                end_time = word_info.end_time.total_seconds()
                
                transcricao_completa.append(word)
                transcricao_com_tempos.append({
                    'word': word,
                    'start_time': start_time,
                    'end_time': end_time
                })
        
        return " ".join(transcricao_completa), transcricao_com_tempos

    except Exception as e:
        logger.error(f"Erro na transcrição: {str(e)}")
        return None, None

def transcrever_video_com_google_cloud(video_path, audio_path):
    """
    Transcreve um vídeo do Google Cloud Storage

    Args:
        video_path (str): Caminho do vídeo de entrada
        audio_path (str): Caminho do arquivo de saída   

    """
    try:
        # 1. Primeiro extrai o áudio do vídeo
        logger.info(f"Extraindo áudio do vídeo: {video_path}")
        if not os.path.exists(audio_path):
            success = extract_audio(video_path, audio_path)
            if not success:
                logger.error("Falha ao extrair áudio do vídeo")
                return None, None

        # 2. Faz a transcrição do áudio
        logger.info("Iniciando transcrição do áudio")
        client = speech_v1.SpeechClient()
        
        # Carrega o arquivo de áudio
        with open(audio_path, "rb") as audio_file:
            content = audio_file.read()
        
        # Configura o reconhecimento
        audio = speech_v1.RecognitionAudio(content=content)
        config = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=44100,
            language_code="pt-BR",
            enable_word_time_offsets=True,
        )
        
        # Faz a transcrição
        logger.info("Executando transcrição...")
        operation = client.long_running_recognize(config=config, audio=audio)
        response = operation.result()
        
        # Processa os resultados
        transcricao_completa = []
        transcricao_com_tempos = []
        
        for result in response.results:
            for word_info in result.alternatives[0].words:
                word = word_info.word
                start_time = word_info.start_time.total_seconds()
                end_time = word_info.end_time.total_seconds()
                
                transcricao_completa.append(word)
                transcricao_com_tempos.append({
                    'word': word,
                    'start_time': start_time,
                    'end_time': end_time
                })
        
        logger.info(f"Transcrição concluída com {len(transcricao_completa)} palavras")
        return " ".join(transcricao_completa), transcricao_com_tempos

    except Exception as e:
        logger.error(f"Erro na transcrição: {str(e)}")
        logger.error(f"Tipo do erro: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None, None

def extract_audio(video_path, audio_path):
    """
    Extrai o áudio do vídeo usando FFmpeg com configurações otimizadas

    Args:
        video_path (str): Caminho do vídeo de entrada
        audio_path (str): Caminho do arquivo de saída

    Retorna:
        bool: True se o áudio foi extraído com sucesso, False caso contrário
    """
    try:
        logger.info(f"FFmpeg package path: {ffmpeg.__file__}")
        
        logger.info(f"Extraindo áudio de {video_path} para {audio_path}")
        
        # Garante que o arquivo de saída tem extensão .wav
        if not audio_path.endswith('.wav'):
            audio_path = f"{audio_path}.wav"
            
        # Primeiro vamos verificar se os diretórios existem
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        
        # Configuração mais simples e robusta para extração de áudio
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(
            stream,
            audio_path,
            acodec='pcm_s16le',  # WAV sem compressão
            ac=1,                 # Mono
            ar='16000',          # Sample rate para Speech-to-Text
            sample_fmt='s16'     # Adicionando formato de amostra explícito
        )
        
        # Captura a saída do FFmpeg com mais detalhes
        try:
            logger.info("Iniciando processo FFmpeg...")
            logger.info(f"Comando FFmpeg: {' '.join(ffmpeg.compile(stream))}")
            
            out, err = ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            logger.info(f"Áudio extraído com sucesso: {audio_path}")
            
            # Verifica se o arquivo foi criado
            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(f"Tamanho do arquivo de áudio: {file_size} bytes")
                return True
            else:
                logger.error("Arquivo de áudio não foi criado")
                return False
                
        except ffmpeg.Error as e:
            logger.error("Erro detalhado do FFmpeg:")
            logger.error(f"stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
            logger.error(f"stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
            raise
            
    except Exception as e:
        logger.error(f"Erro ao extrair áudio: {str(e)}")
        logger.error(f"Tipo do erro: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

def upload_video_to_bucket(video_path):
    """
    Faz upload do vídeo processado para o bucket

    Args:
        video_path (str): Caminho do vídeo de entrada

    Retorna:
        str: URL pública do vídeo no bucket ou None em caso de erro

    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket('conteudo-autenticare-videos')
        blob_name = f"videos_processados/{os.path.basename(video_path)}"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(video_path)
        return f"https://storage.googleapis.com/conteudo-autenticare-videos/{blob_name}"
    except Exception as e:
        logger.error(f"Erro no upload do vídeo: {str(e)}")
        return None
    

def upload_audio_to_bucket(audio_path, bucket_name="yduqs-audio-web"):
    """
    Faz upload de um vídeo para o Google Cloud Storage.

    Args:
        video_path: Caminho local do arquivo de vídeo
        bucket_name: Nome do bucket do GCS (default: 'yduqs-audio-web')

    Returns:
        URL pública do vídeo no bucket ou None em caso de erro
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Nome do arquivo no bucket será o mesmo do video_path
        blob_name = os.path.basename(audio_path)
        blob = bucket.blob(blob_name)
        
        # Faz upload do arquivo
        blob.upload_from_filename(audio_path)
        logger.info(f"Vídeo enviado para o bucket: gs://{bucket_name}/{blob_name}")
        
        # Retorna URL pública do vídeo
        video_url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
        return video_url

    except Exception as e:
        logger.error(f"Erro ao fazer upload do vídeo: {str(e)}")
        logger.error(f"Detalhes do erro: {traceback.format_exc()}")
        return None