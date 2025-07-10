from datetime import datetime
import os
import subprocess
import requests
from app import settings
from app.config.gemini_client import get_gemini_manager
from dotenv import load_dotenv
import time
from app.config.vertexAi import generate_content
from app.core import file_manager
from app.editandoVideo.edicao_video import editandoVideo
from app.searchImagens import searchImagens_Envato, searchImagens_Google, searchImagens_GoogleImagem, searchImagens_Pexel
from app.services import vertexai_service
import json
from app.common import criaRoteiroPrompt
import re
from unidecode import unidecode
from pathlib import Path

import os

from app.core.logger_config import setup_logger
from app.config import ffmpeg as ffmpeg_config
import ffmpeg as ffmpeg_python
from app.config.config import HEYGEN_API_KEY, HEYGEN_HEADERS  # Importar configurações

logger = setup_logger(__name__)

pasta_videos_heygen = ffmpeg_config.get_videos_heygen_path()
file_manager.criar_diretorio_se_nao_existir(pasta_videos_heygen)

# Carregar variáveis do arquivo .env
load_dotenv()

def aguardar_geracao_video(video_id, headers):
    """
    Aguarda a conclusão da geração do vídeo.

    Recebe:
    - video_id: ID do vídeo
    - headers: Headers para requisição  

    Retorna:
    - URL do vídeo gerado
    """
    video_status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"

    while True:
        response = requests.get(video_status_url, headers=headers)
        status = response.json()["data"]["status"]

        if status == "completed":
            return response.json()["data"]["video_url"]
        elif status == "processing" or status == "pending":
            print("Vídeo ainda sendo processado. Verificando status...")
            time.sleep(10)
        elif status == "failed":
            print(f"A geração do vídeo falhou. '{response.json() ['data']['error']}'")
            return None


def salvar_video(video_url, filename, caminho_destino=None):
    """
    Salva o vídeo em um arquivo, adicionando verificação de integridade.
    
    Args:
        video_url (str): A URL do vídeo.
        filename (str): O nome do arquivo para salvar o vídeo.
        caminho_destino (str): (Opcional) local que o video sera salvo por padrao no metodo

    Returns:
        bool|None: `True` se o video for salvo corretamente, `None` caso contrário
    """
    try:
       
        if caminho_destino is None:  #Usar o filename caso não existe caminho destino.
              caminho_final = filename
        else:
              caminho_final = os.path.join(caminho_destino,filename)   # Cria caminho usando parametro opcional com join, que é ideal

        logger.info(f"Iniciando download do vídeo: {video_url} para {caminho_final}")
        response = requests.get(video_url, stream=True, verify=False)
        response.raise_for_status()  # Verifica se houve erros HTTP
         
        total_size = int(response.headers.get('content-length', 0)) # Obter o tamanho do vídeo no header, ele pode ser `None`, por isso o segundo argumento.

        if total_size == 0:
           logger.warning("Não foi possível obter o tamanho do arquivo do cabeçalho HTTP. Prosseguindo sem verificação de tamanho.")

        bytes_baixados = 0
        
        with open(caminho_final, "wb") as video_file:
              for chunk in response.iter_content(chunk_size=8192):
                  video_file.write(chunk)
                  bytes_baixados += len(chunk)

            
        if total_size > 0:
              if bytes_baixados == total_size:
                   logger.info(f"Vídeo baixado e salvo com sucesso, e tamanho correto: {caminho_final}")
                   return True # Retornando quando estiver tudo OK
              else:
                 logger.warning(f"Vídeo baixado e salvo. O tamanho do arquivo difere do tamanho informado no cabeçalho. O download pode estar incompleto: {caminho_final}. Baixados {bytes_baixados}, Total {total_size}")

        else:
              logger.info(f"Vídeo baixado e salvo: {caminho_final}")
              return True

        return None

    except requests.exceptions.RequestException as e:
         logger.error(f"Erro ao baixar vídeo da URL {video_url}: {e}")
         return None
    except Exception as e:
          logger.error(f"Erro ao salvar vídeo no arquivo {caminho_final}: {e}")
          return None


