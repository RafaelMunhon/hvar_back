import os
import subprocess
import traceback
from app.core.logger_config import setup_logger
import ffmpeg as ffmpeg_python

logger = setup_logger(__name__)

def extract_audio(video_path, audio_path):
    """
    Extrai o áudio do vídeo usando FFmpeg com configurações otimizadas.

    Tenta extrair o áudio do vídeo usando FFmpeg com configurações otimizadas.

    Retorna:
        bool: True se o áudio foi extraído com sucesso, False caso contrário    
    """
    try:
        logger.info(f"Extraindo áudio de {video_path} para {audio_path}")
        
        # Garante que o arquivo de saída tem extensão .wav
        if not audio_path.endswith('.wav'):
            audio_path = f"{audio_path}.wav"
            
        # Primeiro vamos verificar se os diretórios existem
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        
        # Configuração mais simples e robusta para extração de áudio
        stream = ffmpeg_python.input(video_path)
        stream = ffmpeg_python.output(
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
            logger.info(f"Comando FFmpeg: {' '.join(ffmpeg_python.compile(stream))}")
            
            out, err = ffmpeg_python.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            logger.info(f"Áudio extraído com sucesso: {audio_path}")
            
            # Verifica se o arquivo foi criado
            if os.path.exists(audio_path):
                file_size = os.path.getsize(audio_path)
                logger.info(f"Tamanho do arquivo de áudio: {file_size} bytes")
                return True
            else:
                logger.error("Arquivo de áudio não foi criado")
                return False
                
        except ffmpeg_python.Error as e:
            logger.error("Erro detalhado do FFmpeg:")
            logger.error(f"stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
            logger.error(f"stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
            raise
            
    except Exception as e:
        logger.error(f"Erro ao extrair áudio: {str(e)}")
        logger.error(f"Tipo do erro: {type(e).__name__}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False