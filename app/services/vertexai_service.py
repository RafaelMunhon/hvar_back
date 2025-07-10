from datetime import datetime
import os
import re

from app.common.palavras_chaves_prompt import prompt_palavras_chaves_imagem
from .. import settings  # Importa settings do diretório pai
import json
from app.common import criaRoteiroPrompt, audiobookprompt, tratamentoJsonMatriz
import logging
from app.config.vertexAi import get_model, init_vertex_ai, get_generation_config, generate_content
import sys
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
import asyncio
from google import genai
from google.genai import types
import base64
from ..config.gemini_client import get_gemini_manager
from ..utils.ssl_config import SSLConfig, SSLContextBuilder, log_ssl_config
import ssl

logger = logging.getLogger(__name__)

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def init_vertex_ai():
    """
    Initialize Vertex AI with project settings.
    
    Loads credentials and configures the environment for Vertex AI usage.
    Must be called before any other operation with Vertex AI.
    
    Returns:
        None
    """
    try:
        vertexai.init(project=settings.PROJECT_ID, location=settings.LOCATION)
        
        # Create and verify SSL configuration
        ssl_config = SSLConfig(
            verify_ssl=True,
            minimum_version=ssl.TLSVersion.TLSv1_2,
            verify_hostname=True
        )
        
        # Log SSL configuration
        log_ssl_config(ssl_config)
        
        logger.info("✓ Vertex AI initialized successfully with secure SSL configuration")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Vertex AI: {str(e)}")
        raise

def gemini_ai_thinking():
    """
    Initialize Gemini AI Thinking client with secure SSL configuration.

    Returns:
    - Gemini AI Thinking client
    """
    try:
        # Create SSL configuration
        ssl_config = SSLConfig(
            verify_ssl=True,
            minimum_version=ssl.TLSVersion.TLSv1_2,
            verify_hostname=True
        )
        ssl_builder = SSLContextBuilder(ssl_config)
        
        # Create client with SSL context
        client = genai.Client(
            vertexai=True,
            project=settings.PROJECT_ID,
            location=settings.LOCATION
        )
        
        return client
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini AI Thinking client: {str(e)}")
        raise

def get_model():
    """
    Get configured Gemini-Pro model instance with secure SSL.
    
    Returns:
        GenerativeModel: Configured Gemini-Pro model instance
    """
    try:
        # Create SSL configuration
        ssl_config = SSLConfig(
            verify_ssl=True,
            minimum_version=ssl.TLSVersion.TLSv1_2,
            verify_hostname=True
        )
        ssl_builder = SSLContextBuilder(ssl_config)
        
        # Create model with SSL context
        model = GenerativeModel(
            settings.GEMINI,
            ssl_context=ssl_builder.create_context()
        )
        return model
    except Exception as e:
        logger.error(f"❌ Failed to get Gemini model: {str(e)}")
        raise

async def generate_content_flash_2(prompt: str) -> str:
    """
    Generate content using Gemini 2.0 Flash with connection management

    Args:
        prompt (str): Text to generate content

    Returns:
        str: Generated content or None in case of error
    """
    try:
        manager = get_gemini_manager()
        return await manager.generate_content(prompt)
    except Exception as e:
        logger.error(f"Error generating content with Gemini 2.0 Flash: {str(e)}")
        return None

async def generate_content_flash(prompt: str) -> str:
    """
    Use Gemini 2.5 Flash Preview for fast content generation
    Args:
        prompt: prompt text to generate content
    Returns:
        model response or None in case of error
    """
    try:
        manager = get_gemini_manager()
        return await manager.generate_content(prompt, model="gemini-2.5-flash-preview-04-17")
    except Exception as e:
        logger.error(f"Error generating content with Gemini 2.5 Flash Preview: {str(e)}")
        # Try fallback to 1.5 model in case of error
        try:
            return await generate_content_flash_2(prompt)
        except Exception as fallback_error:
            logger.error(f"Error in fallback to 1.5 model: {str(fallback_error)}")
            return None

async def generate_content_old(texto_entrada: str, max_retries: int = 3) -> str:
    """
    Generate content using Gemini 2.5 Pro with retries and fallback.

    Args:
        texto_entrada (str): Text to generate content from
        max_retries (int): Maximum number of retries (default: 3)

    Returns:
        str: Generated content or None in case of error
    """
    manager = get_gemini_manager()
    
    for attempt in range(max_retries):
        try:
            response = await manager.generate_content(
                texto_entrada, 
                model="gemini-2.5-flash-preview-04-17"
            )
            if response:
                return response
                
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.info("Trying again...")
                await asyncio.sleep(1)  # Small delay between attempts
                continue
            else:
                logger.warning("All attempts failed. Trying alternative method...")
                try:
                    return await generate_content_flash(texto_entrada)
                except Exception as fallback_error:
                    logger.error(f"Error in fallback method: {str(fallback_error)}")
                    return None
    
    return None