async def gerar_video_template_3_roteiro(data, buscaImagem, avatar_number, id, theme, titulo_nc):
    """
    Gera um vídeo usando um template pré-definido e um roteiro.

    Recebe:
    - data: Dados para gerar o roteiro
    - buscaImagem: Lista de imagens para overlay
    - avatar_number: Número do avatar a ser usado
    - id: Identificador único do vídeo
    - theme: Tema visual a ser aplicado
    - titulo_nc: Título do conteúdo

    Retorna:
    - URL do vídeo gerado   
    """
    if not HEYGEN_API_KEY:
        logger.error("HEYGEN_API_KEY não configurada!")
        return None
        
    try:
        logger.info("Iniciando geração de vídeo com HeyGen")
        logger.info(f"Template: {buscaImagem}")
        logger.info(f"avatar_number: {avatar_number}")
        
        # Verifica se data é None
        if data is None:
            logger.error("Dados recebidos são None")
            return None

        # Verifica se data é um dicionário
        if not isinstance(data, dict):
            logger.error(f"Dados recebidos não são um dicionário. Tipo: {type(data)}")
            try:
                # Tenta converter para dicionário se for string JSON
                if isinstance(data, str):
                    data = json.loads(data)
                else:
                    logger.error("Não foi possível converter os dados para dicionário")
                    return None
            except Exception as e:
                logger.error(f"Erro ao converter dados: {e}")
                return None

        template_id, num_cenas = get_template_id(avatar_number)
        logger.info(f"template_id: {template_id}")
        logger.info(f"num_cenas: {num_cenas}")

        # Usa o novo método que faz as tentativas
        dados = await gerarRoteiroComVerificacao(data, num_cenas)
        if not dados:
            logger.error("Não foi possível gerar um roteiro válido")
            return None

        if buscaImagem:
            #inicio busca Imagem Envato
            lista_imagens = []
            lista_imagens = list_imagem_envato(dados,lista_imagens)
            logger.info(f"lista_imagens list_imagem_envato: {lista_imagens}")
        else:
            lista_imagens = []

        #fim busca Imagem Envato
        
        # Log da API Key e Headers
        logger.info(f"API Key configurada: {'Sim' if HEYGEN_API_KEY else 'Não'}")
        logger.info(f"API Key: {HEYGEN_API_KEY[:10]}...") # Mostra só o início da key
        
        # Usa os headers globais
        headers = HEYGEN_HEADERS
        logger.info(f"Headers para requisição: {headers}")

        payload = criaRoteiroPrompt.criar_payload_heygen_template_3(dados)
        logger.info("Payload criado com sucesso")

        generate_url = f"https://api.heygen.com/v2/template/{template_id}/generate"
        logger.info(f"URL da requisição: {generate_url}")

        try:
            # Desabilitar a verificação de certificado SSL (não recomendado para produção)
            response = requests.post(generate_url, headers=headers, json=payload, verify=False)
            
            logger.info(f"Status code da resposta: {response.status_code}")
            logger.info(f"Resposta da API: {response.text}")

            if response.status_code != 200:
                logger.error(f"Erro na API HeyGen: {response.status_code} - {response.text}")
                return None  # ou lance uma exceção

            video_data = response.json()["data"] # Resposta do Heygen
            video_id = video_data["video_id"]
            logger.info(f"Vídeo gerado com sucesso! ID: {video_id}")

            video_url = aguardar_geracao_video(video_id, headers) # Aguarda a conclusão do processamento

            if video_url:
                logger.info(f"Vídeo pronto! URL: {video_url}")
                # salva video se teve resultado na url.
                filename_video = f"video_{datetime.now().strftime('%Y%m%dT%H%M%S')}.mp4"
                salvou_video = salvar_video(video_url, filename_video, pasta_videos_heygen)
                if salvou_video is True:
                    logger.info(f"Video foi salvo com sucesso, na uri: {video_url}")
                    editandoVideo(filename_video, dados, lista_imagens, buscaImagem, id, theme, titulo_nc)
                else:
                    logger.error("Video não salvo! Um problema ocorreu, verifique os logs")
                
                return video_url

            else:
                logger.error("Falha na geração do vídeo.")
                return None
            
        except Exception as e:
            logger.error(f"Erro ao fazer requisição para API HeyGen: {str(e)}")
            return None
        
    except Exception as e:
        logger.error(f"Erro ao gerar vídeo: {str(e)}")
        return None
    
