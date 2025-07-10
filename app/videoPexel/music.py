import subprocess
import requests
import os
import json
from app.config.ffmpeg import get_temp_files_path
from app.videoPexel.config import (
    JAMENDO_CLIENT_ID, JAMENDO_API_URL, JAMENDO_FORMATS,
    BACKGROUND_MUSIC_VOLUME
)
from app.videoPexel.utils import get_temp_files_pexel_path, get_video_duration

def download_background_music(style):
    """
    Baixa uma música de fundo do Jamendo com base no estilo especificado.

    Faz uma busca na API do Jamendo por músicas instrumentais do estilo fornecido,
    filtrando por músicas com duração adequada e fazendo o download da música selecionada.

    Args:
        style (str): Estilo musical desejado para a música de fundo (opcional)
                    Se não fornecido, busca apenas músicas instrumentais genéricas

    Returns:
        str: Caminho do arquivo de música baixado em caso de sucesso
        None: Em caso de falha no download ou se nenhuma música adequada for encontrada
    """
    try:
        print(f"\nBaixando música de fundo...")
        
        # Parâmetros para a busca de música
        params = {
            'client_id': JAMENDO_CLIENT_ID,
            'format': 'json',
            'limit': 100,
            'include': 'musicinfo',
            'audioformat': 'mp32',
            'tags': f'instrumental,{style}' if style else 'instrumental',
            'orderby': 'popularity_total'
        }

        # Faz a requisição para a API do Jamendo
        print("Buscando músicas...")
        response = requests.get(f"{JAMENDO_API_URL}/tracks/", params=params)
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {response.headers}")

        if response.status_code != 200:
            raise Exception(f"Erro ao buscar músicas: {response.status_code}")

        data = response.json()
        results = data.get('results', [])
        print(f"Músicas encontradas na primeira tentativa: {len(results)}")

        # Filtra músicas válidas
        valid_tracks = [
            track for track in results
            if track.get('audiodownload')
            and float(track.get('duration', 0)) >= 30
        ]
        print(f"Músicas válidas encontradas: {len(valid_tracks)}")

        if not valid_tracks:
            raise Exception("Nenhuma música válida encontrada")

        # Seleciona a primeira música válida
        track = valid_tracks[0]
        print(f"\nBaixando música: {track['name']} - {track['artist_name']}")
        print(f"Duração: {track['duration']} segundos")
        print(f"URL: {track['audiodownload']}")

        # Define o caminho para salvar a música
        pasta_arquivos_pexel = get_temp_files_path()
        music_path = os.path.join(pasta_arquivos_pexel, "background_music.mp3")

        # Baixa a música
        response = requests.get(track['audiodownload'])
        if response.status_code != 200:
            raise Exception("Erro ao baixar música")

        with open(music_path, 'wb') as f:
            f.write(response.content)

        print(f"Música baixada com sucesso: {len(response.content)} bytes")
        return music_path

    except Exception as e:
        print(f"Erro ao baixar música de fundo: {e}")
        return None

def prepare_background_music(music_path, target_duration, volume=0.1):
    """
    Prepara a música de fundo para um vídeo, ajustando sua duração e volume.

    Recebe uma música e a prepara para ser usada como background em um vídeo,
    fazendo os ajustes necessários de duração (repetindo se necessário) e volume.

    Args:
        music_path (str): Caminho do arquivo de música original
        target_duration (float): Duração desejada em segundos
        volume (float, optional): Volume da música (0.0 a 1.0). Padrão é 0.1

    Returns:
        str: Caminho do arquivo de música preparado em caso de sucesso
        None: Em caso de erro
    """
    try:
        print("\nPreparando música de fundo...")
        
        # Cria nome para arquivo temporário
        temp_dir = os.path.dirname(music_path)
        prepared_music = os.path.join(temp_dir, "prepared_music.mp3")
        
        # Obtém duração da música original
        music_duration = get_video_duration(music_path)
        print(f"Duração da música original: {music_duration:.2f}s")
        
        # Adiciona 10 segundos extras para garantir que a música cubra todo o vídeo
        target_duration_with_buffer = target_duration
        print(f"Duração necessária (com buffer): {target_duration_with_buffer:.2f}s")
        
        # Calcula quantas repetições são necessárias
        repeats = int(target_duration_with_buffer / music_duration) + 1
        print(f"Número de repetições necessárias: {repeats}")
        
        # Comando para preparar a música
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(repeats),  # Número de loops
            "-i", music_path,              # Arquivo de entrada
            "-t", str(target_duration_with_buffer),  # Duração com buffer
            "-af", f"volume={volume}",     # Ajusta volume
            prepared_music                 # Arquivo de saída
        ]
        
        print("Executando comando de preparação da música...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Erro ao preparar música: {result.stderr}")
            return None
            
        if not os.path.exists(prepared_music):
            print("Erro: Arquivo de música preparado não foi criado")
            return None
            
        print(f"Música preparada com sucesso: {prepared_music}")
        return prepared_music
        
    except Exception as e:
        print(f"Erro ao preparar música: {str(e)}")
        return None

def add_background_music(video_path, music_path, output_path, volume=0.1):
    """
    Adiciona música de fundo a um vídeo.

    Combina um vídeo com uma faixa de música de fundo, ajustando o volume da música
    e garantindo que ela cubra toda a duração do vídeo.

    Args:
        video_path (str): Caminho do arquivo de vídeo de entrada
        music_path (str): Caminho do arquivo de música de fundo
        output_path (str): Caminho onde o vídeo final será salvo
        volume (float, optional): Volume da música de fundo (0.0 a 1.0). Padrão é 0.1

    Returns:
        str: Caminho do vídeo com música adicionada em caso de sucesso
        None: Em caso de erro
    """
    try:
        print(f"\nAdicionando música de fundo ao vídeo: {video_path}")
        video_duration = get_video_duration(video_path)
        print(f"Duração do vídeo com narração: {video_duration:.2f}s")
        
        # Prepara a música
        prepared_music = prepare_background_music(music_path, video_duration, volume)
        if not prepared_music:
            return None
            
        # Verifica duração da música preparada
        music_duration = get_video_duration(prepared_music)
        print(f"Duração da música preparada: {music_duration:.2f}s")
        
        # Combina vídeo com música
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", prepared_music,
            "-filter_complex", 
            # Removido duration=first para não cortar no primeiro input
            "[0:a][1:a]amix=inputs=2[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            output_path
        ]
        
        print("\nComando ffmpeg para adicionar música:")
        print(" ".join(cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Erro ao adicionar música: {result.stderr}")
            return None
            
        print(f"Música adicionada com sucesso ao vídeo: {output_path}")
        print(f"Duração final do vídeo: {get_video_duration(output_path):.2f}s")
        
        return output_path

    except Exception as e:
        print(f"Erro ao adicionar música de fundo: {str(e)}")
        return None