def prepare_text_topic(texto):
    """
    Recebe um texto grande e gera um resumo com 15 palavras usando o Vertex AI com Gemini.

    Args:
        texto (str): O texto grande a ser resumido.
    """
    init_vertex_ai()
    model = get_model()
    generation_config = get_generation_config()

    prompt = f"Resuma o seguinte texto em 15 palavras:\n\n{texto}"

    try:
        responses = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=settings.safety_settings,
            stream=False,
        )
        return responses
    except Exception as e:
        logging.error(f"Erro ao gerar resumo: {e}")
        return None

def prepare_aula_3(texto):
    orientacoes_aula_3 =  """
        faça uma analise do texto e me retorne da seguinte forma.
        resumo_aula: string até 5 palavras
        topico4: string 3 palavra
        subtitulo4: string até 15 palavras
        topico5: string 3 palavra
        subtitulo5: string até 15 palavras
        topico6: string 3 palavra
        subtitulo6: string até 15 palavras
    """

    init_vertex_ai()
    model = get_model()
    generation_config = get_generation_config()

    prompt = orientacoes_aula_3 + "\nTexto:\n" + texto

    responses = model.generate_content(
        prompt,
        generation_config=generation_config,
        safety_settings=settings.safety_settings,
        stream=False,
    )
    
    response_text = extrair_informacoes(responses.strip())
    
    dados = json.loads(response_text) # Converte a string JSON para um dicionário Python
    return dados # Retorna um dicionário Python

def extrair_informacoes(texto):
    
    data = {}
    for line in texto.splitlines():
        try:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
        except ValueError:
            print(f"Linha inválida: {line}")

    return json.dumps(data, indent=4)
    # print(json.dumps(data, indent=4))

def resumo_texto_mil(texto):

    init_vertex_ai()
    model = get_model()
    generation_config = get_generation_config()

    prompt_for_resumo = f"""Você esta apresentando uma aula é experiente e professora.
    - Com base em todo material disponibilizado sobre a aula, você deve criar uma apresentação.
    - O texto é esse.
    - deve continuar a apresentação por um bom tempo.
    - não parar de escrever
    - tudo em uma linha só, sem quebra de linhas
    - limite maximo de 1000 caracteres
    \n\n{texto}"""

    responses = model.generate_content(
        prompt_for_resumo,
        generation_config=generation_config,
        safety_settings=settings.safety_settings,
        stream=False,
    )

    resumo = responses.text
    
    return resumo

async def cria_roteiro_template_3(data, num_cenas):
    """
    Gera um roteiro usando o modelo de template 3.

    Recebe:
    - data: Dados para gerar o roteiro
    - num_cenas: Número de cenas desejado

    Retorna:
    - Roteiro gerado ou None se falhar
    """
    try:
        # Aqui, obtém os prompts, objetos e os componentes.
        logger.info("Iniciando cria_roteiro_template_3")
        component_classes = tratamentoJsonMatriz.get_component_classes()
        if not component_classes:
            logging.error("Não foi possível obter as classes de componentes")
            return None

        logger.info("Buscando prompt da matriz")
        texto_completo = tratamentoJsonMatriz.buscaPromptMatriz(data, component_classes)
        if not texto_completo:
            logging.error("Falha ao processar o texto da matriz")
            return None

        logger.info("Criando prompt do roteiro")
        prompt_roteiro = criaRoteiroPrompt.cria_roteiro_prompt_template_3(texto_completo, num_cenas)
        if not prompt_roteiro:
            logging.error("Falha ao criar o prompt do roteiro")
            return None
        
        try:
            logger.info("Gerando resposta do modelo")
            manager = get_gemini_manager()
            responses = await manager.generate_content(
                prompt_roteiro,
                model=settings.GEMINI
            )

            #responses = await generate_content(prompt_roteiro)
            if not responses:
                logging.error("Não houve resposta do modelo de geração")
                return None

            logger.info("Removendo tags HTML")
            response_text = responses
            if not response_text:
                logging.error("Texto da resposta está vazio")
                return None

            logger.info("Removendo tags HTML")
            response_text = remove_html_tags(response_text)
            if not response_text:
                logging.error("Texto após remoção de tags HTML está vazio")
                return None

            logger.info("Decodificando JSON")
            logger.info(f"Texto da resposta: {response_text}")
            try:
                json_data = json.loads(response_text)
            except json.JSONDecodeError as je:
                logging.error(f"Erro ao decodificar JSON: {je}")
                return None

            logger.info("Processando JSON")
            json_data = process_json_data(json_data)

            logger.info("Salvando JSON")
            try:
                filename_json = f"output_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
                salvar_json(json_data, filename_json)
            except IOError as io_err:
                logging.error(f"Erro ao salvar arquivo JSON: {io_err}")
                # Continua mesmo se falhar ao salvar o JSON
                
            return json_data

        except Exception as e:
            logging.error(f"Erro ao gerar conteúdo: {e}")
            return None

    except Exception as e:
        logging.error(f"Erro geral em cria_roteiro_template_3: {e}")
        return None

