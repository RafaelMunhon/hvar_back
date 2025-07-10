import os
import re
import shutil
from app.config.ffmpeg import get_temp_files_path, get_temp_files_pexel_path
import subprocess

def remove_html_tags(text):
    """
    Remove todas as tags HTML de um texto.

    Recebe um texto que pode conter tags HTML e retorna o mesmo texto
    com todas as tags removidas, mantendo apenas o conteúdo textual.

    Args:
        text (str): O texto contendo possíveis tags HTML

    Returns:
        str: O texto limpo, sem as tags HTML
    """
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def adjust_text_for_duration(text, target_duration):
    """
    Ajusta um texto para caber em uma duração alvo.

    Recebe um texto e uma duração alvo em segundos, e ajusta o texto para que sua narração
    caiba aproximadamente nessa duração. O ajuste é feito estimando a velocidade média de
    fala em 1.8 palavras por segundo e truncando o texto se necessário.

    Args:
        text (str): O texto a ser ajustado
        target_duration (float): A duração alvo em segundos

    Returns:
        str: O texto ajustado para caber na duração alvo.
             Se o texto original já couber na duração, retorna o próprio texto.
    """
    palavras = len(text.split())
    duracao_estimada = palavras / 1.8  # Estimativa de palavras por segundo
    
    if duracao_estimada > target_duration:
        palavras_alvo = int(target_duration * 1.8)
        palavras_texto = text.split()
        texto_ajustado = ' '.join(palavras_texto[:palavras_alvo])
        return texto_ajustado
    return text

def clean_temp_folder():
    """
    Limpa a pasta temporária removendo todos os arquivos e subdiretórios.

    Remove todos os arquivos e subdiretórios dentro da pasta temporária definida em
    get_temp_files_path(). Útil para liberar espaço em disco e remover arquivos
    temporários que não são mais necessários.

    Args:
        None

    Returns:
        None
    """
    pasta_temp = get_temp_files_path()
    
    # Cria as pastas se não existirem
    os.makedirs(pasta_temp, exist_ok=True)
    
    # Lista todos os arquivos na pasta temp
    for filename in os.listdir(pasta_temp):
        file_path = os.path.join(pasta_temp, filename)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Erro ao deletar {file_path}: {e}')

def get_video_duration(video_path):
    """
    Obtém a duração de um arquivo de vídeo em segundos.

    Utiliza o ffprobe para extrair a duração do vídeo especificado.
    Executa um comando ffprobe que retorna apenas o valor da duração,
    sem formatação adicional.

    Args:
        video_path (str): Caminho do arquivo de vídeo

    Returns:
        float: Duração do vídeo em segundos se bem sucedido
        None: Em caso de erro ao obter a duração
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return float(result.stdout.strip())
        return None
    except Exception as e:
        print(f"Erro ao obter duração do vídeo: {e}")
        return None

def extract_main_term(text):
    """
    Extrai o termo principal de um texto, removendo caracteres especiais.

    Recebe um texto e retorna a primeira palavra encontrada após remover caracteres especiais
    e espaços extras. Se o texto estiver vazio ou não contiver palavras válidas, retorna "video".

    Args:
        text (str): O texto do qual extrair o termo principal

    Returns:
        str: A primeira palavra do texto processado ou "video" se o texto for inválido
    """
    if not text:
        return "video"
    
    # Remove caracteres especiais e espaços extras
    text = re.sub(r'[^\w\s]', '', text)
    words = text.split()
    
    # Retorna a primeira palavra ou "video" se não houver palavras
    return words[0] if words else "video"

def criar_diretorio_se_nao_existir(path):
    """
    Cria um diretório se ele não existir.

    Verifica se o diretório especificado existe e o cria caso não exista.
    Imprime uma mensagem informando quando um novo diretório é criado.

    Args:
        path (str): Caminho do diretório a ser verificado/criado

    Returns:
        str: O mesmo caminho passado como argumento
    """
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"Diretório criado: {path}")
    return path

def cleanup_temp_files(*files):
    """
    Remove arquivos temporários gerados durante o processamento.

    Recebe uma lista variável de arquivos ou listas de arquivos e tenta removê-los,
    preservando apenas os arquivos finais (que terminam com '_final.mp4').
    Imprime mensagens informando quais arquivos foram removidos ou preservados.

    Args:
        *files: Lista variável de strings com caminhos de arquivos ou listas/tuplas de caminhos.
               Cada argumento pode ser uma string com caminho de arquivo ou uma lista/tupla de caminhos.

    Returns:
        None
    """
    try:
        for file in files:
            if isinstance(file, (list, tuple)):
                for f in file:
                    cleanup_temp_files(f)
            elif file and isinstance(file, str) and os.path.exists(file):
                filename = os.path.basename(file).lower()
                if not filename.endswith('_final.mp4'):
                    try:
                        os.remove(file)
                        print(f"Arquivo temporário removido: {file}")
                    except Exception as e:
                        print(f"Erro ao remover {file}: {e}")
                else:
                    print(f"Preservando vídeo final: {file}")
    except Exception as e:
        print(f"Erro ao limpar arquivos temporários: {e}")