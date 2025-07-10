import logging
import os
import sys
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
import asyncio
from google import genai
from google.genai import types
import base64
from .gemini_client import get_gemini_manager
from ..utils.ssl_config import SSLConfig, SSLContextBuilder, log_ssl_config
import ssl

logger = logging.getLogger(__name__)

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import settings

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

def get_generation_config():
    """
    Obtém as configurações de geração para o modelo.
    
    Define parâmetros como temperatura, top_k, top_p e candidate_count
    para controlar a geração de conteúdo.
    
    Returns:
        GenerationConfig: Configurações para geração de conteúdo
    """
    return GenerationConfig(
        max_output_tokens=8192,  # max 8192
        temperature=2,  # quanto maior, mais criativo vai ser max 2
        top_p=0.95,
    )

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

async def generate_content(texto_entrada: str, max_retries: int = 3) -> str:
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
                model="gemini-2.5-pro-preview-05-06",
                temperature=1,
                top_p=1,
                max_output_tokens=65535
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