async def melhorar_texto_com_gemini(texto):
    try:
        # Gera o prompt com a função
        manager = get_gemini_manager()
        responses = await manager.generate_content(texto, model=settings.GEMINI) # chama o modelo antigo
        
        if responses:
            # Verifica se é um objeto GenerationResponse
            if hasattr(responses, 'text'):
                response_text = responses.text
            elif hasattr(responses, 'candidates'):
                response_text = responses.candidates[0].content.text
            else:
                response_text = str(responses)
                
            response_text = remove_html_tags(response_text)        

            if not response_text:
                print("Resposta do modelo está vazia.")
                return texto  # Retorna o texto original se a resposta estiver vazia
            
            print(f"Texto após Gemini: {response_text}")
            return response_text
        
        return texto  # Retorna o texto original se não houver resposta
        
    except Exception as e:
        print(f"Erro ao processar texto com Gemini: {e}")
        return texto  # Em caso de erro, retorna o texto original


def remove_html_tags(text):
    """Remove HTML tags e as marcações ```json e ``` de uma string."""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    text = text.replace("```json", "").replace("```", "")
    return text


def salvar_json(data, filename):
     # Criar o diretório se não existir
     diretorio = "output_jsons"

     if not os.path.exists(diretorio):
        os.makedirs(diretorio)

    # obter data e hora para nome unico de arquivo (YYYY-MM-DD_HH-MM-SS)
     timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
     filename_com_timestamp = f"{timestamp}_{filename}"
     full_path = os.path.join(diretorio, filename_com_timestamp)

     with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
     logging.info(f"JSON salvo em {full_path}")

     return filename_com_timestamp


async def encontrar_palavras_chaves_imagem(texto, quantidade_palavras_chaves, quantidade_imagens):
    """
    Encontra palavras-chave e imagens em um texto usando a API Vertex AI.
    """
    try:
        # Gera o prompt para a API
        prompt = prompt_palavras_chaves_imagem(texto, quantidade_palavras_chaves, quantidade_imagens)
        
        # Chama a API para gerar o conteúdo
        manager = get_gemini_manager()
        response = await manager.generate_content(prompt, model=settings.GEMINI)
        
        # Extrai o JSON da resposta
        json_str = response.strip()
        
        # Verifica se o JSON está entre ```json e ```
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        
        # Converte a string JSON para um objeto Python
        json_obj = json.loads(json_str)
        
        # Corrige a estrutura do JSON se necessário
        if 'properties' in json_obj:
            # Extrai os arrays diretamente das propriedades
            palavras_chaves = json_obj['properties']['palavras_chaves']['items']
            imagens = json_obj['properties']['imagens']['items']
            
            # Cria um novo objeto com a estrutura correta
            json_obj = {
                'palavras_chaves': palavras_chaves,
                'imagens': imagens
            }
        
        # Salva o JSON em um arquivo para referência
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = os.path.join(os.getcwd(), "output_jsons")
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f"{timestamp}_estudio_output_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_obj, f, indent=4, ensure_ascii=False)
        
        logging.info(f"JSON salvo em {output_file}")
        logging.info(f"JSON recebido para imagens:\n{json_obj}")
        
        return json_obj
        
    except Exception as e:
        logging.error(f"Erro ao encontrar palavras-chave e imagens: {str(e)}")
        logging.error(f"Stack trace completo:", exc_info=True)
        return None
    
def process_json_data(data):
    """Pre-processa o JSON para garantir que campos não sejam nulos"""
    for item in data.get('conteudo', []):
        if item.get('__component') == 'principais.caixa-formula':
            if item.get('titulo') is None:
                item['titulo'] = ''
    return data