def verificar_continuacao():
    controle = os.path.join(ffmpeg_config.get_temp_files_path(), "controle.txt")

    with open(controle, 'r') as f:
        status = f.read().strip()
        return status.lower() == 'continuar'

def list_imagem_envato(json_data, lista_imagens):
    """
    Lista imagens a partir de uma descrição de busca.

    Recebe:
    - json_data: Dados para gerar o roteiro
    - lista_imagens: Lista de imagens

    Retorna:
    - Lista de imagens
    """

    pasta_arquivos_temporarios = ffmpeg_config.get_temp_files_path()
    file_manager.criar_diretorio_se_nao_existir(pasta_arquivos_temporarios)

    for script in json_data["cenas"]:
        script_completo = ' '.join(script["script"])
        logger.info(f"script_completo: {script_completo}")

    for imagem in json_data["imagens"]:
                logger.info(f"Imagem: {imagem}")
                # Verifica se 'urlimg' existe e é uma string
                if 'descricaoBuscaEnvato' in imagem and isinstance(imagem.get('descricaoBuscaEnvato'), str):
                    
                    # Extrair nome base da URL
                    url_img_base = os.path.basename(imagem["descricaoBuscaEnvato"])  # Pega a url para extrair a parte que nomeia as fotos.
                    logger.info(f"url_img_base: {url_img_base}")
                    nome_base_imagem_aux = url_img_base.replace(' ', '_')
                    nome_base_imagem = nome_base_imagem_aux.split('.')[0] # Tira o .jpg .jpeg ou qualquer outro do nome.
                    
                    momento_chave = imagem.get('momentoChave', None)
                    filename_imagem = f"{nome_base_imagem}.jpg"  # Utilizando o nome customizado e sempre salva como png
                    path_name = os.path.join(pasta_arquivos_temporarios, f"{nome_base_imagem}.jpg")

                    # Tenta buscar no Envato
                    #lista_imagens_atualizada = searchImagens_Envato.buscar_imagens_envato(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
                    #lista_imagens_atualizada =searchImagens_Pexel.busca_imagens_pexels(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
                    #lista_imagens_atualizada = searchImagens_Google.busca_imagens_google(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave, script_completo)
                    lista_imagens_atualizada = searchImagens_GoogleImagem.generate(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
                    logger.info(f"lista_imagens_atualizada: {len(lista_imagens_atualizada)}")
                    logger.info(f"lista_imagens: {len(lista_imagens)}")
                    
                    # Se não retornou todas as imagens, tenta buscar novamente
                    if len(lista_imagens_atualizada) < len(json_data["imagens"]):
                        logger.info(f"Tentando buscar no Pexels")
                        #lista_imagens = searchImagens_Pexel.busca_imagens_pexels(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
                        lista_imagens = searchImagens_Google.busca_imagens_google(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave, script_completo)

                    lista_imagens = lista_imagens_atualizada
                        #lista_imagens = searchImagens_Pexel.busca_imagens_pexels(lista_imagens, imagem.get('descricaoBuscaEnvato'), filename_imagem, path_name, momento_chave)
    return lista_imagens


def get_video_duration(video_path):
    """
    Obtém a duração de um arquivo de vídeo em segundos.

    Recebe:
        video_path (str): Caminho completo para o arquivo de vídeo.

    Retorna:
        float|None: Duração do vídeo em segundos se bem sucedido, None caso contrário.
    """
    if not os.path.exists(video_path):
        logger.error(f"Arquivo de vídeo não encontrado: {video_path}")
        return None

    try:
        # Tenta primeiro usar ffmpeg-python
        try:
            probe = ffmpeg_python.probe(video_path)
            if 'format' in probe and 'duration' in probe['format']:
                duration = float(probe["format"]["duration"])
                logger.info(f"Duração do vídeo: {duration} segundos")
                return duration
        except Exception as e:
            logger.warning(f"Falha ao usar ffmpeg-python, tentando método alternativo: {e}")
            
        # Método alternativo usando ffprobe diretamente
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            duration = float(result.stdout.strip())
            logger.info(f"Duração do vídeo: {duration} segundos")
            return duration
            
        logger.error(f"Erro ao obter duração do vídeo: {result.stderr}")
        return None

    except Exception as e:
        logger.error(f"Erro ao obter duração do vídeo: {str(e)}")
        return None

def get_template_id(avatar_number):
    """
    Obtém o template_id e o número de cenas correspondentes ao avatar_number.

    Recebe:
    - avatar_number: Número do avatar a ser usado

    Retorna:
    - template_id: ID do template a ser usado
    - num_cenas: Número de cenas do template
    """

    # Dicionário para mapear avatar_number para template_id e número de cenas
    template_map = {
        1: {
            "template_id": "18c7370997844bcc8996222113f30d0a",
            "num_cenas": 5
        },
        2: {
            "template_id": "d651ee063f3f40e491aa2fa8520a515f", 
            "num_cenas": 6
        },
        3: {
            "template_id": "063f23cbd3164f348c4e982dc076212c",
            "num_cenas": 7
        },
        4: {
            "template_id": "02af38f5ad12450ea5c38481bc81921c",
            "num_cenas": 1
        },
        5: {
            "template_id": "e882c07f804c42918026433d7a051e3f",
            "num_cenas": 5
        },
        6: {
            "template_id": "b8ff0a87e8a6440fbf8413cb6233e7e1",
            "num_cenas": 6
        },
        7: {
            "template_id": "3b2623e8638f4784970e95f869680507",
            "num_cenas": 7
        }
    }
    
    # Converte avatar_number para inteiro para garantir a comparação correta
    avatar_num = int(avatar_number)
    
    # Retorna o template_id e num_cenas correspondentes ou valores padrão
    template_info = template_map.get(avatar_num, {
        "template_id": "0add0af20ead43169bbfed11f68d21e3",
        "num_cenas": 5
    })
    
    return template_info["template_id"], template_info["num_cenas"]



def verificarRoteiroImagem(roteiro):
    """
    Verifica se os momentos-chave das imagens existem nos scripts das cenas
    e se cada momento-chave tem pelo menos 5 palavras.
    
    Args:
        roteiro (dict): O roteiro em formato JSON
        
    Returns:
        bool: True se todos os momentos-chave são válidos, False caso contrário
    """
    logger.info("Verificando momentos-chave das imagens")
    
    # Verifica se existem imagens
    if 'imagens' not in roteiro or not roteiro['imagens']:
        logger.info("Roteiro não contém imagens")
        return True
        
    # Concatena todos os scripts em um único texto
    todos_scripts = ' '.join(cena['script'] for cena in roteiro['cenas'])
    
    # Verifica cada momento-chave
    for imagem in roteiro['imagens']:
        momento_chave = imagem.get('momentoChave', '')
        
        # Verifica se o momento-chave tem pelo menos 5 palavras
        if momento_chave:
            palavras = momento_chave.split()
            if len(palavras) < 5:
                logger.warning(f"Momento-chave tem menos de 5 palavras: '{momento_chave}'")
                return False, momento_chave
        
        if momento_chave and momento_chave.lower() not in todos_scripts.lower():
            logger.warning(f"Momento-chave não encontrado nos scripts: {momento_chave}")
            return False, momento_chave
    
    logger.info("Todos os momentos-chave são válidos")
    return True, None


async def geraRoteiro(data, num_cenas):
    """
    Gera o roteiro usando o modelo de template 3.

    Recebe:
    - data: Dados para gerar o roteiro
    - num_cenas: Número de cenas desejado

    Retorna:
    - Roteiro gerado ou None se falhar
    """
    # Gera o roteiro
    dados = await vertexai_service.cria_roteiro_template_3(data, num_cenas)
    if not dados:
        logger.error("Falha ao gerar roteiro com geraRoteiro")
        return None
    return dados

async def gerarRoteiroComVerificacao(data, num_cenas, max_tentativas=10):
    """
    Tenta gerar um roteiro válido com até max_tentativas tentativas.

    Recebe:
    - data: Dados para gerar o roteiro
    - num_cenas: Número de cenas desejado
    - max_tentativas: Número máximo de tentativas (default: 10)

    Retorna:
    - Roteiro válido ou None se falhar
    """
    # Primeira fase: tentar gerar um roteiro válido
    momento_chave_invalido_texto = None
    
    for tentativa in range(max_tentativas):
        logger.info(f"Tentativa {tentativa + 1} de {max_tentativas} de gerar roteiro")
        
        dados = await geraRoteiro(data, num_cenas)
        if not dados:
            logger.error("Falha ao gerar roteiro com verificacao")
            continue

        momento_chave_valido, momento_chave_invalido_texto = verificarRoteiroImagem(dados)
            
        if momento_chave_valido:
            logger.info(f"Roteiro gerado com sucesso na tentativa {tentativa + 1}")
            return dados
        else:
            logger.warning(f"Tentativa {tentativa + 1}: Momento-chave inválido: '{momento_chave_invalido_texto}'")
            logger.info(f"Tentando corrigir o momento-chave inválido: '{momento_chave_invalido_texto}'")
            
            # Tentativas adicionais após correção
            for tentativa_correcao in range(3):  # Limita a 3 tentativas de correção
                logger.info(f"Tentativa de correção {tentativa_correcao + 1} de 3")
                
                dados_corrigidos = await mudarMomentoChave(dados, momento_chave_invalido_texto)
                if not dados_corrigidos:
                    logger.error("Falha ao corrigir o roteiro")
                    continue
                    
                # Verifica se a correção funcionou
                momento_chave_valido, novo_momento_invalido = verificarRoteiroImagem(dados_corrigidos)
                    
                if momento_chave_valido:
                    logger.info(f"Roteiro corrigido com sucesso na tentativa {tentativa_correcao + 1}")
                    return dados_corrigidos
                else:
                    logger.warning(f"Tentativa de correção {tentativa_correcao + 1}: Ainda há momento-chave inválido: '{novo_momento_invalido}'")
                    momento_chave_invalido_texto = novo_momento_invalido  # Atualiza para a próxima tentativa
    
    logger.error(f"Falha ao gerar roteiro válido após todas as tentativas")
    
    # Se chegou aqui, retorna o último roteiro gerado, mesmo com momentos-chave inválidos
    # Isso permite que o processo continue, mesmo que algumas imagens possam não ser exibidas corretamente
    return dados



async def mudarMomentoChave(roteiro, momento_chave_invalido):
    """
    Muda o momento-chave para um novo valor.

    Args:
        roteiro (dict): O roteiro em formato de dicionário
        momento_chave_invalido (str): O momento-chave inválido que precisa ser corrigido

    Returns:
        dict: O roteiro corrigido em formato de dicionário
    """
    try:
        # Converte o roteiro para string JSON se for um dicionário
        roteiro_str = json.dumps(roteiro) if isinstance(roteiro, dict) else roteiro
        
        prompt = f"O momentoChave inválido é: '{momento_chave_invalido}' e o roteiro é: {roteiro_str}. Refaça o JSON completo e garanta que todos os momentoChave estejam presentes no script das cenas correspondentes. Não altere o script das cenas, apenas o momentoChave."

        # Gera o conteúdo corrigido
        manager = get_gemini_manager()
        dados_corrigidos = await manager.generate_content(prompt, model=settings.GEMINI)

        if not dados_corrigidos:
            logger.error("Não houve resposta do modelo de geração")
            return None
        
        response_text = vertexai_service.remove_html_tags(dados_corrigidos)
        if not response_text:
            logger.error("Texto após remoção de tags HTML está vazio")
            return None

        logger.info(f"dados_corrigidos: {response_text}")
        
        # Se o resultado for uma string JSON, converte para dicionário
        try:
            json_data = json.loads(response_text)
        except json.JSONDecodeError as je:
            logger.error(f"Erro ao decodificar JSON: {je}")
            return None
        
        return json_data
        
    except Exception as e:
        logger.error(f"Erro ao corrigir momento-chave: {e}")
        return None

    