import logging
from typing import Optional
from google import genai
from google.genai import types
import aiohttp
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ..utils.resilience import (
    RetryConfig, CircuitBreaker, with_retry, 
    with_circuit_breaker, APIError, map_api_error
)
from ..utils.ssl_config import SSLConfig, SSLContextBuilder
from ..config.timeout_config import TimeoutConfig
import ssl

logger = logging.getLogger(__name__)

class GeminiClientManager:
    _instance = None
    _lock = asyncio.Lock()
    _client = None
    _circuit_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)
    _retry_config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        exponential_base=2,
        jitter_factor=0.1
    )
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiClientManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    async def __aenter__(self):
        if not self._initialized:
            await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def initialize(self):
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:  # Double check
                return
                
            try:
                # Get resource manager
                from app.core.resource_manager import get_resource_manager
                resource_manager = get_resource_manager()
                await resource_manager.initialize()
                
                # Initialize Gemini client
                self._client = genai.Client(
                    vertexai=True,
                    project="conteudo-autenticare",
                    location="us-central1"
                )
                
                # Thread pool for synchronous operations
                self._thread_pool = ThreadPoolExecutor(max_workers=10)
                
                self._initialized = True
                logger.info("✓ GeminiClientManager initialized successfully")
                
            except Exception as e:
                logger.error(f"❌ Error initializing GeminiClientManager: {str(e)}")
                raise map_api_error('INTERNAL', str(e))
    
    @property
    def client(self):
        """Returns the Gemini singleton client"""
        if not self._initialized:
            raise RuntimeError("GeminiClientManager not initialized")
        return self._client
    
    @property
    async def session(self):
        """Returns the HTTP session from the resource manager"""
        if not self._initialized:
            raise RuntimeError("GeminiClientManager not initialized")
        
        # Get resource manager
        from app.core.resource_manager import get_resource_manager
        resource_manager = get_resource_manager()
        
        # Use the gemini session from resource manager
        async with resource_manager.http_session("gemini") as session:
            return session
    
    @with_retry(RetryConfig())
    @with_circuit_breaker(_circuit_breaker)
    async def generate_content(
        self, 
        prompt: str, 
        model: str = "gemini-2.0-flash-001", 
        temperature: float = 1.0, 
        top_p: float = 0.95, 
        max_output_tokens: int = 8192
    ) -> Optional[str]:
        """
        Generates content using the Gemini client with connection management and resilience
        
        Args:
            prompt (str): Text to generate content from
            model (str): Name of the Gemini model to use
            temperature (float): Temperature for generation (0.0 to 2.0)
            top_p (float): Top-p for generation (0.0 to 1.0)
            max_output_tokens (int): Maximum number of tokens in output
            
        Returns:
            str: Generated content or None in case of error
            
        Raises:
            APIError: For specific API errors
        """
        if not self._initialized:
            await self.initialize()
            
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ]
            
            generate_content_config = types.GenerateContentConfig(
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
                safety_settings=[
                    types.SafetySetting(category=cat, threshold="OFF")
                    for cat in [
                        "HARM_CATEGORY_HATE_SPEECH",
                        "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "HARM_CATEGORY_HARASSMENT"
                    ]
                ]
            )
            
            async with self._lock:  # Ensure thread-safety
                response_text = ""
                
                # Use ThreadPoolExecutor to run the synchronous code in a separate thread
                def generate_stream():
                    return self.client.models.generate_content_stream(
                        model=model,
                        contents=contents,
                        config=generate_content_config
                    )
                
                # Run the stream generation in a thread pool
                stream = await asyncio.get_event_loop().run_in_executor(
                    self._thread_pool, 
                    generate_stream
                )
                
                # Process the stream chunks
                for chunk in stream:
                    if chunk and hasattr(chunk, 'text'):
                        response_text += chunk.text
                        logger.debug(f"Received chunk: {len(chunk.text)} characters")
                    
                logger.info(f"✓ Generated content successfully: {len(response_text)} characters")
                return response_text
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"❌ Error generating content: {error_message}")
            if "INVALID_ARGUMENT" in error_message:
                raise map_api_error("INVALID_ARGUMENT", error_message)
            elif "RESOURCE_EXHAUSTED" in error_message:
                raise map_api_error("RESOURCE_EXHAUSTED", error_message)
            elif "UNAVAILABLE" in error_message:
                raise map_api_error("UNAVAILABLE", error_message)
            elif "DEADLINE_EXCEEDED" in error_message:
                raise map_api_error("DEADLINE_EXCEEDED", error_message)
            else:
                raise map_api_error("INTERNAL", error_message)
            
    async def close(self):
        """Closes all connections and resources"""
        if self._initialized:
            if self._thread_pool:
                self._thread_pool.shutdown(wait=True)
            self._initialized = False
            logger.info("✓ GeminiClientManager shutdown successful")

# Helper function to get the manager instance
@lru_cache(maxsize=1)
def get_gemini_manager() -> GeminiClientManager:
    return GeminiClientManager() 