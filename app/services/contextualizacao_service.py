import os
import json
import time
import traceback
import asyncio
import aiohttp
import threading
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from functools import wraps, lru_cache
from abc import ABC, abstractmethod
from datetime import datetime
from google import genai
from google.cloud import storage
from google.genai import types
from google.api_core import retry
import base64
from jinja2 import Template
import tempfile
from weasyprint import HTML
import re
import google.generativeai as genai_chat
import urllib.parse
import requests
# Import the GoogleDriveClient from the utility module
from app import settings
from app.bd.bd import inserir_contextualizacao
from app.config.ffmpeg import get_root_path, get_temp_files_path
from app.config.vertexAi import generate_content_flash_2
from app.utils.google_drive_utils import GoogleDriveClient
from app.core.logger_config import setup_logger

from app.utils.metrics import global_metrics
from app.config.timeout_config import TimeoutConfig
import aiofiles
from app.utils.resilience import APIError
from app.config.gemini_client import get_gemini_manager


logger = setup_logger(__name__)

credentials_path = get_root_path() + '/mydrive.json'
path_google_drive = "1i6UkhDYe59L1Yf6u2rc-iF37ozVgPfId"

def initialize_timeout_config():
    """Initialize timeout configuration for the service"""
    # Obter configuração padrão
    timeout_config = TimeoutConfig.get_default()
    
    # Obter timeout para cliente HTTP
    client_timeout = timeout_config.get_client_timeout()
    
    # Obter configuração para workers
    worker_config = timeout_config.get_worker_config()
    
    # Logar configuração atual
    timeout_config.log_config()
    
    return timeout_config, client_timeout, worker_config

# Initialize configurations
_timeout_config, _client_timeout, _worker_config = initialize_timeout_config()

class ProcessType(Enum):


    #TI
    contextualization_to_TI = "contextualization_to_TI"
    #Engenharia
    contextualization_to_engenharia_00221 = "contextualization_to_engenharia_00221"
    #Gestão
    contextualization_to_gestao_00962 = "contextualization_to_gestao_00962"
    #Humanas
    contextualization_to_humanidades_00908 = "contextualization_to_humanidades_00908"
    #Economia Criativa
    contextualization_to_exatas_00221 = "contextualization_to_exatas_00221"
    #Saúde
    contextualization_to_saude_00962 = "contextualization_to_saude_00962"
    #Direito
    contextualization_to_direito = "contextualization_to_direito"
    #Suavização
    suavization_03024 = "suavization_03024"


    #CONTEXTUALIZATION_WITH_SUAVIZATION_TO_GESTAO_00306 = "contextualization_with_suavization_to_gestao_00306"    
    #CONTEXTUALIZATION_TO_GESTAO_00962 = "contextualization_to_gestao_00962"
    #CONTEXTUALIZATION_TO_SAUDE_00962 = "contextualization_to_saude_00962"
    #SUAVIZATION_03024 = "suavization_03024"
    
    #CONTEXTUALIZATION_TO_HUMANIDADES_00908 = "contextualization_to_humanidades_00908"
    
@dataclass
class ProcessingMetrics:
    """Class to track processing metrics with type validation"""
    start_time: float
    processed_files: int = 0
    failed_files: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    api_calls: int = 0
    api_errors: int = 0
    skipped_files: int = 0

    def __post_init__(self):
        """Validate and convert types after initialization"""
        try:
            self.start_time = float(self.start_time)
            self.processed_files = int(self.processed_files)
            self.failed_files = int(self.failed_files)
            self.total_processing_time = float(self.total_processing_time)
            self.average_processing_time = float(self.average_processing_time)
            self.api_calls = int(self.api_calls)
            self.api_errors = int(self.api_errors)
            self.skipped_files = int(self.skipped_files)
            logger.info(f"✓ ProcessingMetrics initialized with types validated:")
            logger.info(f"  - start_time: ({type(self.start_time)}) {self.start_time}")
            logger.info(f"  - total_processing_time: ({type(self.total_processing_time)}) {self.total_processing_time}")
            logger.info(f"  - average_processing_time: ({type(self.average_processing_time)}) {self.average_processing_time}")
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Error validating ProcessingMetrics types: {str(e)}")
            raise TypeError(f"Invalid type in ProcessingMetrics initialization: {str(e)}")

@dataclass
class Config:
    gemini_api_key: str
    bucket_name: str
    model_config: Dict
    prompt_paths: Dict
    batch_size: int = 10
    max_workers: int = 10
    page_size: int = 100
    
    @classmethod
    def get_default_config(cls) -> 'Config':
        """Get configuration with default values"""
        return cls(
            gemini_api_key='AIzaSyDUnkQyPkwB3VH5T6DlY1oz6RxoGtXYroA',
            bucket_name='conteudo-autenticare-contextualizacao',
            model_config={
                'learnlm': {
                    'name': 'learnlm-1.5-pro-experimental',
                    'temperature': 2.0,
                    'top_p': 0.95,
                    'max_output_tokens': 8192
                },
                'flash_thinking': {
                    'name': 'gemini-2.0-flash-thinking-exp-01-21',
                    'temperature': 1,
                    'top_p': 0.95,
                    'top_k': 64,
                    'max_output_tokens': 8192
                },
                'gemini_flash': {
                    'name': 'gemini-2.0-flash',
                    'temperature': 1.0,
                    'top_p': 0.95,
                    'max_output_tokens': 8192
                },
                'gemini_exp': {
                    'name': 'gemini-2.5-pro-preview-05-06',
                    'temperature': 1.0,
                    'top_p': 0.95,
                    'max_output_tokens': 8192
                }
            },
            # prompt_paths={
            #     'contextualization': 'prompts/contextualization_prompt.txt',
            #     'contextualization_math': 'prompts/contextualization_prompt_math.txt',

            #     'simplification': 'prompts/simplification_prompt.txt',
            #     'simplification_math': 'prompts/simplification_prompt_math.txt',

            #     'review': 'prompts/review_prompt.txt',
            #     'review_math': 'prompts/review_prompt_math.txt',

            #     'review_simplification': 'prompts/simplification_review_prompt.txt',
            #     'reviw_simplification_math': 'prompts/simplification_review_prompt_math.txt',
            #     'json_reconstruction': 'prompts/json_reconstruction_prompt.txt',
            # }


            prompt_paths={
                #Aprofundamento de Funções
                #'contextualization_with_suavization_to_gestao_00306':'prompts/contextualization_with_suavization_to_gestao_00306.txt',
                'content_score_classification_00306':'prompts/content_score_classification_00306.txt',

                #Técnicas de Pesquisa
                #'contextualization_to_gestao_00962':'prompts/contextualization_to_gestao_00962.txt',
                #'contextualization_to_saude_00962':'prompts/contextualization_to_saude_00962.txt',
                'content_score_classification_00962':'prompts/content_score_classification_00962.txt',

                #Transformação de Energia na célula
                #'suavization_03024':'prompts/suavization_03024.txt',
                'content_score_classification_03024':'prompts/content_score_classification_03024.txt',

                #Cotidiano do Gestor
                #'contextualization_to_engenharia_00221':'prompts/contextualization_to_engenharia_00221.txt',
                #'contextualization_to_exatas_00221':'prompts/contextualization_to_exatas_00221.txt',
                'content_score_classification_00221':'prompts/content_score_classification_00221.txt',
                #Projeto e Organização
                #'contextualization_to_humanidades_00908':'prompts/contextualization_to_humanidades_00908.txt',
                #'content_score_classification_00221':'prompts/content_score_classification_00221.txt',

                'contextualization_to_TI':'prompts/contextualization_to_TI.txt',
                'contextualization_to_engenharia_00221':'prompts/contextualization_to_engenharia_00221.txt',
                'contextualization_to_gestao_00962':'prompts/contextualization_to_gestao_00962.txt',
                'contextualization_to_humanidades_00908':'prompts/contextualization_to_humanidades_00908.txt',
                'contextualization_to_exatas_00221':'prompts/contextualization_to_exatas_00221.txt',
                'contextualization_to_saude_00962':'prompts/contextualization_to_saude_00962.txt',
                'contextualization_to_direito':'prompts/contextualization_to_direito.txt',
                'suavization_03024':'prompts/suavization_03024.txt'
            }
        )

@dataclass
class ProcessingResult:
    content: str
    metadata: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    processing_time: Optional[float] = None

@dataclass
class ProcessorResponse:
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None
    stats: Optional[Dict] = None
    json_url: Optional[str] = None
    folder_link: Optional[str] = None

class ContentProcessor(ABC):
    @abstractmethod
    async def process(self, content: str, session: Optional[aiohttp.ClientSession] = None) -> ProcessingResult:
        pass

class LearnLMProcessor(ContentProcessor):
    def __init__(self, model_config: Dict, prompt_template: str = ""):
        self.model_config = model_config
        self.prompt_template = prompt_template
   
    async def process(self, content: str, session: Optional[aiohttp.ClientSession] = None) -> ProcessingResult:
        """Process content using the LearnLM model"""
        start_time = time.time()
        try:
            # Get the GeminiClientManager instance
            from app.config.gemini_client import get_gemini_manager
            manager = get_gemini_manager()
            
            # Prepare prompt with content
            if isinstance(content, list):
                # If content is already a list of prompt parts, use it directly
                prompt = "\n".join([part.get("text", "") for part in content])
            else:
                # Otherwise, create a simple text prompt
                prompt = self.prompt_template + "\n\n" + content
            
            # Make the Gemini API call using the manager
            response = await manager.generate_content(
                prompt=prompt,
                model=self.model_config['name'],
                temperature=self.model_config['temperature'],
                top_p=self.model_config['top_p'],
                max_output_tokens=self.model_config['max_output_tokens']
            )
            
            if response is None:
                raise Exception("Failed to generate content")
            
            return ProcessingResult(
                content=response,
                metadata={
                    'model': self.model_config['name']
                },
                success=True,
                processing_time=time.time() - start_time
            )
            
        except Exception as e:
            error_msg = f"LearnLM processing failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ProcessingResult(
                content='',
                metadata={},
                success=False,
                error=error_msg,
                processing_time=time.time() - start_time
            )

class HTMLGenerator(ContentProcessor):
    def __init__(self, client, model_config: Dict):
        self.client = client
        self.model_config = model_config
        self.template = self._get_template()

    @global_metrics.timing()
    def _get_template(self) -> Template:
        """Get HTML template (hardcoded to avoid file dependency)"""
        template_html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Conteúdo Educacional</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Open+Sans:wght@400;600&display=swap');

        :root {
            --primary-color: #2c3e50;
            --secondary-color: #3498db;
            --text-color: #333;
            --light-bg: #f8f9fa;
            --border-color: #ddd;
        }

        body {
            font-family: 'Open Sans', sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fff;
        }

        h1, h2, h3, h4, h5, h6 {
            font-family: 'Montserrat', sans-serif;
            color: var(--primary-color);
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            font-weight: 600;
        }

        h1 {
            font-size: 2em;
            color: #1a365d;
            border-bottom: 2px solid var(--secondary-color);
            padding-bottom: 0.3em;
        }

        h2 { font-size: 1.5em; }

        p {
            margin-bottom: 1.2em;
            font-size: 1em;
        }

        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1.5em auto;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        figure {
            margin: 2em 0;
            text-align: center;
        }

        figcaption {
            font-size: 0.9em;
            color: #666;
            margin-top: 0.5em;
            font-style: italic;
        }

        .formula {
            background-color: var(--light-bg);
            padding: 15px;
            border-radius: 5px;
            margin: 1.5em 0;
            overflow-x: auto;
            text-align: center;
            font-size: 1.1em;
            border-left: 4px solid var(--secondary-color);
        }

        ul, ol {
            padding-left: 2em;
            margin-bottom: 1.2em;
        }

        li { margin-bottom: 0.5em; }

        blockquote {
            border-left: 4px solid var(--secondary-color);
            padding: 0.5em 1em;
            margin-left: 0;
            background-color: var(--light-bg);
            color: #555;
        }

        code {
            background-color: #f0f0f0;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: monospace;
        }

        table {
            border-collapse: collapse;
            width: 100%;
            margin: 1.5em 0;
            table-layout: fixed; /* Use fixed table layout */
        }

        th, td {
            border: 1px solid var(--border-color);
            padding: 8px 12px;
            text-align: left;
            word-wrap: break-word; /* Enable word wrapping */
            hyphens: auto; /* Enable hyphenation */
        }

        th {
            background-color: var(--light-bg);
            font-weight: 600;
        }

        .header {
            background-color: var(--primary-color);
            color: white;
            padding: 1em;
            margin-bottom: 2em;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .header a {
            color: white;
            text-decoration: none;
            margin-right: 1em;
            font-weight: 600;
        }

        .header a:hover {
            text-decoration: underline;
        }

        .back-button {
            display: inline-block;
            margin-bottom: 1em;
            padding: 0.5em 1em;
            background-color: var(--secondary-color);
            color: white;
            text-decoration: none;
            border-radius: 3px;
            font-weight: 600;
            transition: background-color 0.2s;
        }

        .back-button:hover {
            background-color: #2980b9;
        }

        .content {
            background-color: white;
            padding: 2em;
            border-radius: 5px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }

        /* Special styling for mathematical equations */
        .equ {
            font-family: 'Times New Roman', serif;
            font-style: italic;
        }

        /* Accordion styling */
        .accordion {
            margin-bottom: 1em;
            border: 1px solid var(--border-color);
            border-radius: 5px;
            overflow: hidden;
        }

        .accordion-header {
            background-color: var(--light-bg);
            padding: 1em;
            cursor: pointer;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
        }

        .accordion-content {
            padding: 1em;
        }

        .accordion.active .accordion-content {
            display: block;
        }

        /* Video container */
        .video-container {
            position: relative;
            padding-bottom: 56.25%; /* 16:9 aspect ratio */
            height: 0;
            overflow: hidden;
            margin: 1.5em 0;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }

        .video-container iframe {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 0;
        }

        @media (max-width: 768px) {
            body { padding: 15px; }
            .content { padding: 1em; }
            h1 { font-size: 1.8em; }
        }

        /* Print-specific styles */
        @media print {
            body {
                font-size: 12pt;
                color: #000;
                background-color: #fff;
            }

            .header, .back-button {
                display: none;
            }

            h1 {
                font-size: 18pt;
                margin-top: 1cm;
            }

            h2 {
                font-size: 16pt;
                margin-top: 0.8cm;
            }

            img {
                max-width: 100% !important;
                page-break-inside: avoid;
            }

            a {
                color: #000;
                text-decoration: none;
            }

            .video-container {
                display: none;
            }

            .formula {
                border: 1px solid #ddd;
                page-break-inside: avoid;
            }
        }
    </style>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Initialize accordions
            const accordionHeaders = document.querySelectorAll('.accordion-header');
            accordionHeaders.forEach(header => {
                header.addEventListener('click', function() {
                    this.parentElement.classList.toggle('active');
                });
            });
        });
    </script>
</head>
<body>
    <div class="header">
        <a href="index.html" class="back-button">← Voltar</a>
    </div>

    <div class="content">
        {{ content|safe }}
    </div>
</body>
</html>"""
        return Template(template_html)
    
    @global_metrics.timing()
    def _generate_html_from_json(self, json_data: Dict) -> str:
        """Generate HTML from JSON content with improved styling and math rendering"""
        content_parts = []  # Initialize content_parts list
        
        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="pt-BR">',
            '<head>',
            '    <meta charset="UTF-8">',
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">',
            f'    <title>{json_data.get("titulo_nc", "Documento")}</title>',
            '    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&family=Open+Sans:wght@400;600&display=swap" rel="stylesheet">',
            # Add MathJax for LaTeX rendering
            '    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>',
            '    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>',
            '    <style>',
            '        @import url(\'https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Open+Sans:wght@400;600&display=swap\');',
            '        ',
            '        :root {',
            '            --primary-color: #2c3e50;',
            '            --secondary-color: #3498db;',
            '            --text-color: #333;',
            '            --light-bg: #f8f9fa;',
            '            --border-color: #ddd;',
            '        }',
            '        ',
            '        body {',
            '            font-family: "Open Sans", sans-serif;',
            '            line-height: 1.6;',
            '            color: var(--text-color);',
            '            max-width: 1200px;',
            '            margin: 0 auto;',
            '            padding: 20px;',
            '            background-color: #fff;',
            '        }',
            '        ',
            '        h1, h2, h3, h4, h5, h6 {',
            '            font-family: "Montserrat", sans-serif;',
            '            color: var(--primary-color);',
            '            margin-top: 1.5em;',
            '            margin-bottom: 0.5em;',
            '            font-weight: 600;',
            '        }',
            '        ',
            '        h1 { ',
            '            font-size: 2em; ',
            '            color: #1a365d;',
            '            border-bottom: 2px solid var(--secondary-color);',
            '            padding-bottom: 0.3em;',
            '        }',
            '        ',
            '        h2 { font-size: 1.5em; }',
            '        ',
            '        p { ',
            '            margin-bottom: 1.2em; ',
            '            font-size: 1em;',
            '        }',
            '        ',
            '        img { ',
            '            max-width: 100%; ',
            '            height: auto;',
            '            display: block;',
            '            margin: 1.5em auto;',
            '            border-radius: 5px;',
            '            box-shadow: 0 2px 5px rgba(0,0,0,0.1);',
            '        }',
            '        ',
            '        figure {',
            '            margin: 2em 0;',
            '            text-align: center;',
            '        }',
            '        ',
            '        figcaption {',
            '            font-size: 0.9em;',
            '            color: #666;',
            '            margin-top: 0.5em;',
            '            font-style: italic;',
            '        }',
            '        ',
            '        .formula {',
            '            background-color: #e1f5fe;', # Light blue background like in the example
            '            padding: 20px;',
            '            border-radius: 5px;',
            '            margin: 1.5em 0;',
            '            overflow-x: auto;',
            '            text-align: center;',
            '            font-size: 1.1em;',
            '            border-left: 4px solid var(--secondary-color);',
            '        }',
            '        ',
            '        .equ {',
            '            font-family: "Times New Roman", serif;',
            '            font-style: italic;',
            '        }',
            '        ',
            '        /* Video container */',
            '        .video-container {',
            '            position: relative;',
            '            padding-bottom: 56.25%; /* 16:9 aspect ratio */',
            '            height: 0;',
            '            overflow: hidden;',
            '            margin: 1.5em 0;',
            '            border-radius: 5px;',
            '            box-shadow: 0 2px 5px rgba(0,0,0,0.1);',
            '        }',
            '        ',
            '        .video-container iframe {',
            '            position: absolute;',
            '            top: 0;',
            '            left: 0;',
            '            width: 100%;',
            '            height: 100%;',
            '            border: 0;',
            '        }',
            '        ',
            '        /* Accordion styling */',
            '        .accordion {',
            '            margin-bottom: 1em;',
            '            border: 1px solid var(--border-color);',
            '            border-radius: 5px;',
            '            overflow: hidden;',
            '        }',
            '        ',
            '        .accordion-header {',
            '            background-color: var(--light-bg);',
            '            padding: 1em;',
            '            cursor: pointer;',
            '            font-weight: 600;',
            '            border-bottom: 1px solid var(--border-color);',
            '        }',
            '        ',
            '        .accordion-content {',
            '            padding: 1em;',
            '        }',
            '        ',
            '        .accordion.active .accordion-content {',
            '            display: block;',
            '        }',
            '        ',
            '        /* Special styling for mathematical equations */',
            '        .equ {',
            '            font-family: "Times New Roman", serif;',
            '            font-style: italic;',
            '        }',
            '        ',
            '        /* Accordion styling */',
            '        .accordion {',
            '            margin-bottom: 1em;',
            '            border: 1px solid var(--border-color);',
            '            border-radius: 5px;',
            '            overflow: hidden;',
            '        }',
            '        ',
            '        .accordion-header {',
            '            background-color: var(--light-bg);',
            '            padding: 1em;',
            '            cursor: pointer;',
            '            font-weight: 600;',
            '            border-bottom: 1px solid var(--border-color);',
            '        }',
            '        ',
            '        .accordion-content {',
            '            padding: 1em;',
            '        }',
            '        ',
            '        .accordion.active .accordion-content {',
            '            display: block;',
            '        }',
            '        ',
            '        /* Video container */',
            '        .video-container {',
            '            position: relative;',
            '            padding-bottom: 56.25%; /* 16:9 aspect ratio */',
            '            height: 0;',
            '            overflow: hidden;',
            '            margin: 1.5em 0;',
            '            border-radius: 5px;',
            '            box-shadow: 0 2px 5px rgba(0,0,0,0.1);',
            '        }',
            '        ',
            '        .video-container iframe {',
            '            position: absolute;',
            '            top: 0;',
            '            left: 0;',
            '            width: 100%;',
            '            height: 100%;',
            '            border: 0;',
            '        }',
            '        ',
            '        @media (max-width: 768px) {',
            '            body { padding: 15px; }',
            '            .content { padding: 1em; }',
            '            h1 { font-size: 1.8em; }',
            '        }',
            '        ',
            '        /* Print-specific styles */',
            '        @media print {',
            '            body {',
            '                font-size: 12pt;',
            '                color: #000;',
            '                background-color: #fff;',
            '            }',
            '            ',
            '            .header, .back-button {',
            '                display: none;',
            '            }',
            '            ',
            '            h1 {',
            '                font-size: 18pt;',
            '                margin-top: 1cm;',
            '            }',
            '            ',
            '            h2 {',
            '                font-size: 16pt;',
            '                margin-top: 0.8cm;',
            '            }',
            '            ',
            '            img {',
            '                max-width: 100% !important;',
            '                page-break-inside: avoid;',
            '            }',
            '            ',
            '            a {',
            '                color: #000;',
            '                text-decoration: none;',
            '            }',
            '            ',
            '            .video-container {',
            '                display: none;',
            '            }',
            '            ',
            '            .formula {',
            '                border: 1px solid #ddd;',
            '                page-break-inside: avoid;',
            '            }',
            '        }',
            '    </style>',
            '</head>',
            '<body>',
        ]
        
        # Process each component
        content_items = json_data.get('conteudo', [])
        for item in content_items:
            component_type = item.get('__component')
            if not component_type:
                continue
                
            # Handle each component type with improved HTML structure
            if component_type == 'principais.tipografia':
                variante = item.get('variante', 'paragraph')
                texto = item.get('texto', '')
                
                # Check if the text contains LaTeX-like formulas
                if '\\begin{cases}' in texto or '\\frac' in texto or '_' in texto or '^' in texto or '\\leq' in texto:
                    html_parts.append('<div class="formula">')
                    # Properly format LaTeX with MathJax delimiters
                    clean_text = texto.replace("<p>", "").replace("</p>", "")
                    html_parts.append(f'<div class="formula-content">\\[{clean_text}\\]</div>')
                    html_parts.append('</div>')
                elif variante == 'title':
                    html_parts.append(f'<h1>{texto}</h1>')
                elif variante == 'subtitle':
                    html_parts.append(f'<h2>{texto}</h2>')
                else:
                    html_parts.append(f'<div class="typography">{texto}</div>')

            elif component_type == 'principais.caixa-formula':
                formula = item.get('formula', '')
                titulo = item.get('titulo', '')
                legenda = item.get('legenda', '')

                # Clean up the formula if needed
                if formula.startswith('$$') and formula.endswith('$$'):
                    formula = formula[2:-2].strip()

                html_parts.append('<div class="formula">')
                if titulo:
                    html_parts.append(f'<div class="formula-title">{titulo}</div>')
                # Properly format LaTeX with MathJax delimiters
                html_parts.append(f'<div class="formula-content">\\[{formula}\\]</div>')
                if legenda:
                    html_parts.append(f'<div class="formula-caption">{legenda}</div>')
                html_parts.append('</div>')

            elif component_type == 'principais.grupo-imagem':
                imagens = item.get('imagens', [])
                formato = item.get('formato', 'full')

                for img in imagens:
                    imagem = img.get('imagem', {})
                    url = imagem.get('url', '')
                    legenda = img.get('legenda', '')
                    creditos = img.get('creditos', '')
                    alt_text = img.get('texto_alternativo', '')

                    if url:
                        html_parts.append('<figure class="image-container">')
                        html_parts.append(f'<img src="{url}" alt="{alt_text or "Imagem"}" loading="lazy">')
                        if legenda:
                            html_parts.append(f'<figcaption>{legenda}</figcaption>')
                        if creditos:
                            html_parts.append(f'<div class="credits">{creditos}</div>')
                        html_parts.append('</figure>')

            elif component_type == 'principais.video':
                url_video = item.get('urlVideo', '')
                if url_video:
                    html_parts.append('<div class="video-container">')
                    html_parts.append(f'<iframe src="{url_video}" allowfullscreen></iframe>')
                    html_parts.append('</div>')

            elif component_type == 'principais.grupo-accordion':
                variant = item.get('variante_cor', 'light')
                position = item.get('posicao', 'abaixo')
                accordion_type = item.get('tipo', 'padrao')

                html_parts.append(f'<div class="accordion-group accordion-{variant} accordion-{position} accordion-{accordion_type}">')

                for accordion in item.get('accordions', []):
                    title = accordion.get('titulo_accordion', '')
                    content = accordion.get('conteudo_accordion', '')

                    html_parts.append('<div class="accordion">')
                    html_parts.append(f'<div class="accordion-title">{title}</div>')
                    html_parts.append(f'<div class="accordion-content">{content}</div>')
                    html_parts.append('</div>')

                html_parts.append('</div>')

            elif component_type == 'principais.card-tematico':
                title = item.get('titulo_card_tematico', '')
                content = item.get('conteudo_card_tematico', '')
                card_type = item.get('tipo', 'default')

                html_parts.append(f'<div class="card card-{card_type}">')
                if title:
                    html_parts.append(f'<h3 class="card-title">{title}</h3>')
                html_parts.append(f'<div class="card-content">{content}</div>')
                html_parts.append('</div>')

            elif component_type == 'principais.carrossel':
                # Handle carrossel component with a simpler approach
                print(item)

                carousel_items = []

                # Get carousel items safely
                try:
                    # Get the raw carousel items
                    raw_items = item.get('itens_carrossel', [])

                    # Ensure it's a list
                    if isinstance(raw_items, list):
                        # Process each item
                        for carousel_item in raw_items:
                            if isinstance(carousel_item, dict):
                                carousel_items.append({
                                    'title': str(carousel_item.get('titulo_texto', '')),
                                    'content': str(carousel_item.get('conteudo_texto', '')),
                                    'caption': str(carousel_item.get('legenda', '')),
                                    'credits': str(carousel_item.get('creditos', ''))
                                })

                    # Log the number of items processed
                    logger.info(f"Processed {len(carousel_items)} carousel items")
                except Exception as e:
                    logger.error(f"Error processing carousel items: {str(e)}")
                content_parts = []
                # Add the carousel component with a simple items list
                content_parts.append({
                    'type': 'carousel',
                    'items': carousel_items,
                    'carousel_type': item.get('tipo', 'horizontal')
                })

            elif component_type == 'principais.destaque-texto':
                # Handle destaque-texto component
                content_parts.append({
                    'type': 'highlight',
                    'content': item.get('conteudo', ''),
                    'variant': item.get('variante_cor', 'light')
                })

            elif component_type == 'principais.patterns-imagem':
                # Handle patterns-imagem component
                image_data = item.get('imagem', {})
                image_url = image_data.get('url', '') if image_data else ''
                position = item.get('posicao_texto', 'texto a direita')

                content_parts.append({
                    'type': 'text_with_image',
                    'content': item.get('texto', ''),
                    'image_url': image_url,
                    'caption': item.get('legenda', ''),
                    'credits': item.get('creditos', ''),
                    'alt_text': item.get('texto_alternativo', ''),
                    'position': position
                })

            # Add more component handlers as needed


        html_parts.append('</body>')
        html_parts.append('</html>')

        return '\n'.join(html_parts)
    
    @global_metrics.timing()
    def _generate_html_from_text(self, content: str) -> str:
        """Generate HTML from text content"""
        # Wrap content in template
        return self.template.render(content=content)
    
    @global_metrics.timing()
    async def process(self, content: str, session: Optional[aiohttp.ClientSession] = None) -> ProcessingResult:
        start_time = time.time()
        try:
            # Check if content is JSON and parse it
            try:
                if isinstance(content, str) and content.strip().startswith('{'):
                    json_data = json.loads(content)
                    # Extract content from JSON structure
                    html_content = self._generate_html_from_json(json_data)
                    logger.info(f"Generated HTML from JSON with title: {json_data.get('titulo_nc', 'No title')}")
                else:
                    # If not JSON, treat as HTML content directly
                    html_content = self._generate_html_from_text(content)
                    logger.info("Generated HTML from text content")
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as HTML content
                logger.warning("Content is not valid JSON, treating as HTML")
                html_content = self._generate_html_from_text(content)
            
            # Log a preview of the generated HTML
            logger.info(f"Generated HTML preview: {html_content[:200]}...")
            
            return ProcessingResult(
                content=html_content,
                metadata={'generator': 'html'},
                success=True,
                processing_time=time.time() - start_time
            )
        except Exception as e:
            error_msg = f"HTML generation failed: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ProcessingResult(
                content='',
                metadata={},
                success=False,
                error=error_msg,
                processing_time=time.time() - start_time
            )

class MainMenuGenerator:
    def __init__(self, tema_structure: Dict):
        self.tema_structure = tema_structure
    
    @global_metrics.timing()
    def generate_menu_html(self) -> str:
        """Generate the main HTML page with navigation menu"""
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.tema_structure['titulo_tema']}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .module {{
            margin-bottom: 30px;
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
        }}
        h1 {{
            color: #333;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #333;
            margin-bottom: 15px;
        }}
        ul {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        li {{
            margin-bottom: 10px;
        }}
        a {{
            color: #2c5282;
            text-decoration: none;
            padding: 5px 10px;
            border-radius: 4px;
            transition: background-color 0.2s;
            display: block;
        }}
        a:hover {{
            background-color: #e2e8f0;
        }}
    </style>
</head>
<body>
    <h1>{self.tema_structure['titulo_tema']}</h1>"""
        
        for modulo in self.tema_structure['modulos']:
            html += f"""
    <div class="module">
        <h2>{modulo['titulo_modulo']}</h2>
        <ul>"""
            
            for nc in modulo['nucleosConceituais']:
                html += f"""
            <li><a href="nc_{nc['id']}.html">{nc['titulo_nc']}</a></li>"""
            
            html += """
        </ul>
    </div>"""
        
        html += """
</body>
</html>"""
        return html

class PDFRenderer(ContentProcessor):
    def __init__(self):
        self.wkhtmltopdf_path = get_wkhtmltopdf_path()
        
    def __init__(self):
        self.template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{{ title }}</title>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&family=Open+Sans:wght@400;600&display=swap');
                
                :root {
                    --primary-color: #2c3e50;
                    --secondary-color: #3498db;
                    --text-color: #333;
                    --light-bg: #f8f9fa;
                    --border-color: #ddd;
                }
                
                body {
                    font-family: 'Open Sans', sans-serif;
                    line-height: 1.6;
                    color: var(--text-color);
                    margin: 0;
                    padding: 2cm;
                    background-color: #fff;
                }
                
                h1, h2, h3, h4, h5, h6 {
                    font-family: 'Montserrat', sans-serif;
                    color: var(--primary-color);
                    margin-top: 1.5em;
                    margin-bottom: 0.5em;
                    font-weight: 600;
                }
                
                h1 { 
                    font-size: 24pt; 
                    color: #1a365d;
                    border-bottom: 2px solid var(--secondary-color);
                    padding-bottom: 0.3em;
                }

                table {
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1.5em 0;
                    table-layout: fixed; /* Use fixed table layout */
                }
                
                th, td {
                    border: 1px solid var(--border-color);
                    padding: 8px 12px;
                    text-align: left;
                    word-wrap: break-word; /* Enable word wrapping */
                    hyphens: auto; /* Enable hyphenation */
                }
                
                h2 { font-size: 18pt; }
                
                p { 
                    margin-bottom: 1.2em; 
                    font-size: 11pt;
                }
                
                img { 
                    max-width: 100%; 
                    height: auto;
                    display: block;
                    margin: 1.5em auto;
                    border-radius: 5px;
                }
                
                figure {
                    margin: 2em 0;
                    text-align: center;
                    page-break-inside: avoid;
                }
                
                figcaption {
                    font-size: 9pt;
                    color: #666;
                    margin-top: 0.5em;
                    font-style: italic;
                }
                
                .formula {
                    background-color: #e1f5fe;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 1.5em 0;
                    text-align: center;
                    font-size: 11pt;
                    border-left: 4px solid var(--secondary-color);
                    page-break-inside: avoid;
                }
                
                .formula img {
                    margin: 0 auto;
                    max-width: 90%;
                }
                
                .equ {
                    font-family: 'Times New Roman', serif;
                    font-style: italic;
                }
                
                .page-break {
                    page-break-after: always;
                }
                
                /* Card styles */
                .card {
                    background-color: #f8f9fa;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 1.5em 0;
                    border-left: 4px solid #3498db;
                }
                
                .card-comment {
                    background-color: #e8f4f8;
                    border-left-color: #2980b9;
                }
                
                .card-warning {
                    background-color: #fff3cd;
                    border-left-color: #ffc107;
                }
                
                .card-info {
                    background-color: #d1ecf1;
                    border-left-color: #17a2b8;
                }
                
                /* Accordion styles */
                .accordion-group {
                    margin: 1.5em 0;
                }
                
                .accordion {
                    margin-bottom: 10px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    overflow: hidden;
                }
                
                .accordion-title {
                    background-color: #f1f1f1;
                    padding: 10px 15px;
                    font-weight: bold;
                    border-bottom: 1px solid #ddd;
                }
                
                .accordion-content {
                    padding: 15px;
                }
                
                /* Carousel styles */
                .carousel {
                    margin: 1.5em 0;
                    background-color: #f8f9fa;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                }
                
                .carousel h3 {
                    color: #3498db;
                    margin-top: 0;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }
                
                .carousel-content {
                    margin-top: 10px;
                }
                
                .carousel ul {
                    margin-left: 20px;
                    padding-left: 0;
                }
                
                .carousel li {
                    margin-bottom: 8px;
                }
                
                /* Text with image styles */
                .text-with-image {
                    display: flex;
                    margin: 1.5em 0;
                    gap: 20px;
                    align-items: flex-start;
                    page-break-inside: avoid;
                }
                
                .text-with-image.text-right {
                    flex-direction: row;
                }
                
                .text-with-image.text-left {
                    flex-direction: row-reverse;
                }
                
                .text-with-image .image {
                    max-width: 40%;
                }
                
                .text-with-image .text {
                    flex: 1;
                }
                
                .text-with-image img {
                    max-width: 100%;
                    margin: 0;
                }
                
                .text-with-image .caption {
                    font-size: 9pt;
                    color: #666;
                    margin-top: 0.5em;
                    font-style: italic;
                    text-align: center;
                }
                
                /* Highlight styles */
                .highlight {
                    background-color: #f8f9fa;
                    border-left: 4px solid #6c757d;
                    padding: 15px;
                    margin: 1.5em 0;
                    font-style: italic;
                }
                
                .highlight-light {
                    background-color: #f8f9fa;
                    border-left-color: #6c757d;
                }
                
                .highlight-dark {
                    background-color: #e9ecef;
                    border-left-color: #343a40;
                }
                
                /* Header and footer */
                @page {
                    @top-center { content: normal; }
                    @bottom-center { content: normal; }
                }
                
                /* First page has no header */
                @page :first {
                    @top-center { content: normal; }
                }
                
                /* Card with image styles */
                .card-with-image-container {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-bottom: 20px;
                }

                .card-with-image {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                    flex: 1;
                    min-width: 250px;
                    background-color: #f8f8f8;
                }

                .card-with-image .card-title {
                    font-weight: bold;
                    margin-bottom: 10px;
                }

                .card-with-image .card-description {
                    margin-bottom: 10px;
                }

                .card-with-image img {
                    max-width: 100%;
                    height: auto;
                    margin-bottom: 10px;
                }
                
                .card-with-image .card-credits {
                    font-size: 0.8em;
                    color: #666;
                }
                /* Card Comparativo styles */
                .card-comparativo {
                    display: flex;
                    gap: 20px;
                    margin: 1.5em 0;
                }
                
                .card-comparativo-card {
                    flex: 1;
                    border: 1px solid #ddd;
                    padding: 15px;
                }
                /* Modal Container Styles */
                .modal-container {
                    border: 1px solid #ccc;
                    padding: 10px;
                    margin-bottom: 10px;
                    background-color: #f8f8f8;
                }
                .modal-title {
                    font-weight: bold;
                    margin-bottom: 5px;
                }
                .modal-content {
                    margin-bottom: 5px;
                }
                .chave-resposta {
                    background-color: #e9f5e9; /* Light green background */
                    border: 1px solid #a3d3a3;
                    border-left: 4px solid #4CAF50; /* Green left border */
                    padding: 15px;
                    margin: 1.5em 0;
                    border-radius: 5px;
                    page-break-inside: avoid;
                }

                .chave-resposta h3 {
                    margin-top: 0;
                    color: #388E3C; /* Darker green for title */
                }

                .chave-resposta-content p:last-child {
                    margin-bottom: 0; /* Remove extra margin at the end */
                }
                /* Quote styles */
                .quote {
                    background-color: #f8f9fa;
                    border-left: 4px solid #6c757d;
                    padding: 15px;
                    margin: 1.5em 0;
                    font-style: italic;
                }
                .quote-autor{
                    font-size: 0.8em;
                    color: #666;
                    margin-top: 0.5em;
                    font-style: italic;
                    text-align: right;
                }
            </style>
        </head>
        <body>
            <h1>{{ title }}</h1>
            {% for part in content_parts %}
                {% if part.type == 'text' %}
                    <div class="text">{{ part.content|safe }}</div>
                {% elif part.type == 'heading' %}
                    <h{{ part.level }}>{{ part.content|safe }}</h{{ part.level }}>
                {% elif part.type == 'formula' %}
                    <div class="formula">
                        {% if part.title %}<div class="formula-title">{{ part.title }}</div>{% endif %}
                        {% if part.image_data %}
                            <img src="data:image/png;base64,{{ part.image_data }}" alt="Formula" />
                        {% else %}
                            <div class="formula-content">{{ part.content|safe }}</div>
                        {% endif %}
                        {% if part.caption %}<div class="formula-caption">{{ part.caption }}</div>{% endif %}
                    </div>
                {% elif part.type == 'image' %}
                    <figure>
                        <img src="{{ part.url }}" alt="{{ part.alt }}">
                        {% if part.caption %}
                            <figcaption>{{ part.caption|safe }}</figcaption>
                        {% endif %}
                    </figure>
                {% elif part.type == 'card' %}
                    <div class="card card-{{ part.card_type }}">
                        {% if part.title %}<h3>{{ part.title }}</h3>{% endif %}
                        <div class="card-content">{{ part.content|safe }}</div>
                    </div>
                {% elif part.type == 'highlight' %}
                    <blockquote class="highlight highlight-{{ part.variant }}">
                        {{ part.content|safe }}
                    </blockquote>
                {% elif part.type == 'text_with_image' %}
                    <div class="text-with-image {% if part.position == 'texto a direita' %}text-right{% else %}text-left{% endif %}">
                        <div class="image">
                            {% if part.image_url %}
                                <img src="{{ part.image_url }}" alt="{{ part.alt_text }}">
                                {% if part.caption %}
                                    <div class="caption">{{ part.caption|safe }}{% if part.credits %} {{ part.credits|safe }}{% endif %}</div>
                                {% endif %}
                            {% endif %}
                        </div>
                        <div class="text">
                            {{ part.content|safe }}
                        </div>
                    </div>
                {% elif part.type == 'question' %}
                    <div class="question">
                        <h3>{{ part.title }}</h3>
                        <div class="statement">{{ part.statement|safe }}</div>
                        <div class="alternatives">
                            {% for alt in part.alternatives %}
                                <div class="alternative {% if alt.is_correct %}correct{% endif %}">
                                    <span class="letter">{{ alt.letter }})</span> {{ alt.text|safe }}
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                {% elif part.type == 'accordion_group' %}
                    <div class="accordion-group">
                        {% if part.accordions and part.accordions is iterable %}
                            {% for accordion in part.accordions %}
                                <div class="accordion">
                                    <div class="accordion-title">{{ accordion.title }}</div>
                                    <div class="accordion-content">{{ accordion.content|safe }}</div>
                                </div>
                            {% endfor %}
                        {% else %}
                            <div class="accordion-error">Error: Accordion data is not iterable</div>
                        {% endif %}
                    </div>
                {% elif part.type == 'carousel' %}
                    <div class="carousel">
                        <h3>Conteúdo em Carrossel</h3>
                        {% if part['items'] is defined and part['items'] and (part['items']|length > 0) %}
                            <ul>
                                {% for item in part['items'] %}
                                    <li>
                                        <strong>{{ item['title'] }}</strong>: {{ item['content'] }}
                                    </li>
                                {% endfor %}
                            </ul>
                        {% else %}
                            <p>Nenhum item disponível no carrossel.</p>
                        {% endif %}
                    </div>
                {% elif part.type == 'video_placeholder' %}
                    <div class="video-placeholder">
                        <p>{{ part.message }}</p>
                        <p>URL: {{ part.url }}</p>
                    </div>
                {% elif part.type == 'card_with_image' %}
                    <div class="card-with-image">
                        {% if part.image_url %}
                            <img src="{{ part.image_url }}" alt="{{ part.alt_text }}">
                        {% endif %}
                        <div class="card-title">{{ part.title|safe }}</div>
                        <div class="card-description">{{ part.description|safe }}</div>
                        <div class="card-credits">{{ part.credits|safe }}</div>
                    </div>
                {% elif part.type == 'card_comparativo' %}
                    <div class="card-comparativo">
                        <div class="card-comparativo-card">
                            {% if part.card1_title %}<div class="card-comparativo-title">{{ part.card1_title|safe }}</div>{% endif %}
                            {% if part.card1_description %}<div class="card-comparativo-description">{{ part.card1_description|safe }}</div>{% endif %}
                        </div>
                        <div class="card-comparativo-card">
                            {% if part.card2_title %}
                                <div class="card-comparativo-title">{{ part.card2_title|safe }}</div>
                            {% endif %}
                            {% if part.card2_description %}
                                <div class="card-comparativo-description">{{ part.card2_description|safe }}</div>
                           {% endif %}
                        </div>
                    </div>
                {% elif part.type == 'modal' %}
                    <div class="modal-container">
                        <div class="modal-title">{{ part.title }}</div>
                        <div class="modal-content">{{ part.content }}</div>
                    </div>
                {% elif part.type == 'quote' %}
                    <div class="quote">
                        {{ part.texto|safe }}
                        {% if part.autor %}
                            <div class="quote-autor">{{ part.autor }}</div>
                        {% endif %}
                    </div>
                {% elif part.type == 'chave_resposta' %}
                    <div class="chave-resposta">
                        {% if part.title %}
                            <h3>{{ part.title|safe }}</h3>
                        {% endif %}
                        <div class="chave-resposta-content">
                            {{ part.content|safe }}
                        </div>
                    </div>
                {% endif %}
            {% endfor %}
        </body>
        </html>
        """
    
    @global_metrics.timing()
    def render_to_pdf(self, json_content: dict) -> bytes:
        """Generate PDF from JSON content with pre-rendered formulas"""
        try:
            if not json_content:
                raise ValueError("JSON content cannot be None or empty")
                
            # Validate JSON structure
            if not isinstance(json_content, dict):
                raise ValueError(f"Expected dict for json_content, got {type(json_content)}")
            
            # Extract title from JSON
            title = json_content.get('titulo_nc', 'Untitled Document')
            
            # Extract content parts for rendering
            content_parts = self._extract_content_parts(json_content)
            if not content_parts:
                content_parts = [{
                    'type': 'text',
                    'content': 'No content available. Please check the input data.'
                }]
                logger.warning("No content parts extracted from JSON, using fallback content")
            
            # Pre-render LaTeX formulas to images
            content_parts = self._pre_render_formulas(content_parts)
            
            # Create a temporary HTML file
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
                try:
                    # Render HTML with content parts
                    html_content = Template(self.template).render(
                        title=title,
                        content_parts=content_parts
                    )
                except Exception as template_error:
                    logger.error(f"Template rendering error: {str(template_error)}")
                    # Debug the content parts that might be causing issues
                    for i, part in enumerate(content_parts):
                        logger.debug(f"Content part {i}: {part.get('type')} - Keys: {part.keys()}")
                    raise
                
                temp_html.write(html_content.encode('utf-8'))
                temp_html_path = temp_html.name
            
            try:
                # Use WeasyPrint to generate PDF
                html = HTML(filename=temp_html_path)
                pdf_bytes = html.write_pdf()
                
                # Validate PDF content
                if not pdf_bytes or len(pdf_bytes) < 100:  # PDF menor que 100 bytes provavelmente está corrompido
                    raise ValueError("Generated PDF is empty or too small")
                    
                return pdf_bytes
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_html_path):
                    os.remove(temp_html_path)
                    
        except Exception as e:
            error_msg = f"PDF rendering failed: {str(e)}"
            logger.error(error_msg)
            raise

    @global_metrics.timing()
    def _format_piecewise_function(self, text: str) -> str:
        """Format a piecewise function into proper LaTeX cases environment"""
        # If it's already in proper LaTeX format, return as is
        if '\\begin{cases}' in text:
            return text
            
        # Try to detect piecewise function format like in the image
        if 'f(x)' in text and '{' in text and '}' in text:
            # Extract the function definition
            try:
                # Remove any HTML tags
                clean_text = re.sub(r'<[^>]+>', '', text)
                
                # Check if it matches the pattern in the image
                pattern = r'f\(x\)\s*=\s*\{\s*(.*?)\s*\}'
                match = re.search(pattern, clean_text, re.DOTALL)
                
                if match:
                    cases_content = match.group(1)
                    # Split by commas or line breaks to get individual cases
                    cases = re.split(r',|\n', cases_content)
                    formatted_cases = []
                    
                    for case in cases:
                        if case.strip():
                            # Split each case into expression and condition
                            parts = case.split(',')
                            if len(parts) == 1 and '>' in case:
                                parts = case.split('>')
                                if len(parts) == 2:
                                    expr = parts[0].strip()
                                    cond = f"x > {parts[1].strip()}"
                                    formatted_cases.append(f"{expr}, {cond}")
                            elif len(parts) == 1 and '<' in case:
                                parts = case.split('<')
                                if len(parts) == 2:
                                    expr = parts[0].strip()
                                    cond = f"x < {parts[1].strip()}"
                                    formatted_cases.append(f"{expr}, {cond}")
                            elif len(parts) == 2:
                                expr, cond = parts
                                formatted_cases.append(f"{expr.strip()}, {cond.strip()}")
                            else:
                                # If we can't parse it properly, use as is
                                formatted_cases.append(case.strip())
                    
                    # Create the LaTeX cases environment
                    if formatted_cases:
                        cases_latex = ' \\\\ '.join(formatted_cases)
                        return f"f(x) = \\begin{{cases}} {cases_latex} \\end{{cases}}"
            except Exception as e:
                logger.warning(f"Error formatting piecewise function: {str(e)}")
                
        # If we couldn't parse it or it's not a piecewise function, return as is
        return text
    
    @global_metrics.timing()
    def save_pdf_to_file(self, json_content: dict, output_path: str) -> str:
        """Generate PDF and save it to a file"""
        try:
            pdf_content = self.render_to_pdf(json_content)
            
            # Ensure pdf_content is bytes
            if not isinstance(pdf_content, bytes):
                raise TypeError(f"Expected bytes for PDF content, got {type(pdf_content).__name__}")
            
            # Save PDF to file
            with open(output_path, 'wb') as f:
                f.write(pdf_content)
            
            logger.info(f"✅ PDF saved successfully to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Failed to save PDF: {str(e)}")
            
            # Create a simple fallback PDF with basic content
            try:
                logger.info("Attempting to create a fallback PDF...")
                fallback_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>{json_content.get('titulo_nc', 'Untitled Document')}</title>
                </head>
                <body>
                    <h1>{json_content.get('titulo_nc', 'Untitled Document')}</h1>
                    <p>PDF generation encountered an error. Please check the logs for details.</p>
                    <p>Error: {str(e)}</p>
                </body>
                </html>
                """
                
                with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
                    temp_html.write(fallback_html.encode('utf-8'))
                    temp_html_path = temp_html.name
                
                try:
                    # Use WeasyPrint to generate a simple PDF
                    html = HTML(string=fallback_html)
                    pdf_bytes = html.write_pdf()
                    
                    with open(output_path, 'wb') as f:
                        f.write(pdf_bytes)
                    
                    logger.info(f"✅ Fallback PDF saved to: {output_path}")
                    return output_path
                    
                finally:
                    if os.path.exists(temp_html_path):
                        os.remove(temp_html_path)
                        
            except Exception as fallback_error:
                logger.error(f"❌ Failed to create fallback PDF: {str(fallback_error)}")
                raise e  # Re-raise the original error

    @global_metrics.timing()
    async def process(self, content: str, session: Optional[aiohttp.ClientSession] = None) -> ProcessingResult:
        """
        Process JSON content and generate a PDF
        """
        start_time = time.time()
        try:
            # Parse the JSON content
            json_content = json.loads(content)
            
            # Generate the PDF content
            pdf_bytes = self.render_to_pdf(json_content)
            
            # Save to Google Drive if credentials are available
            try:
                credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'conteudo-autenticare-d2aaae9aeffe.json')
                # if os.path.exists(credentials_path):
                #     drive_result = self.save_pdf_to_drive(
                #         json_content=json_content,
                #         blob_name=content.get('id', 'untitled'),
                #         credentials_path=credentials_path
                #     )
                #     return ProcessingResult(
                #         content=pdf_bytes,
                #         metadata={
                #             'content_type': 'application/pdf',
                #             'format': 'bytes',
                #             'drive_file_id': drive_result['file_id'],
                #             'drive_file_link': drive_result['file_link']
                #         },
                #         success=True,
                #         processing_time=time.time() - start_time
                #     )
            except Exception as drive_error:
                logger.warning(f"Failed to save PDF to Google Drive: {str(drive_error)}")
            
            # Return success result with PDF content as bytes
            return ProcessingResult(
                content=pdf_bytes,
                metadata={'content_type': 'application/pdf', 'format': 'bytes'},
                success=True,
                processing_time=time.time() - start_time
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON: {str(e)}"
            logger.error(error_msg)
            return ProcessingResult(
                content="",
                metadata={},
                success=False,
                error=error_msg,
                processing_time=time.time() - start_time
            )
        except Exception as e:
            error_msg = f"PDF generation failed: {str(e)}"
            logger.error(error_msg)
            traceback.print_exc()
            return ProcessingResult(
                content="",
                metadata={},
                success=False,
                error=error_msg,
                processing_time=time.time() - start_time
            )

    @global_metrics.timing()
    def _extract_content_parts(self, json_data: Dict) -> List[Dict[str, Any]]:
        """
        Extract content parts from JSON data for PDF rendering
        """
        content_parts = []  # Initialize content_parts list
        
        if not json_data or not isinstance(json_data, dict):
            logger.warning("Invalid JSON data structure")
            return content_parts
        
        html_parts = []
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html>')
        html_parts.append('<head><meta charset="UTF-8"></head>')
        html_parts.append('<body>')
            
        content_items = json_data.get('conteudo', [])
        if not content_items or not isinstance(content_items, list):
            logger.warning("No valid content items found in JSON data")
            return content_parts
        
        for item in content_items:
            if not isinstance(item, dict):
                logger.warning("Invalid content item structure")
                continue
                
            component_type = item.get('__component')
            if not component_type:
                logger.warning("Content item missing '__component'")
                continue
            
            if component_type == 'principais.tipografia':
                variante = item.get('variante', 'paragraph')
                texto = item.get('texto', '')
                
                # Check if the text contains LaTeX-like formulas
                if '\\begin{cases}' in texto or '\\frac' in texto or '_' in texto or '^' in texto or '\\leq' in texto:
                    # This might be a formula embedded in text
                    clean_text = texto.replace('<p>', '').replace('</p>', '')
                    
                    # For piecewise functions, use the formatter
                    if 'f(x)' in clean_text and '{' in clean_text and '}' in clean_text and '\\begin{cases}' not in clean_text:
                        # Format piecewise function
                        clean_text = self._format_piecewise_function(clean_text)
                    
                    content_parts.append({
                        'type': 'formula',
                        'content': clean_text,
                        'title': '',
                        'caption': ''
                    })
                else:
                    # Handle different typography variants
                    if variante == 'title':
                        content_parts.append({
                            'type': 'heading',
                            'level': 1,
                            'content': texto
                        })
                    elif variante == 'subtitle':
                        content_parts.append({
                            'type': 'heading',
                            'level': 2,
                            'content': texto
                        })
                    else:
                        content_parts.append({
                            'type': 'text',
                            'content': texto
                        })
            
            elif component_type == 'principais.caixa-formula':
                # Extract the formula content, ensuring LaTeX is properly formatted
                formula = item.get('formula', '')
                
                # Clean up the formula if needed
                if formula.startswith('$$') and formula.endswith('$$'):
                    formula = formula[2:-2].strip()
                
                # Format piecewise functions
                if 'f(x)' in formula and '{' in formula and '}' in formula and '\\begin{cases}' not in formula:
                    formula = self._format_piecewise_function(formula)
                
                content_parts.append({
                    'type': 'formula',
                    'content': formula,
                    'title': item.get('titulo', ''),
                    'caption': item.get('legenda', '')
                })
            
            elif component_type == 'principais.grupo-imagem':
                images = item.get('imagens', [])
                for img in images:
                    image_url = img.get('imagem', {}).get('url', '')
                    alt_text = img.get('texto_alternativo', '')
                    caption = img.get('legenda', '')
                    credits = img.get('creditos', '')
                    
                    if image_url:
                        content_parts.append({
                            'type': 'image',
                            'url': image_url,
                            'alt': alt_text,
                            'caption': caption,
                            'credits': credits
                        })
            
            elif component_type == 'principais.video':
                # For PDF, we can include a placeholder or screenshot for videos
                url_video = item.get('urlVideo', '')
                if url_video:
                    content_parts.append({
                        'type': 'video_placeholder',
                        'url': url_video,
                        'message': 'Este vídeo está disponível na versão online do conteúdo.'
                    })
            
            elif component_type == 'principais.grupo-accordion':
                accordions = []
                accordion_items = item.get('accordions', [])
                
                # Ensure accordions is a list and not None or a function
                if accordion_items and isinstance(accordion_items, list):
                    for accordion in accordion_items:
                        accordions.append({
                            'title': accordion.get('titulo_accordion', ''),
                            'content': accordion.get('conteudo_accordion', '')
                        })
                
                content_parts.append({
                    'type': 'accordion_group',
                    'accordions': accordions,
                    'variant': item.get('variante_cor', 'light')
                })
                
            elif component_type == 'principais.card-tematico':
                # Handle card-tematico component
                content_parts.append({
                    'type': 'card',
                    'title': item.get('titulo_card_tematico', ''),
                    'content': item.get('conteudo_card_tematico', ''),
                    'card_type': item.get('tipo', 'default')
                })
            elif component_type == "principais.grupo-card":
                cards = item.get("cards", [])
                if not isinstance(cards, list):
                    logger.warning(f"Invalid cards data: {cards}")
                    cards = []
                    
                for card in cards:
                    if not isinstance(card, dict):
                        logger.warning(f"Invalid card data: {card}")
                        continue
                        
                    card_title = card.get("titulo_card", "") if card else ""
                    card_description = card.get("descricao_card", "") if card else ""
                    card_image = card.get("imagem", {}) if card else {}
                    if not isinstance(card_image, dict):
                        card_image = {}
                    card_image_url = card_image.get("url", "")
                    card_credits = card.get("creditos","") if card else ""
                    card_alt_text = card.get("texto_alternativo","") if card else ""

                    # Remove HTML tags from title and description
                    card_title = re.sub(r"<[^>]+>", "", card_title)
                    card_description = re.sub(r"<[^>]+>", "", card_description)
                    card_credits = re.sub(r"<[^>]+>", "", card_credits)

                    content_parts.append({
                        "type": "card_with_image",
                        "title": card_title,
                        "description": card_description,
                        "image_url": card_image_url,
                        "credits": card_credits,
                        "alt_text": card_alt_text
                    })
            elif component_type == 'principais.carrossel':
                # Handle carrossel component with a simpler approach
                carousel_items = []
                
                # Get carousel items safely
                try:
                    # Get the raw carousel items
                    raw_items = item.get('itens_carrossel', [])
                    
                    # Ensure it's a list
                    if isinstance(raw_items, list):
                        # Process each item
                        for carousel_item in raw_items:
                            if isinstance(carousel_item, dict):
                                carousel_items.append({
                                    'title': str(carousel_item.get('titulo_texto', '')),
                                    'content': str(carousel_item.get('conteudo_texto', '')),
                                    'caption': str(carousel_item.get('legenda', '')),
                                    'credits': str(carousel_item.get('creditos', ''))
                                })
                    
                    # Log the number of items processed
                    logger.info(f"Processed {len(carousel_items)} carousel items")
                except Exception as e:
                    logger.error(f"Error processing carousel items: {str(e)}")
                
                # Add the carousel component with a simple items list
                content_parts.append({
                    'type': 'carousel',
                    'items': carousel_items,
                    'carousel_type': item.get('tipo', 'horizontal')
                })
            
            elif component_type == 'principais.destaque-texto':
                # Handle destaque-texto component
                content_parts.append({
                    'type': 'highlight',
                    'content': item.get('conteudo', ''),
                    'variant': item.get('variante_cor', 'light')
                })
            
            elif component_type == 'principais.patterns-imagem':
                # Handle patterns-imagem component
                image_data = item.get('imagem', {})
                image_url = image_data.get('url', '') if image_data else ''
                position = item.get('posicao_texto', 'texto a direita')
                
                content_parts.append({
                    'type': 'text_with_image',
                    'content': item.get('texto', ''),
                    'image_url': image_url,
                    'caption': item.get('legenda', ''),
                    'credits': item.get('creditos', ''),
                    'alt_text': item.get('texto_alternativo', ''),
                    'position': position
                })
            elif component_type == "principais.quote":
                content_parts.append({
                    "type": "quote",
                    "texto": item.get("texto", ""),
                    "autor": item.get("autor", "")
                })
            elif component_type == "principais.card-comparativo":
                card1 = item.get("card1", {})
                card2 = item.get("card2", {})

                # Remove HTML tags from titles and descriptions
                card1_title = re.sub(r"<[^>]+>", "", card1.get("titulo_card", ""))
                card1_description = re.sub(r"<[^>]+>", "", card1.get("descricao_card", ""))
                card2_title = re.sub(r"<[^>]+>", "", card2.get("titulo_card", ""))
                card2_description = re.sub(r"<[^>]+>", "", card2.get("descricao_card", ""))

                content_parts.append({
                    "type": "card_comparativo",
                    "card1_title": card1_title,
                    "card1_description": card1_description,
                    "card2_title": card2_title,
                    "card2_description": card2_description
                })
            elif component_type == "principais.tipografia-modal":
                # Handle tipografia-modal component
                texto = item.get("texto", "")
                modais = item.get("modais", [])

                content_parts.append({
                    "type": "text",
                    "content": texto
                })

                for modal in modais:
                    modal_title = modal.get("titulo_modal", "")
                    modal_content = modal.get("conteudo_modal", "")

                    content_parts.append({
                        "type": "modal",
                        "title": modal_title,
                        "content": modal_content
                    })
            elif component_type == 'principais.chave-resposta':
                title = item.get('titulo')
                feedback_items = item.get('conteudo_feedback', [])
                feedback_html_parts = []

                # Process nested components within conteudo_feedback
                # (Assuming they are mostly 'principais.tipografia' for now)
                for feedback_item in feedback_items:
                    if feedback_item.get('__component') == 'principais.tipografia':
                        feedback_html_parts.append(feedback_item.get('texto', ''))
                    # Add handling for other potential nested components if needed

                feedback_content_html = "\n".join(feedback_html_parts)

                content_parts.append({
                    'type': 'chave_resposta', # Define a new type for the template
                    'title': title,
                    'content': feedback_content_html # Store the combined HTML content
                })
            # Add more component handlers as needed
        
        return content_parts
    
    @global_metrics.timing()
    def _pre_render_formulas(self, content_parts: List[Dict]) -> List[Dict]:
        """Pre-render LaTeX formulas to base64-encoded PNG images"""
        for part in content_parts:
            if part['type'] == 'formula':
                try:
                    # Use Google Charts API to render LaTeX
                    latex_content = part['content']
                    
                    # Clean up the LaTeX content
                    latex_content = latex_content.replace('\\[', '').replace('\\]', '')
                    
                    # URL encode the LaTeX content
                    encoded_latex = urllib.parse.quote(latex_content)
                    
                    # Create Google Charts API URL
                    chart_url = f"https://chart.googleapis.com/chart?cht=tx&chl={encoded_latex}&chs=500"
                    
                    # Fetch the image
                    response = requests.get(chart_url)
                    if response.status_code == 200:
                        # Convert to base64
                        image_data = base64.b64encode(response.content).decode('utf-8')
                        part['image_data'] = image_data
                    else:
                        logger.warning(f"Failed to render formula: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Error pre-rendering formula: {str(e)}")
            elif part['type'] == 'modal':
                # Clean up HTML tags from modal content
                part['title'] = re.sub(r'<[^>]+>', '', part['title'])
                part['content'] = re.sub(r'<[^>]+>', '', part['content'])

        return content_parts

    @global_metrics.timing()
    def save_pdf_to_drive(self, json_content: dict, blob_name: str, base_folder_id: str = None, credentials_path: str = None, credentials_dict: dict = None) -> dict:
        """Generate PDF and save it to Google Drive"""
        try:
            # Generate PDF content
            pdf_content = self.render_to_pdf(json_content)
            
            # Initialize Google Drive client
            drive_client = GoogleDriveClient(
                credentials_path=credentials_path,
                credentials_dict=credentials_dict
            )
            
            # Parse the blob path into components
            path_components = blob_name.split('/')
            
            # Extract the filename (last component)
            if len(path_components) > 0:
                filename = path_components[-1].replace(".txt", ".pdf")  # Change extension to .pdf
                folder_components = path_components[:-1]
            else:
                filename = blob_name.replace(".txt", ".pdf")
                folder_components = []
                
            # Add PDF folder to path
            folder_components.insert(-1, "PDF")
            
            # Create folder structure
            current_folder_id = base_folder_id
            if folder_components:
                logger.info(f"Creating folder structure: {'/'.join(folder_components)}")
                for folder_name in folder_components:
                    if not folder_name:  # Skip empty folder names
                        continue
                    current_folder_id = drive_client.find_or_create_folder(folder_name, current_folder_id)
            
            # Upload the PDF file
            file_id = drive_client.create_document(
                title=filename,
                content=pdf_content,
                folder_id=current_folder_id
            )
            
            # Generate a shareable link
            file_link = drive_client.get_file_link(file_id)
            
            logger.info(f"✅ PDF saved to Google Drive successfully")
            logger.info(f"📄 File ID: {file_id}")
            logger.info(f"🔗 File Link: {file_link}")
            
            return {
                "file_id": file_id,
                "file_link": file_link
            }
            
        except Exception as e:
            error_msg = f"Failed to save PDF to Google Drive: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

class ContentPipeline:
    def __init__(self, initial_processor: ContentProcessor, 
                 review_processor: ContentProcessor,
                 correction_processor: ContentProcessor,
                 html_processor: ContentProcessor,
                 json_reconstruction_processor: ContentProcessor,
                 simplification_processor=ContentProcessor,
                 batch_size: int = 5,
                 config: Config = None):  # Add config parameter
        self.initial_processor = initial_processor
        self.review_processor = review_processor
        self.correction_processor = correction_processor
        self.html_processor = html_processor
        self.json_reconstruction_processor = json_reconstruction_processor
        self.simplification_processor = simplification_processor
        self.batch_size = batch_size
        self.config = config  # Store config
        self.pdf_renderer = PDFRenderer()
        

    @global_metrics.timing()
    async def generate_html(self, content: str, session: Optional[aiohttp.ClientSession]) -> ProcessingResult:
        """Stage 5: HTML Generation"""
        logger.info("🔄 Starting HTML generation")
        result = await self.html_processor.process(content, session)
        if not result.success:
            logger.error(f"❌ HTML generation failed: {result.error}")
        else:
            logger.info("✅ HTML generation completed")
        return result

    @global_metrics.timing()
    async def process_parallel(self, content: str, session: Optional[aiohttp.ClientSession] = None, blob_name: str = None, folder_id: str = None, json_parametros: dict = None  ) -> ProcessingResult:
        """Process content using the complete pipeline with detailed logger"""
        start_time = time.time()
        max_retries = 3  # Número máximo de tentativas
        
        try:
            # Convert content to JSON if needed
            json_data = json.loads(content) if isinstance(content, str) else content
            
            # Get resource manager
            from app.core.resource_manager import get_resource_manager
            resource_manager = get_resource_manager()
            await resource_manager.initialize()

            # Initialize Google Drive client
            drive_client = GoogleDriveClient(credentials_path=credentials_path)
            path_modulo = json_parametros.get('modulo')
            path_nucleo = json_parametros.get('nucleo')

            # Verificar se o módulo e núcleo foram fornecidos
            if not path_modulo or not path_nucleo:
                raise ValueError("Módulo ou Núcleo não fornecidos nos parâmetros")

            # 1. Gerar e verificar PDF
            logger.info("\n📑 STAGE 1: PDF GENERATION")
            pdf_generated = False
            pdf_base64 = None
            
            for attempt in range(max_retries):
                try:
                    temp_dir = get_temp_files_path()
                    output_path = f"{temp_dir}/output_{time.time()}.pdf"
                    logger.info(f"Tentativa {attempt + 1} de gerar PDF em: {output_path}")
                    
                    path_pdf = self.pdf_renderer.save_pdf_to_file(json_data, output_path)
                    
                    # Verificar se o PDF foi gerado corretamente
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        # Converter PDF para base64
                        with open(output_path, 'rb') as pdf_file:
                            pdf_bytes = pdf_file.read()
                            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                            
                        pdf_generated = True
                        logger.info("✓ PDF gerado e convertido para base64 com sucesso")
                        break
                    else:
                        logger.warning(f"PDF não gerado corretamente na tentativa {attempt + 1}")
                except Exception as e:
                    logger.error(f"Erro ao gerar PDF (tentativa {attempt + 1}): {str(e)}")
                    if attempt == max_retries - 1:
                        raise

            if not pdf_generated or not pdf_base64:
                raise Exception("Falha ao gerar ou codificar o PDF após todas as tentativas")

            # 2. Criar estrutura de pastas e salvar arquivos
            tema_modulo_folder = None
            for attempt in range(max_retries):
                try:
                    tema_modulo_folder = drive_client.find_or_create_folder(path_modulo, folder_id)
                    if tema_modulo_folder:
                        logger.info(f"✓ Pasta do módulo criada/encontrada: {path_modulo}")
                        break
                except Exception as e:
                    logger.error(f"Erro ao criar pasta (tentativa {attempt + 1}): {str(e)}")
                    if attempt == max_retries - 1:
                        raise

            if not tema_modulo_folder:
                raise Exception("Falha ao criar/encontrar pasta do módulo")

            # Resto do código existente para contextualização...
            # ... existing code ...

            # 3. Verificar se os arquivos foram salvos
            for attempt in range(max_retries):
                try:
                    # Verificar se o arquivo existe no Drive
                    file_name = path_nucleo.replace('.json', '.doc')
                    existing_file = drive_client.find_file_by_name(file_name, tema_modulo_folder)
                    
                    if existing_file:
                        logger.info(f"✓ Arquivo encontrado no Drive: {file_name}")
                        break
                    else:
                        logger.warning(f"Arquivo não encontrado no Drive (tentativa {attempt + 1})")
                        if attempt < max_retries - 1:
                            # Tentar criar o arquivo novamente
                            document_id = drive_client.create_document(
                                title=file_name,
                                content=best_contextualization.replace('```', '').replace('```', '').strip(),
                                folder_id=tema_modulo_folder
                            )
                except Exception as e:
                    logger.error(f"Erro ao verificar/criar arquivo (tentativa {attempt + 1}): {str(e)}")
                    if attempt == max_retries - 1:
                        raise

            # ... rest of the existing code ...

            # 4. Contextualization Process
            logger.info("\n🔄 STAGE 2: CONTENT CONTEXTUALIZATION (MULTIPLE ATTEMPTS)")
            logger.info("→ Preparing contextualization prompt...")
            contextualization_prompt = [
                {"text": self.initial_processor.prompt_template},
                {
                     "inline_data": {
                         "mime_type": "application/pdf",
                         "data": pdf_base64
                     }
                 }                
            ]
            
            logger.info("→ Sending content for contextualization (3 attempts)...")
            logger.info(f"→ Using model: {settings.GEMINI}")
            
            # Run contextualization 3 times and store results
            contextualization_results = []
            
            try:
                for attempt in range(1, 2):
                    logger.info(f"Iniciando tentativa de contextualização #{attempt}...")
                    # Await the task immediately instead of collecting them
                    result = await self._process_with_gemini(contextualization_prompt, session)
                    if not result.success:
                        logger.error(f"Tentativa de contextualização #{attempt} falhou: {result.error}")
                        continue
                        
                    logger.info(f"✓ Tentativa de contextualização #{attempt} completada com sucesso")
                    logger.info(f"Preview do conteúdo contextualizado #{attempt}:")
                    logger.info(f"{result.content[:200]}...")
                    
                    contextualization_results.append({
                        "attempt": attempt,
                        "content": result.content,
                        "score": 0  # Will be filled by review process
                    })
                    
                if not contextualization_results:
                    raise Exception("Nenhum resultado de contextualização foi gerado")
                    
            except Exception as e:
                logger.error(f"Erro durante a contextualização: {str(e)}")
                raise Exception(f"Contextualização falhou: {str(e)}")
            
            # 3. Review Process - Compare the 2 contextualization results
            logger.info("\n🔍 STAGE 3: CONTENT REVIEW AND SELECTION")
            logger.info("→ Preparing review prompt...")
            
            # Create a review prompt that includes all contextualization results
            review_prompt_text = """Por favor, avalie as duas versões de contextualização abaixo e atribua uma nota de 1 a 10 para cada uma, considerando:
                                    - Qualidade da contextualização para a área alvo
                                    - Clareza e fluidez do texto
                                    - Precisão do conteúdo
                                    - Adequação da linguagem

                                    Retorne apenas as notas no formato:
                                    Versão 1: [NOTA]
                                    Versão 2: [NOTA]

                                    Não use notas iguais para diferentes versões.

                                    VERSÃO 1:
                                    {version1}

                                    VERSÃO 2:
                                    {version2}

                                """

            # Format the review prompt with the contextualization results
            formatted_review_prompt = review_prompt_text.format(
                version1=contextualization_results[0]["content"] if len(contextualization_results) > 0 else "N/A",
                version2=contextualization_results[1]["content"] if len(contextualization_results) > 1 else "N/A"
            )
            
            review_prompt = [
                {"text": formatted_review_prompt}
            ]
            
            logger.info("→ Sending contextualization results for review...")
            logger.info(f"→ Using model: {settings.GEMINI}")
            review_result = await self._process_with_gemini(review_prompt, session)
            
            if not review_result.success:
                raise Exception(f"Review failed: {review_result.error}")
            
            logger.info("✓ Review completed successfully")
            logger.info("Review feedback:")
            logger.info(f"{review_result.content}")
            
            # Parse the review results to get scores
            # Try both formats: with and without square brackets
            score_pattern = r"Versão (\d+): (?:\[)?(\d+)(?:\])?"
            scores = re.findall(score_pattern, review_result.content)
            
            if not scores:
                logger.warning("Could not parse scores from review result, using first contextualization")
                best_contextualization = contextualization_results[0]["content"]
            else:
                # Update scores in contextualization_results
                for version, score in scores:
                    version_idx = int(version) - 1
                    if 0 <= version_idx < len(contextualization_results):
                        contextualization_results[version_idx]["score"] = int(score)
                
                # Find the best contextualization (highest score)
                best_result = max(contextualization_results, key=lambda x: x["score"])
                best_contextualization = best_result["content"]
                
                logger.info(f"Selected contextualization version {best_result['attempt']} with score {best_result['score']}")
            
            # Google Document Creation
            result = await create_google_document(
                content=best_contextualization.replace('```', '').replace('```', '').strip(),
                blob_name=blob_name,
                base_folder_id=tema_modulo_folder,
                credentials_path=credentials_path,
                json_parametros=json_parametros
            )
            document_link = result["document_link"]
            print(document_link)


            # 4. Reconstruct JSON with the best contextualization
            logger.info("\n🔄 STAGE 4: JSON RECONSTRUCTION")
            logger.info("→ Preparing JSON reconstruction prompt...")
            
            # Get original JSON structure
            original_json = json.loads(content) if isinstance(content, str) else content
            
            # Create the prompt for JSON reconstruction
            json_prompt = self.json_reconstruction_processor.prompt_template.format(
                contextualization=best_contextualization,
                original_json=json.dumps(original_json, indent=2)
            )

            # Use the chat session approach for JSON reconstruction
            logger.info("→ Using chat session approach for JSON reconstruction...")
            json_result = await self._process_with_gemini_chat(
                json_prompt, 
                session
            )

            if not json_result.success:
                raise Exception(f"JSON reconstruction failed: {json_result.error}")

            # Clean up the JSON content
            json_content = json_result.content.replace("```json", "").replace("```", "").strip()

            # Validate the JSON
            try:
                reconstructed_json = json.loads(json_content)
                result = await save_json_to_drive(
                    json_content=reconstructed_json,
                    blob_name=blob_name,
                    base_folder_id=tema_modulo_folder,
                    credentials_path=credentials_path,
                    json_parametros=json_parametros
                )
                document_link = result["file_link"]
                print(document_link)
                logger.info("✓ Valid JSON generated")
            except json.JSONDecodeError as e:
                logger.warning(f"Generated JSON is invalid: {str(e)}")
                logger.warning(f"JSON content preview: {json_content[:500]}...")
                raise Exception(f"Invalid JSON generated: {str(e)}")
            
            # 5. Generate HTML from reconstructed JSON instead of contextualization result
            logger.info("\n🌐 STAGE 7: HTML GENERATION")
            logger.info("→ Converting reconstructed JSON to HTML...")
            
            # Use the reconstructed JSON for HTML generation
            html_result = await self.html_processor.process(json_content, session)
            
            if not html_result.success:
                raise Exception(f"HTML generation failed: {html_result.error}")
            logger.info("✓ HTML generation completed successfully")
            
            # Final Processing Summary
            total_time = time.time() - start_time
            logger.info("\n" + "="*50)
            logger.info("📊 PROCESSING SUMMARY")
            logger.info("="*50)
            logger.info(f"Total Processing Time: {total_time:.2f} seconds")
            logger.info("Pipeline Stages Completed: 7/7")
            logger.info(f"Content ID: {json_data.get('id', 'unknown')}")
            logger.info("Final Content Size: " + str(len(html_result.content)) + " characters")
            logger.info("="*50)
            
            return ProcessingResult(
                content= content,
                metadata={
                    'model': self.initial_processor.model_config['name'],
                    'processing_steps': {
                        'simplification': contextualization_results[0]["content"],
                        'review': "review_result.content",
                        'correction': "correction_result.content",
                        'contextualization': "context_result.content",
                        'json_reconstruction': "json_content"
                    },
                    'processing_time': total_time,
                    'content_id': json_data.get('id', 'unknown')
                },
                success=True,
                processing_time=total_time
            )
            
        except Exception as e:
            error_time = time.time() - start_time
            logger.error("\n" + "="*50)
            logger.error("❌ PIPELINE ERROR")
            logger.error("="*50)
            logger.error(f"Error occurred after {error_time:.2f} seconds")
            logger.error(f"Error message: {str(e)}")
            logger.error("Full traceback:")
            logger.error(traceback.format_exc())
            logger.error("="*50)
            
            # Ensure we return the original content in case of error
            logger.error(f"❌ Processing error - error_time type: {type(error_time)}, value: {error_time}")
            return ProcessingResult(
                content=content,  # Return the original content
                metadata={
                    'error_stage': traceback.extract_stack()[-1].name,
                    'error_time': float(error_time)  # Ensure it's float
                },
                success=False,
                error=str(e),
                processing_time=float(error_time)  # Ensure it's float
            )    

    @global_metrics.timing()
    def _create_correction_prompt(self, original: str, review: str) -> str:
        """Helper method to create correction prompt"""
        return f"""Por favor, reescreva o conteúdo abaixo aplicando as seguintes correções:

Correções a serem aplicadas:
{review}

Conteúdo original:
{original}"""

    @global_metrics.timing()
    def _merge_responses(self, responses: List[str]) -> str:
        """Merge multiple responses, handling potential JSON content"""
        # Check if we're dealing with JSON responses
        if all(r.strip().startswith('{') for r in responses if r.strip()):
            try:
                # For JSON responses, we need to be more careful with merging
                # First, try to find a complete JSON object in the first response
                complete_json = None
                for response in responses:
                    try:
                        complete_json = json.loads(response)
                        break
                    except json.JSONDecodeError:
                        pass
                
                # If we found a complete JSON, use it as base
                if complete_json:
                    return json.dumps(complete_json, ensure_ascii=False, indent=2)
                
                # Otherwise, try to reconstruct by removing trailing/leading parts
                merged = ""
                for i, response in enumerate(responses):
                    if i == 0:
                        # For first part, keep everything
                        merged += response
                    else:
                        # For subsequent parts, try to find where to start
                        # Look for the first complete JSON object or array opening
                        start_idx = 0
                        for j, char in enumerate(response):
                            if char in ['{', '[']:
                                start_idx = j
                                break
                        merged += response[start_idx:]
                
                # Try to parse the merged content
                try:
                    parsed = json.loads(merged)
                    return json.dumps(parsed, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse merged JSON, returning raw merged content")
                    return merged
            except Exception as e:
                logger.warning(f"Error merging JSON responses: {str(e)}")
                return "".join(responses)
        else:
            # For non-JSON responses, simple concatenation
            return "".join(responses)

    @global_metrics.timing()
    async def _process_with_gemini(self, prompt_parts: List[Dict], session: Optional[aiohttp.ClientSession] = None) -> ProcessingResult:
        """Process content with Gemini API, handling truncated responses"""
        try:
            start_time = time.time()
            
            # Get the GeminiClientManager instance
            from app.config.gemini_client import get_gemini_manager
            from app.utils.resilience import APIError
            manager = get_gemini_manager()
            
            # Convert prompt_parts to a single string for generate_content
            prompt_text = ""
            for part in prompt_parts:
                if isinstance(part, dict):
                    if 'text' in part:
                        prompt_text += part['text'] + "\n"
                    elif 'inline_data' in part:
                        # Handle inline data (like PDFs)
                        prompt_text += f"[INLINE_DATA: {part['inline_data']['mime_type']}]\n"
                        prompt_text += part['inline_data']['data'] + "\n"
                    elif 'parts' in part:
                        for p in part['parts']:
                            if isinstance(p, dict) and 'text' in p:
                                prompt_text += p['text'] + "\n"
                elif isinstance(part, str):
                    prompt_text += part + "\n"

            # Make the API call using the manager
            response = await manager.generate_content(
                prompt=prompt_text,
                model=settings.GEMINI,
                temperature=1.0,
                top_p=0.95,
                max_output_tokens=8192
            )

            if not response:
                raise APIError("Failed to generate content", retryable=True)
            
            processing_time = time.time() - start_time
            return ProcessingResult(
                content=response,
                metadata={
                    "processing_time": processing_time,
                    "model": settings.GEMINI
                },
                success=True
            )

        except APIError as e:
            logger.error(f"❌ Gemini API error: {str(e)}")
            return ProcessingResult(
                content="",
                metadata={},
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error: {str(e)}")
            return ProcessingResult(
                content="",
                metadata={},
                success=False,
                error=str(e)
            )

    @global_metrics.timing()
    async def _process_with_gemini_chat(self, prompt: str, session: Optional[aiohttp.ClientSession] = None) -> ProcessingResult:
        start_time = time.time()
        retry_count = 0
        max_retries = 20
        
        # Melhorando o prompt para ser mais específico sobre JSON
        json_instruction = """
        INSTRUÇÕES CRÍTICAS PARA GERAÇÃO DE JSON:
        
        1. REGRAS OBRIGATÓRIAS:
        - Responda APENAS com um JSON válido
        - Use APENAS aspas duplas (") para strings, NUNCA aspas simples
        - O JSON DEVE começar com { e terminar com }
        - NUNCA inclua texto antes ou depois do JSON
        - NUNCA use formatação markdown (```json)
        - Mantenha EXATAMENTE a mesma estrutura do JSON original
        - Todas as strings devem estar entre aspas duplas
        - Todos os arrays devem estar entre colchetes []
        - Todos os objetos devem estar entre chaves {}
        
        2. ESTRUTURA OBRIGATÓRIA:
        {
            "id": "string",
            "titulo_nc": "string",
            "conteudo": [
                {
                    "__component": "string",
                    // outros campos específicos do componente
                }
            ]
        }
        
        3. ERROS COMUNS A EVITAR:
        ❌ NÃO use aspas simples: {'chave': 'valor'}
        ❌ NÃO deixe vírgulas pendentes: {"chave": "valor",}
        ❌ NÃO use comentários no JSON
        ❌ NÃO quebre strings em múltiplas linhas
        ❌ NÃO use undefined ou null - use string vazia "" se necessário
        
        4. VALIDAÇÃO:
        - Cada objeto DEVE ter todas suas chaves entre aspas duplas
        - Arrays DEVEM ter seus elementos separados por vírgulas
        - O último elemento NÃO deve ter vírgula
        - URLs devem ser strings completas e válidas
        - Números não precisam de aspas
        - Booleanos devem ser true ou false (sem aspas)
        
        5. EXEMPLO DE FORMATO CORRETO:
        {
            "id": "123",
            "titulo_nc": "Exemplo",
            "conteudo": [
                {
                    "__component": "principais.texto",
                    "texto": "Conteúdo de exemplo"
                },
                {
                    "__component": "principais.grupo-imagem",
                    "imagens": [
                        {
                            "imagem": {
                                "url": "https://exemplo.com/imagem.jpg"
                            }
                        }
                    ]
                }
            ]
        }
        """
        
        enhanced_prompt = f"{json_instruction}\n\n{prompt}"
        
        try:
            manager = get_gemini_manager()
            while True:
                try:
                    response = await manager.generate_content(
                        prompt=enhanced_prompt,
                        model=settings.GEMINI,
                        temperature=0.1,  # Reduzindo ainda mais a temperatura para respostas mais determinísticas
                        top_p=0.95,
                        max_output_tokens=8192
                    )
                    
                    if not response:
                        raise APIError("Empty response from Gemini", retryable=True)
                    
                    content = response
                    merged_content = content
                    
                    if not self._is_json_complete(content):
                        logger.info("Requesting continuation of JSON response...")
                        continuation_prompt = "Continue generating the JSON from where you left off. Do not repeat any content, just continue."
                        continuation_response = await manager.generate_content(
                            prompt=continuation_prompt,
                            model=settings.GEMINI,
                            temperature=0.1,  # Mantendo a mesma temperatura baixa para consistência
                            top_p=0.95,
                            max_output_tokens=8192
                        )
                        
                        if continuation_response:
                            continuation_content = continuation_response
                            logger.info(f"Received continuation of length: {len(continuation_content)}")
                            
                            # Merge the responses
                            merged_content = self._merge_json_responses(content, continuation_content)
                            logger.info(f"Merged JSON response length: {len(merged_content)}")
                    
                    # Clean up and validate the response
                    cleaned_content = self._clean_json_response(merged_content)
                    cleaned_content = await self._attempt_json_repair(cleaned_content)

                    # Validate the JSON
                    json.loads(cleaned_content)
                    logger.info(f"✓ Generated JSON is valid on attempt {retry_count + 1}")
                    return ProcessingResult(
                        content=cleaned_content,
                        metadata={
                            "model": settings.GEMINI,
                            "processing_time": time.time() - start_time
                        },
                        success=True,
                        processing_time=time.time() - start_time
                    )
                except json.JSONDecodeError as e:
                    retry_count += 1
                    logger.warning(f"Attempt {retry_count}: JSON validation failed - {str(e)}")
                    if retry_count >= max_retries:
                        logger.warning(f"Reached max retries ({max_retries}), but will continue trying...")
                        # Aqui NÃO levantamos a exceção, continuamos tentando
                    logger.info(f"Retrying JSON generation... (attempt {retry_count})")
                    # Modificamos o prompt para tentar obter um JSON mais limpo
                    prompt = "Please generate a valid JSON following the exact same structure as before, but ensure it is complete and properly formatted. Previous attempt failed with: " + str(e)
                    continue
                except APIError as e:
                    if not e.retryable:
                        raise
                    retry_count += 1
                    logger.warning(f"Attempt {retry_count}: API error - {str(e)}")
                    continue
                
        except APIError as e:
            logger.error(f"❌ Gemini API error: {str(e)}")
            return ProcessingResult(
                content="",
                metadata={},
                success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )
        except Exception as e:
            logger.error(f"❌ Unexpected error: {str(e)}")
            return ProcessingResult(
                content="",
                metadata={},
                success=False,
                error=str(e),
                processing_time=time.time() - start_time
            )


        
    @global_metrics.timing()
    def _merge_json_responses(self, first_part: str, second_part: str) -> str:
        """Intelligently merge two parts of a JSON response"""
        # Clean up both parts - only remove markdown code blocks
        first_part = first_part.replace("```json", "").replace("```", "").strip()
        second_part = second_part.replace("```json", "").replace("```", "").strip()
        
        # Log the first few characters of each part for debugging
        logger.debug(f"First part starts with: {first_part[:100]}...")
        logger.debug(f"Second part starts with: {second_part[:100]}...")
        
        # Special handling for truncated URLs
        # Look for URL pattern that might be cut off at the end of first_part
        url_pattern = r'"url"\s*:\s*"https?:[^"]*$'
        url_match = re.search(url_pattern, first_part)
        
        if url_match:
            logger.info("Found truncated URL at end of first part")
            # Find where the URL starts
            url_start_pos = url_match.start()
            first_part_before_url = first_part[:url_start_pos]
            
            # Extract the partial URL
            partial_url = first_part[url_start_pos:]
            logger.debug(f"Partial URL: {partial_url}")
            
            # Look for the continuation in second_part
            url_continuation_pattern = r'^[^"]*"'
            continuation_match = re.search(url_continuation_pattern, second_part)
            
            if continuation_match:
                url_continuation = continuation_match.group(0)
                logger.debug(f"URL continuation: {url_continuation}")
                second_part_remainder = second_part[continuation_match.end():]
                
                # Reconstruct with the complete URL
                merged = first_part_before_url + partial_url + url_continuation + second_part_remainder
                logger.info("Successfully reconstructed URL")
                return merged
        
        # If no truncated URL found, try standard JSON merging
        
        # Check if second_part is a complete JSON object (might be a repetition)
        if second_part.startswith('{') and second_part.endswith('}'):
            try:
                json.loads(second_part)
                if len(second_part) > len(first_part):
                    logger.info("Second part is a complete JSON and longer than first part, using it")
                    return second_part
            except json.JSONDecodeError:
                # Not a complete JSON, continue with merge
                pass
        
        # Find the last complete JSON structure in first_part
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        last_safe_pos = 0
        
        for i, char in enumerate(first_part):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
            elif char == '"' and not escape_next:
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_safe_pos = i + 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        last_safe_pos = i + 1
        
        # Find where to start in second_part
        in_string = False
        escape_next = False
        start_pos = 0
        
        for i, char in enumerate(second_part):
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
            elif char == '"' and not escape_next:
                in_string = not in_string
            elif not in_string and char in '{[':
                start_pos = i
                break
        
        # Create merged JSON
        if last_safe_pos > 0:
            # We found a complete structure in first_part
            first_part_clean = first_part[:last_safe_pos]
            second_part_clean = second_part[start_pos:]
            
            # Check if we need a comma between parts
            if first_part_clean.endswith('}') or first_part_clean.endswith(']'):
                if not second_part_clean.startswith('}') and not second_part_clean.startswith(']') and not second_part_clean.startswith(','):
                    first_part_clean += ','
            
            merged = first_part_clean + second_part_clean
        else:
            # No complete structure found, just concatenate
            merged = first_part + second_part
        
        # Validate the merged JSON
        try:
            json.loads(merged)
            logger.info("✅ Successfully merged JSON parts")
            return merged
        except json.JSONDecodeError as e:
            logger.warning(f"Merged JSON is invalid: {str(e)}")
            
            # Try a simpler approach - find the last property in first_part
            property_pattern = r',?\s*"[^"]+"\s*:\s*'
            last_property_match = list(re.finditer(property_pattern, first_part))
            
            if last_property_match:
                last_property_pos = last_property_match[-1].start()
                if last_property_pos > 0:
                    # Try merging from the last property
                    alternative_merge = first_part[:last_property_pos] + second_part
                    try:
                        json.loads(alternative_merge)
                        logger.info("✅ Alternative merge successful")
                        return alternative_merge
                    except json.JSONDecodeError:
                        pass
            
            # If all else fails, return the longer part
            return first_part if len(first_part) > len(second_part) else second_part
    
    @global_metrics.timing()
    def _is_json_complete(self, json_text: str) -> bool:
        """Check if the JSON response appears to be complete and not truncated"""
        # Remove markdown code blocks if present, but preserve the content
        cleaned = json_text
        if "```json" in cleaned:
            cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        
        # Basic structure check
        if not (cleaned.strip().startswith('{') and cleaned.strip().endswith('}')):
            logger.warning("JSON doesn't have proper opening/closing braces")
            return False
            
        try:
            # Try to parse the JSON
            parsed_json = json.loads(cleaned)
            
            # Check for required top-level keys
            required_keys = {'id', 'titulo_nc', 'conteudo'}
            missing_keys = required_keys - set(parsed_json.keys())
            if missing_keys:
                logger.warning(f"Missing required keys: {missing_keys}")
                return False
            
            # Check for truncated arrays in 'conteudo'
            if 'conteudo' in parsed_json:
                content = parsed_json['conteudo']
                if not isinstance(content, list):
                    logger.warning("'conteudo' is not an array")
                    return False
                    
                # Check each content item
                for item in content:
                    if '__component' not in item:
                        logger.warning("Content item missing '__component'")
                        return False
                        
                    component_type = item['__component']
                    
                    if component_type == 'principais.grupo-imagem':
                        if 'imagens' not in item or not isinstance(item['imagens'], list):
                            logger.warning("Incomplete image group component")
                            return False
                        
                        # Check each image in the group
                        for img in item['imagens']:
                            if 'imagem' not in img or not isinstance(img['imagem'], dict):
                                logger.warning("Incomplete image data")
                                return False
                            
                            # Check URL structure
                            image_data = img['imagem']
                            if 'url' not in image_data:
                                logger.warning("Image missing URL")
                                return False
                            
                            # Validate URL format
                            url = image_data['url']
                            if not isinstance(url, str) or not url.startswith('http'):
                                logger.warning(f"Invalid URL format: {url}")
                                return False
                            
                            # Check if URL is complete (not truncated)
                            if not re.match(r'https?://[^\s"]+\.[^\s"]+', url):
                                logger.warning(f"Potentially truncated URL: {url}")
                                return False
            
            # Check for balanced brackets and braces
            stack = []
            in_string = False
            escape_char = False
            
            for char in cleaned:
                if escape_char:
                    escape_char = False
                    continue
                    
                if char == '\\':
                    escape_char = True
                elif char == '"' and not escape_char:
                    in_string = not in_string
                elif not in_string:
                    if char in '{[':
                        stack.append(char)
                    elif char in '}]':
                        if not stack:
                            logger.warning("Unbalanced brackets/braces")
                            return False
                        if (char == '}' and stack[-1] != '{') or (char == ']' and stack[-1] != '['):
                            logger.warning("Mismatched brackets/braces")
                            return False
                        stack.pop()
            
            if stack:
                logger.warning("Unclosed brackets/braces")
                return False
            
            logger.info("✅ JSON validation successful")
            return True
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON: {str(e)}")
            return False
        except Exception as e:
            logger.warning(f"Error checking JSON completeness: {str(e)}")
            return False
        
    @global_metrics.timing()
    def _clean_json_response(self, json_text: str) -> str:
        """Clean up JSON response to ensure it's valid without affecting URLs"""
        # Remove markdown code blocks
        cleaned = json_text.replace("```json", "").replace("```", "").strip()
        
        # Ensure the JSON starts with { and ends with }
        cleaned = cleaned.strip()
        if not cleaned.startswith('{'):
            first_brace = cleaned.find('{')
            if first_brace >= 0:
                cleaned = cleaned[first_brace:]
        
        if not cleaned.endswith('}'):
            last_brace = cleaned.rfind('}')
            if last_brace >= 0:
                cleaned = cleaned[:last_brace+1]
        
        # Now try to parse the cleaned JSON
        try:
            json.loads(cleaned)
            logger.info("✓ Cleaned JSON is valid")
            return cleaned
        except json.JSONDecodeError as e:
            logger.warning(f"Cleaned JSON is invalid: {str(e)}")
            
            # If the cleaned JSON is invalid and contains URLs, preserve the original
            if "http" in cleaned and "url" in cleaned:
                logger.info("JSON contains URLs, attempting to preserve them")
                
                # Try to parse the original JSON
                try:
                    json.loads(json_text)
                    logger.info("Original JSON is valid, using it instead")
                    return json_text
                except json.JSONDecodeError:
                    logger.warning("Original JSON is also invalid")
                    
                    # Try to fix common JSON issues
                    fixed_json = self._attempt_json_repair(cleaned)
                    return fixed_json
            else:
                # Try to fix common JSON issues
                fixed_json = self._attempt_json_repair(cleaned)
                return fixed_json

    @global_metrics.timing()
    async def _attempt_json_repair(self, json_text: str) -> str:
        """Attempt to repair common JSON issues"""
        try:
            # Try to parse the JSON first to see if it's valid
            json.loads(json_text)
            return json_text
        except json.JSONDecodeError as e:
            logger.warning(f"Attempting to repair JSON: {str(e)}")
            
            # Check for unbalanced quotes
            quote_count = sum(1 for c in json_text if c == '"' and not re.search(r'\\"+', json_text[max(0, json_text.index(c)-1):json_text.index(c)+1]))
            if quote_count % 2 != 0:
                logger.warning("Unbalanced quotes detected, attempting to fix")
                # This is a complex issue to fix automatically
            
            # Check for trailing commas in arrays/objects
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
            
            # Try to fix duplicate keys by keeping the last occurrence
            # This is a complex issue that might require a more sophisticated approach
            
            try:
                # Check if our repairs worked
                json_text = json.loads(json_text)
                logger.info("✓ JSON repair successful")
                return json_text
            except json.JSONDecodeError as err:
                logger.warning(f"JSON repair failed, attempting with Gemini: {str(err)}")
                prompt = f"""
                O Json esta com o seguinte problema: {str(err)}
                Você é um especialista em JSON e precisa corrigir o seguinte JSON:
                {json_text}

                O Json corrigido deve ser retornado em formato JSON.
                """
                response = await self._attempt_json_repair_with_gemini(prompt)
                json_text = json.loads(response)
                return json_text    
            except Exception as e:
                logger.error(f"❌ Error repairing JSON with Gemini: {str(e)}")
                return json_text    
        
    async def _attempt_json_repair_with_gemini(self, json_text: str) -> str:
        """Attempt to repair common JSON issues with Gemini"""
        try:
            manager = get_gemini_manager()
            response = await manager.generate_content(
                prompt=json_text,
                model=settings.GEMINI,
                temperature=0.1,
                top_p=0.95,
                max_output_tokens=8192
            )
            return response
        except Exception as e:
            logger.error(f"❌ Error repairing JSON with Gemini: {str(e)}")

@global_metrics.timing()
def retry_operation(retries: int = 3, delay: int = 1):
    """Decorator for retrying operations with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        raise
                    sleep_time = delay * (2 ** attempt)
                    logger.warning(f"🔄 Attempt {attempt + 1} failed: {str(e)}. Retrying in {sleep_time}s")
                    await asyncio.sleep(sleep_time)
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class CloudContentProcessor:
    def __init__(self, tema_code: str, process_type: ProcessType):
        """Initialize the CloudContentProcessor
        
        Args:
            tema_code (str): The tema code identifier
            process_type (ProcessType): The type of processing to perform
        """
        self.tema_code = str(tema_code)  # Ensure tema_code is string
        self.process_type = process_type       
        self.source_prefix = f"{self.tema_code}"
        self.target_prefix = f"target/{process_type.value}/{self.tema_code}"
        self.config = Config.get_default_config()
        self.metrics = ProcessingMetrics(start_time=time.time())
        self.stats_lock = threading.Lock()
        self.cache = {}
                
        logger.info(f"""🚀 Initializing CloudContentProcessor
📁 Source: {self.source_prefix}
📁 Target: {self.target_prefix}
🔄 Process Type: {process_type.value}
""")        
        self.setup_clients()
        self.setup_pipeline()
    
    @global_metrics.timing()
    def upload_html_file(self, content: str, path: str) -> str:
        """Upload HTML file with proper content type and return public URL"""
        try:
            # Get resource manager
            from app.core.resource_manager import get_resource_manager
            resource_manager = get_resource_manager()
            
            # Create temporary file for HTML content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                # Upload to cloud storage
                blob = self.bucket.blob(path)
                blob.upload_from_filename(temp_path, content_type='text/html; charset=utf-8')
                return self.get_public_url(blob)
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            logger.error(f"Failed to upload HTML file: {str(e)}")
            raise

    @global_metrics.timing()
    def update_metrics(self, processing_time: float, success: bool = True):
        """Update processing metrics"""
        with self.stats_lock:
            try:
                logger.info(f"🔍 Updating metrics - Input processing_time type: {type(processing_time)}, value: {processing_time}")
                logger.info(f"🔍 Current metrics state:")
                logger.info(f"  - total_processing_time: ({type(self.metrics.total_processing_time)}) {self.metrics.total_processing_time}")
                logger.info(f"  - processed_files: ({type(self.metrics.processed_files)}) {self.metrics.processed_files}")
                logger.info(f"  - failed_files: ({type(self.metrics.failed_files)}) {self.metrics.failed_files}")
                logger.info(f"  - average_processing_time: ({type(self.metrics.average_processing_time)}) {self.metrics.average_processing_time}")
                
                # Ensure processing_time is float
                try:
                    processing_time = float(processing_time)
                except (ValueError, TypeError) as e:
                    logger.error(f"❌ Failed to convert processing_time to float: {str(e)}")
                    processing_time = 0.0

                # Update metrics
                if success:
                    self.metrics.processed_files += 1
                else:
                    self.metrics.failed_files += 1

                # Update total processing time
                try:
                    old_total = self.metrics.total_processing_time
                    self.metrics.total_processing_time += processing_time
                    logger.info(f"✓ Updated total_processing_time: {old_total} + {processing_time} = {self.metrics.total_processing_time}")
                except Exception as e:
                    logger.error(f"❌ Error updating total_processing_time: {str(e)}")
                    self.metrics.total_processing_time = float(processing_time)

                # Calculate average
                total_files = self.metrics.processed_files + self.metrics.failed_files
                if total_files > 0:
                    self.metrics.average_processing_time = self.metrics.total_processing_time / total_files
                
                logger.info(f"✅ Metrics updated successfully:")
                logger.info(f"  - New total_time: {self.metrics.total_processing_time}")
                logger.info(f"  - New average_time: {self.metrics.average_processing_time}")
                logger.info(f"  - Total files processed: {total_files}")
                
            except Exception as e:
                import traceback
                logger.error(f"❌ Error in update_metrics: {str(e)}")
                logger.error(f"❌ Error traceback:\n{traceback.format_exc()}")
                raise


    @global_metrics.timing()
    @retry.Retry(predicate=retry.if_exception_type(Exception))
    def setup_clients(self):
        """Setup Gemini and Cloud Storage clients with retry"""
        try:
            # Setup Gemini client
            self.gemini_client = genai.Client(api_key=self.config.gemini_api_key)
            
            # Setup Storage client with explicit credentials
            credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'conteudo-autenticare-d2aaae9aeffe.json')
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"Arquivo de credenciais não encontrado em: {credentials_path}")
                
            self.storage_client = storage.Client.from_service_account_json(credentials_path)
            self.bucket = self.storage_client.bucket(self.config.bucket_name)
            
            logger.info("✅ Clients initialized successfully")
            
            # Adiciona diagnóstico após inicialização
            self.diagnose_bucket_access()
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize clients: {str(e)}")
            raise    

    @global_metrics.timing()
    @lru_cache(maxsize=128)
    def load_prompt(self, prompt_type: str) -> str:
        """Cached prompt loading"""
        prompt_path = self.config.prompt_paths[prompt_type]
        blob = self.get_blob_with_cache(prompt_path)
        
        if not blob.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            
        template = blob.download_as_text()
        
        if not template.strip():
            raise ValueError(f"Prompt file is empty: {prompt_path}")
        
        return template
        #return template
    
    @global_metrics.timing()
    def get_blob_with_cache(self, blob_name: str) -> storage.Blob:
        """Get blob with caching"""
        if blob_name not in self.cache:
            blob = self.bucket.blob(blob_name)
            self.cache[blob_name] = blob
        return self.cache[blob_name]

    @global_metrics.timing()
    def get_public_url(self, blob: storage.Blob) -> str:
        """Get the public URL for a blob"""
        return f"https://storage.googleapis.com/{self.config.bucket_name}/{blob.name}"
    
    @global_metrics.timing()
    def verify_process_prompt(self, process_type: ProcessType) -> bool:
        """Verifica se o prompt para o processo específico existe e está acessível"""
        try:
            # Verifica se o tipo de processo está mapeado nos prompts
            if process_type.value not in self.config.prompt_paths:
                logger.error(f"❌ Tipo de processo '{process_type.value}' não encontrado no mapeamento de prompts")
                logger.info("📝 Prompts disponíveis:")
                for prompt_type in self.config.prompt_paths.keys():
                    logger.info(f"  - {prompt_type}")
                return False

            prompt_path = self.config.prompt_paths[process_type.value]
            logger.info(f"🔍 Verificando prompt para processo '{process_type.value}' em: {prompt_path}")

            # Verifica se o arquivo existe
            blob = self.get_blob_with_cache(prompt_path)
            if not blob.exists():
                logger.error(f"❌ Arquivo de prompt não encontrado: {prompt_path}")
                return False

            # Tenta ler o conteúdo
            try:
                content = blob.download_as_text()
                if not content.strip():
                    logger.error(f"❌ Arquivo de prompt está vazio: {prompt_path}")
                    return False
                logger.info(f"✓ Prompt para '{process_type.value}' carregado com sucesso")
                return True
            except Exception as e:
                logger.error(f"❌ Erro ao ler prompt '{process_type.value}': {str(e)}")
                return False

        except Exception as e:
            logger.error(f"❌ Erro ao verificar prompt do processo: {str(e)}")
            return False
        
    @global_metrics.timing()
    def setup_pipeline(self):
        """Setup the content processing pipeline"""
        try:
            # Verifica o prompt antes de configurar o pipeline
            if not self.verify_process_prompt(self.process_type):
                raise ValueError(f"Prompt não encontrado ou inválido para o processo: {self.process_type.value}")

            # Load main prompt based on process type
            main_prompt = self.load_prompt(self.process_type.value)             

            if self.process_type == ProcessType.contextualization_to_gestao_00962:
                review_prompt = self.load_prompt("content_score_classification_00306")
            elif self.process_type == ProcessType.contextualization_to_gestao_00962:
                review_prompt = self.load_prompt("content_score_classification_00962")
            elif self.process_type == ProcessType.contextualization_to_saude_00962:
                review_prompt = self.load_prompt("content_score_classification_00962")
            elif self.process_type == ProcessType.suavization_03024:
                review_prompt = self.load_prompt("content_score_classification_03024")
            else:
                review_prompt = self.load_prompt("content_score_classification_00306")
                
            
            # Create processors with appropriate prompts
            initial_processor = LearnLMProcessor(
                self.config.model_config['gemini_exp'], #flash_thinking
                main_prompt                
            )
            
            review_processor = LearnLMProcessor(
                self.config.model_config['gemini_exp'], #flash_thinking
                review_prompt                
            )

            simplification_processor = LearnLMProcessor(
                self.config.model_config['gemini_exp'], #flash_thinking
                main_prompt                
            )
            
            correction_processor = LearnLMProcessor(
                self.config.model_config['gemini_exp'], #learnlm
                ""  # Empty prompt as it will be constructed dynamically
            )
            
            html_processor = HTMLGenerator(
                self.gemini_client,
                self.config.model_config['gemini_exp'] #learnlm
            )
            
            # Add JSON reconstruction processor with a default prompt
            json_reconstruction_prompt = """Please reconstruct the JSON document for this content while preserving the original structure.
Use the following contextualization to update the content:

{contextualization}

Original JSON structure to maintain:
{original_json}

Please ensure all JSON fields from the original are preserved, only updating the content based on the contextualization.
"""
            
            json_reconstruction_processor = LearnLMProcessor(
                self.config.model_config['gemini_exp'],
                json_reconstruction_prompt
            )
            
            # Create pipeline with appropriate processors
            self.pipeline = ContentPipeline(
                initial_processor=initial_processor,
                review_processor=review_processor,
                correction_processor=correction_processor,
                html_processor=html_processor,
                json_reconstruction_processor=json_reconstruction_processor,
                simplification_processor=simplification_processor,
                batch_size=self.config.batch_size,
                config=self.config  # Pass config to pipeline
            )
            
            logger.info("✅ Processing pipeline initialized successfully")
            logger.info(f"🔄 Using process type: {self.process_type.value}")
            
        except Exception as e:
            logger.error(f"❌ Error setting up pipeline: {str(e)}")
            raise

    @global_metrics.timing()
    async def process_file_async(self, content: dict, folder_id: str = None, json_parametros: dict = None) -> Optional[Dict[str, str]]:
        """Process a single file asynchronously"""
        start_time = time.time()
        logger.info(f"🕒 Starting process_file_async - start_time type: {type(start_time)}, value: {start_time}")
        urls = None
        try:
            # Debug logs for input parameters
            logger.info(f"📥 Input parameters:")
            logger.info(f"  - content type: {type(content)}")
            logger.info(f"  - folder_id type: {type(folder_id)}, value: {folder_id}")
            logger.info(f"  - json_parametros type: {type(json_parametros)}")
            if json_parametros:
                logger.info("  - json_parametros contents:")
                for key, value in json_parametros.items():
                    logger.info(f"    {key}: ({type(value)}) {value}")

            # Get resource manager
            from app.core.resource_manager import get_resource_manager
            resource_manager = get_resource_manager()
            await resource_manager.initialize()
            
            # Use managed HTTP session
            async with resource_manager.http_session() as session:
                # Convert content to string if it's a dict
                content_str = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
                logger.info(f"📝 Content converted to string, length: {len(content_str)}")
                
                # Process the content
                logger.info("🔄 Starting pipeline.process_parallel")
                result = await self.pipeline.process_parallel(
                    content=content_str,
                    session=session,
                    blob_name=f"{self.tema_code}",
                    folder_id=folder_id,
                    json_parametros=json_parametros)
                logger.info(f"✅ Pipeline result - success: {result.success}, processing_time type: {type(result.processing_time)}")
            
            if not result.success:
                raise Exception(f"Processing failed: {result.error}")
            
            end_time = time.time()
            processing_time = end_time - start_time
            logger.info(f"⏱️ Calculating processing time - end: {end_time}, start: {start_time}, diff type: {type(processing_time)}, value: {processing_time}")
            
            self.update_metrics(processing_time, success=True)
            logger.info(f"✅ Successfully processed content")
            
            return result.success
            
        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time
            logger.info(f"⏱️ [Error] Calculating processing time - end: {end_time}, start: {start_time}, diff type: {type(processing_time)}, value: {processing_time}")
            
            # Log the full error traceback
            import traceback
            logger.error(f"❌ Error processing content: {str(e)}")
            logger.error(f"❌ Error traceback:\n{traceback.format_exc()}")
            
            self.update_metrics(processing_time, success=False)
            raise

    @global_metrics.timing()
    async def generate_main_menu(self) -> str:
        try:
            # Get tema structure
            structure_blob = self.get_blob_with_cache(f"{self.source_prefix}/Estrutura do Tema.txt")
            structure_content = structure_blob.download_as_text()
            tema_structure = json.loads(structure_content)
            
            # Generate menu HTML
            menu_generator = MainMenuGenerator(tema_structure)
            menu_html = menu_generator.generate_menu_html()
            
            # Upload menu HTML with content type
            menu_path = f"{self.target_prefix}/html/index.html"
            menu_url = self.upload_html_file(menu_html, menu_path)

            logger.info(f"📄 Generated main menu HTML: {menu_path}")
            logger.info(f"🌐 Main menu URL: {menu_url}")
            
            return menu_url
            
        except Exception as e:
            logger.error(f"❌ Error generating main menu: {str(e)}")
            raise

    @global_metrics.timing()
    def get_processing_stats(self, processing_time: float) -> dict:
        """Get current processing statistics"""
        return {
            "processed_files": self.metrics.processed_files,
            "failed_files": self.metrics.failed_files,
            "skipped_files": self.metrics.skipped_files,
            "api_calls": self.metrics.api_calls,
            "average_processing_time": self.metrics.average_processing_time,
            "total_processing_time": float(processing_time)  # Retorna como float em vez de string formatada
        }

    @global_metrics.timing()
    async def process_tema(self) -> ProcessorResponse:
        """Process all files in the tema directory with batched processing."""
        start_time = time.time()
        logger.info(f"🔄 Starting {self.process_type.value} processing for Tema {self.tema_code}...")
        
        try:
            # Collect all files to process
            files_to_process = []
            for blob in self.list_blobs_paginated():
                if "nc " in blob.name.lower() and blob.name.endswith(".txt"):
                    try:
                        content = json.loads(blob.download_as_text())
                        nc_id = content.get('id')
                        if nc_id:
                            files_to_process.append((blob, content, nc_id))
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in file: {blob.name}")
                        continue
            
            # Process files in batches
            results = {}
            failed_files = []
            
            for i in range(0, len(files_to_process), self.batch_size):
                batch = files_to_process[i:i + self.batch_size]
                batch_results = await self.process_files_batch(batch)
                results.update(batch_results)
            
            # Calculate processing statistics
            processing_time = time.time() - start_time
            stats = self.get_processing_stats(processing_time)
            
            return ProcessorResponse(
                success=len(results) > 0,
                message=f"Processed {len(results)}/{len(files_to_process)} files in tema {self.tema_code}",
                data={
                    "source": self.source_prefix,
                    "target": self.target_prefix,
                    "results": results,
                    "failed_files": failed_files
                },
                stats=stats
            )
            
        except Exception as e:
            error_msg = f"Error processing tema {self.tema_code}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ProcessorResponse(
                success=False,
                message=error_msg,
                error=str(e)
            )

    @global_metrics.timing()
    async def process_tema(self) -> ProcessorResponse:
        """Process all files in the tema directory with batched processing."""
        start_time = time.time()
        logger.info(f"🔄 Starting {self.process_type.value} processing for Tema {self.tema_code}...")
        
        try:
            # Collect all files to process
            files_to_process = []
            for blob in self.list_blobs_paginated():
                if "nc " in blob.name.lower() and blob.name.endswith(".txt"):
                    try:
                        content = json.loads(blob.download_as_text())
                        nc_id = content.get('id')
                        if nc_id:
                            files_to_process.append((blob, content, nc_id))
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON in file: {blob.name}")
                        continue
            
            # Process files in batches
            results = {}
            failed_files = []
            
            for i in range(0, len(files_to_process), self.batch_size):
                batch = files_to_process[i:i + self.batch_size]
                batch_results = await self.process_files_batch(batch)
                results.update(batch_results)
            
            # Calculate processing statistics
            processing_time = time.time() - start_time
            stats = self.get_processing_stats(processing_time)
            
            return ProcessorResponse(
                success=len(results) > 0,
                message=f"Processed {len(results)}/{len(files_to_process)} files in tema {self.tema_code}",
                data={
                    "source": self.source_prefix,
                    "target": self.target_prefix,
                    "results": results,
                    "failed_files": failed_files
                },
                stats=stats
            )
            
        except Exception as e:
            error_msg = f"Error processing tema {self.tema_code}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return ProcessorResponse(
                success=False,
                message=error_msg,
                error=str(e)
            )

    @global_metrics.timing()
    def diagnose_bucket_access(self):
        """Diagnóstico detalhado do acesso ao bucket e arquivos de prompt"""
        try:
            logger.info(f"🔍 Iniciando diagnóstico de acesso ao bucket: {self.config.bucket_name}")
            
            # 1. Verifica se consegue listar o bucket
            try:
                bucket_exists = self.bucket.exists()
                logger.info(f"✓ Bucket existe: {bucket_exists}")
                if not bucket_exists:
                    logger.error(f"❌ Bucket {self.config.bucket_name} não encontrado")
                    return False
            except Exception as e:
                logger.error(f"❌ Erro ao verificar existência do bucket: {str(e)}")
                return False

            # 2. Verifica permissões do bucket
            try:
                bucket_metadata = self.bucket.get_iam_policy()
                logger.info(f"✓ Permissões do bucket obtidas com sucesso")
            except Exception as e:
                logger.error(f"❌ Erro ao obter permissões do bucket: {str(e)}")
                return False

            # 3. Verifica cada arquivo de prompt configurado
            for prompt_type, prompt_path in self.config.prompt_paths.items():
                try:
                    blob = self.get_blob_with_cache(prompt_path)
                    exists = blob.exists()
                    logger.info(f"Prompt {prompt_type}: {'✓ Encontrado' if exists else '❌ Não encontrado'} em {prompt_path}")
                    
                    if exists:
                        # Tenta ler o conteúdo para verificar permissões de leitura
                        try:
                            content = blob.download_as_text()
                            logger.info(f"✓ Conteúdo do prompt {prompt_type} lido com sucesso")
                        except Exception as e:
                            logger.error(f"❌ Erro ao ler conteúdo do prompt {prompt_type}: {str(e)}")
                    else:
                        logger.error(f"❌ Arquivo de prompt não encontrado: {prompt_path}")
                except Exception as e:
                    logger.error(f"❌ Erro ao verificar prompt {prompt_type}: {str(e)}")

            # 4. Log do service account em uso
            logger.info(f"✓ Usando service account: {self.storage_client._credentials.service_account_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro no diagnóstico de acesso: {str(e)}")
            return False

async def main():
    '''
    Temas:
    03024 - Células
    00962 - Pesquisa
    00221 - Cotidiano do Gestor
    00908 - Projeto e Organização
    '''
    tema_code = "00908"
    process_type = ProcessType.CONTEXTUALIZATION_TO_ENGENHARIA_00221
    
    # Process all NCs in the tema
    result = await process_all_ncs(
        tema_code=tema_code,
        process_type=process_type
    )
    
    if result.success:
        logger.info(f"✅ Successfully processed tema {tema_code}")
        logger.info(f"📊 Stats: {result.stats}")
        logger.info(f"🌐 Main menu URL: {result.data['menu_url']}")
        logger.info(f"✅ Successfully processed {len(result.data['results'])} NCs")
        if result.data['failed_ncs']:
            logger.info(f"❌ Failed to process {len(result.data['failed_ncs'])} NCs: {result.data['failed_ncs']}")
    else:
        logger.error(f"❌ Failed to process tema {tema_code}: {result.message}")

async def process_all_ncs(tema_code: str, process_type: ProcessType, max_retries: int = 1) -> ProcessorResponse:
    """Process all NC files from a tema with retry mechanism for failed NCs."""
    start_time = time.time()
    try:
        logger.info(f"🚀 Starting processing of all NCs in tema {tema_code}")
        
        # Initialize the processor
        processor = CloudContentProcessor(
            tema_code=tema_code,
            process_type=process_type
        )
        # Get tema structure
        structure_blob = processor.get_blob_with_cache(f"{tema_code}/Estrutura do Tema.txt")
        structure_content = structure_blob.download_as_text()
        tema_structure = json.loads(structure_content)
        
        #Salva Núcleos
        # Extract all NC IDs and their locations
        nc_files = []
        for mod_idx, module in enumerate(tema_structure['modulos'], 1):
            for nc_idx, nc in enumerate(module['nucleosConceituais'], 1):
                nc_id = nc['id']
                nc_file = f"{tema_code}/Modulo {mod_idx}/nc {nc_idx}.txt"
                nc_blob = processor.bucket.blob(nc_file)
                
                if nc_blob.exists():
                    nc_files.append({
                        'id': nc_id,
                        'blob': nc_blob,
                        'module': mod_idx,
                        'index': nc_idx,
                        'title': nc.get('titulo_nc', f"NC {nc_id}")
                    })
                else:
                    logger.warning(f"⚠️ NC file not found: {nc_file}")
        
        #Caso não encontre núcleos
        if not nc_files:
            return ProcessorResponse(
                success=False,
                message=f"No NC files found for tema {tema_code}",
                error="No NC files found in tema structure"
            )
        
        logger.info(f"📋 Found {len(nc_files)} NC files to process")
        
        # Process each NC file
        results = {}
        failed_ncs = []
        
        # Process NCs in batches to control parallelism
        batch_size = processor.config.batch_size
        for i in range(0, len(nc_files), batch_size):
            batch = nc_files[i:i+batch_size]
            logger.info(f"🔄 Processing batch {i//batch_size + 1}/{(len(nc_files) + batch_size - 1)//batch_size}")
            
            # Create tasks for each NC in the batch
            tasks = []
            for nc_info in batch:
                task = processor.process_file_async(
                    nc_info['blob'], 
                    nc_info['id']
                )
                tasks.append((nc_info['id'], task))
                #aqui
                #break
            
            # Execute batch tasks in parallel
            batch_results = await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)
            
            # Process results
            for (nc_id, _), result in zip(tasks, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Error processing NC {nc_id}: {str(result)}")
                    # Add to retry list instead of immediately marking as failed
                    nc_info = next((nc for nc in batch if nc['id'] == nc_id), None)
                    if nc_info:
                        nc_info['retry_needed'] = True
                        nc_info['error'] = str(result)
                else:
                    results[nc_id] = result
                    logger.info(f"✅ Successfully processed NC {nc_id}")
            #aqui
            #break
        
        # Retry failed NCs
        retry_count = 0
        retry_ncs = [nc for nc in nc_files if nc.get('retry_needed', False)]
        
        while retry_ncs and retry_count < max_retries:
            retry_count += 1
            logger.info(f"🔄 Retrying {len(retry_ncs)} failed NCs (attempt {retry_count}/{max_retries})")
            
            # Process retries in smaller batches to reduce chances of failure
            retry_batch_size = max(1, batch_size // 2)
            for i in range(0, len(retry_ncs), retry_batch_size):
                retry_batch = retry_ncs[i:i+retry_batch_size]
                logger.info(f"🔄 Processing retry batch {i//retry_batch_size + 1}/{(len(retry_ncs) + retry_batch_size - 1)//retry_batch_size}")
                
                # Create tasks for each NC in the retry batch
                retry_tasks = []
                for nc_info in retry_batch:
                    nc_id = nc_info['id']
                    logger.info(f"🔄 Retrying NC {nc_id} (previous error: {nc_info.get('error', 'unknown')})")
                    
                    # Clear retry flag for next iteration
                    nc_info.pop('retry_needed', None)
                    nc_info.pop('error', None)
                    #
                    task = processor.process_file_async(
                        nc_info['blob'], 
                        nc_id
                    )
                    retry_tasks.append((nc_id, task))
                
                # Execute retry tasks in parallel
                retry_results = await asyncio.gather(*(task for _, task in retry_tasks), return_exceptions=True)
                
                # Process retry results
                for (nc_id, _), result in zip(retry_tasks, retry_results):
                    if isinstance(result, Exception):
                        logger.error(f"❌ Retry failed for NC {nc_id}: {str(result)}")
                        nc_info = next((nc for nc in retry_batch if nc['id'] == nc_id), None)
                        if nc_info and retry_count < max_retries:
                            nc_info['retry_needed'] = True
                            nc_info['error'] = str(result)
                        else:
                            failed_ncs.append(nc_id)
                    else:
                        results[nc_id] = result
                        logger.info(f"✅ Successfully processed NC {nc_id} on retry")
            
            # Update retry_ncs for next iteration
            retry_ncs = [nc for nc in nc_files if nc.get('retry_needed', False)]
        
        # Add any remaining retry_ncs to failed_ncs
        for nc in retry_ncs:
            if nc['id'] not in failed_ncs:
                failed_ncs.append(nc['id'])
        
        # Generate main menu HTML
        menu_url = await processor.generate_main_menu()
        # Calculate processing statistics
        processing_time = time.time() - start_time
        stats = processor.get_processing_stats(processing_time)
        
        # Return results
        return ProcessorResponse(
            success=True,
            message=f"Processed NCs in tema {tema_code}",
            data={
                "source": processor.source_prefix,
                "target": processor.target_prefix,
                "results": results,
                "failed_ncs": failed_ncs,
                "menu_url": menu_url
            },
            stats=stats
        )
        
    except Exception as e:
        error_msg = f"Error processing tema {tema_code}: {str(e)}"
        logger.error(f"❌ {error_msg}\n{traceback.format_exc()}")
        return ProcessorResponse(
            success=False,
            message=error_msg,
            error=str(e)
        )

# Try multiple possible locations for wkhtmltopdf
@global_metrics.timing()
def get_wkhtmltopdf_path():
    possible_paths = [
        '/usr/local/bin/wkhtmltopdf',  # Common macOS location
        '/usr/bin/wkhtmltopdf',        # Common Linux location
        '/opt/homebrew/bin/wkhtmltopdf', # Apple Silicon Homebrew location
        # Add more paths as needed
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
    
    return None

@global_metrics.timing()
async def create_google_document(content: str, blob_name: str, base_folder_id: str = None, credentials_path: str = None, credentials_dict: dict = None, json_parametros: dict = None) -> dict:
    """
    Create a Google Document with the provided content and also upload the HTML version
    
    Args:
        content (str): The content to add to the document (HTML format)
        blob_name (str): The blob name to use for the document title
        base_folder_id (str, optional): The ID of the base folder
        credentials_path (str, optional): Path to service account credentials file
        credentials_dict (dict, optional): Dictionary containing service account credentials
        
    Returns:
        dict: A dictionary containing the document ID, document link, and folder structure
    """
    try:
        logger.info(f"🔄 Creating Google Document for blob: '{blob_name}'")
        
        
        
        # Initialize the Google Drive client
        drive_client = GoogleDriveClient(
            credentials_path=credentials_path,
            credentials_dict=credentials_dict
        )
        
        # Parse the blob path into components
        path_components = blob_name.split('/')
        
        # Extract the filename (last component)
        if len(path_components) > 0:
            filename = path_components[-1]
            folder_components = path_components[:-1]
        else:
            filename = blob_name
            folder_components = []
        
        # Create folder structure
        folder_structure = {}
        current_folder_id = base_folder_id

        path_modulo = json_parametros.get('modulo')
        path_nucleo = json_parametros.get('nucleo')
        
        if folder_components:
            logger.info(f"Creating folder structure: {'/'.join(folder_components)}")
            
            # Track the full path as we build it
            current_path = ""
            
            for folder_name in folder_components:
                if not folder_name:  # Skip empty folder names
                    continue
                    
                # Update the current path
                if current_path:
                    current_path += f"/{folder_name}"
                else:
                    current_path = folder_name
                
                #pasta correta
                tema_modulo_folder = drive_client.find_or_create_folder(path_modulo, current_folder_id)

                # Find or create the folder
                current_folder_id = drive_client.find_or_create_folder(tema_modulo_folder, current_folder_id)
                folder_structure[current_path] = current_folder_id
        
        # Create the document in the final folder
        document_id = drive_client.create_document(
            title=path_nucleo.replace('.json', '.doc'),
            content=content,
            folder_id=current_folder_id
        )
        
        # Generate a shareable link
        document_link = drive_client.get_file_link(document_id)
        
        logger.info(f"✅ Google Document created successfully")
        logger.info(f"📄 Document ID: {document_id}")
        logger.info(f"🔗 Document Link: {document_link}")
        
        return {
            "document_id": document_id,
            "document_link": document_link,
            "folder_structure": folder_structure,
            "final_folder_id": current_folder_id
        }
    except Exception as e:
        error_msg = f"Failed to create Google Document: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)

@global_metrics.timing()
async def save_json_to_drive(json_content: str, blob_name: str, base_folder_id: str = None, credentials_path: str = None, credentials_dict: dict = None, json_parametros: dict = None) -> dict:
        """
        Saves a JSON content to Google Drive in the same folder as the original text document.

        Args:
            json_content (dict): The JSON content to save.
            blob_name (str): The name of the original blob (used to determine the folder).
            base_folder_id (str, optional): The ID of the base folder in Google Drive.
            credentials_path (str, optional): Path to the Google Drive credentials file.
            credentials_dict (dict, optional): Dictionary containing Google Drive credentials.

        Returns:
            dict: A dictionary containing the file ID and the shareable link.
        """
        try:
            logger.info(f"🔄 Saving JSON to Google Drive for blob: '{blob_name}'")

            # Initialize the Google Drive client
            drive_client = GoogleDriveClient(
                credentials_path=credentials_path,
                credentials_dict=credentials_dict
            )

            # Parse the blob path into components
            path_components = blob_name.split('/')

            # Extract the filename (last component)
            if len(path_components) > 0:
                filename = path_components[-1].replace(".txt", ".json")  # Change extension to .json
                folder_components = path_components[:-1]
            else:
                filename = blob_name.replace(".txt", ".json")
                folder_components = []
            folder_components.insert(-1, "JSON")
            # Create folder structure
            current_folder_id = base_folder_id
            if folder_components:
                logger.info(f"Creating folder structure: {'/'.join(folder_components)}")
                for folder_name in folder_components:
                    if not folder_name:  # Skip empty folder names
                        continue
                    current_folder_id = drive_client.find_or_create_folder(folder_name, current_folder_id)

            # Convert JSON to string
            json_string = json.dumps(json_content, ensure_ascii=False, indent=4)

            path_nucleo = json_parametros.get('nucleo')

            # Upload the JSON file
            file_id = drive_client.create_document(
                title=path_nucleo,
                content=json_string,
                folder_id=current_folder_id
            )

            # Generate a shareable link
            file_link = drive_client.get_file_link(file_id)

            logger.info(f"✅ JSON saved to Google Drive successfully")
            logger.info(f"📄 File ID: {file_id}")
            logger.info(f"🔗 File Link: {file_link}")

            return {
                "file_id": file_id,
                "file_link": file_link
            }
        except Exception as e:
            error_msg = f"Failed to save JSON to Google Drive: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)

@global_metrics.timing()
def get_process_type(area_conhecimento: str, context_type: str) -> ProcessType:

    logger.info(f"🔄 Getting process type for area_conhecimento: {area_conhecimento} and context_type: {context_type}")
    
    if context_type.lower() == "suavizacao":  # Adicionado .lower() para normalizar a entrada
        return ProcessType.suavization_03024  # Já está correto, usando o enum
    elif context_type.lower() == "contextualizacao":
        if area_conhecimento == "TI":
            return ProcessType.contextualization_to_TI
        elif area_conhecimento == "Engenharia":
            return ProcessType.contextualization_to_engenharia_00221
        elif area_conhecimento == "Gestão":
            return ProcessType.contextualization_to_gestao_00962
        elif area_conhecimento == "Humanas":
            return ProcessType.contextualization_to_humanidades_00908
        elif area_conhecimento == "Economia Criativa":
            return ProcessType.contextualization_to_engenharia_00221
        elif area_conhecimento == "Saúde":
            return ProcessType.contextualization_to_saude_00962
        elif area_conhecimento == "Direito":
            return ProcessType.contextualization_to_direito
    
    # Se chegou aqui, significa que não encontrou um tipo válido
    raise ValueError(f"Invalid combination of area_conhecimento='{area_conhecimento}' and context_type='{context_type}'")


@global_metrics.timing()
async def process_single_nc(json_content: dict, json_parametros: dict) -> ProcessorResponse:
    """Process a single NC file using a JSON dict directly."""
    max_retries = 3  # Número máximo de tentativas para operações do Google Drive
    
    try:
        # Validar parâmetros obrigatórios
        required_params = ['context_type', 'areaConhecimento', 'tema_code', 'modulo', 'titulo_atual']
        missing_params = [param for param in required_params if not json_parametros.get(param)]
        if missing_params:
            raise ValueError(f"Parâmetros obrigatórios ausentes: {', '.join(missing_params)}")

        # Validar conteúdo JSON
        if not isinstance(json_content, dict):
            try:
                json_content = json.loads(json_content) if isinstance(json_content, str) else json_content
            except (json.JSONDecodeError, TypeError):
                raise ValueError("Conteúdo JSON inválido")

        # Get the context type from parameters
        context_type = json_parametros.get('context_type')
        area_conhecimento = json_parametros.get('areaConhecimento')
        tema_code = json_parametros.get('tema_code')
        
        # If context type is suavizacao_contextualizacao, we need to process both
        if context_type == "suavizacao_contextualizacao":
            # First do suavizacao
            process_type = get_process_type(area_conhecimento, "suavizacao")
            processor = CloudContentProcessor(tema_code, process_type)
            result_suavizacao = await processor.process_file_async(json_content, folder_id=None, json_parametros=json_parametros)
            
            if not result_suavizacao:
                raise Exception("Falha no processo de suavização")
            
            # Then do contextualizacao using the suavized content
            context_type = "contextualizacao"  # Change context type for second processing
            process_type = get_process_type(area_conhecimento, context_type)
            processor = CloudContentProcessor(tema_code, process_type)
            result = await processor.process_file_async(result_suavizacao, folder_id=None, json_parametros=json_parametros)
            
            if not result:
                raise Exception("Falha no processo de contextualização após suavização")
            
            return ProcessorResponse(
                success=True,
                message="File processed with both suavizacao and contextualizacao successfully",
                data=result
            )
                    
        process_type = get_process_type(json_parametros.get('areaConhecimento'), json_parametros.get('context_type'))

        # Get credentials path
        credentials_path = get_root_path() + '/mydrive.json'
        logger.info(f"🔑 Using credentials from: {credentials_path}")

        # Create the folder structure in Google Drive with credentials
        drive_client = GoogleDriveClient(credentials_path=credentials_path)
        
        # Use the correct base folder ID
        path_google_drive = "1i6UkhDYe59L1Yf6u2rc-iF37ozVgPfId"
        logger.info(f"📁 Using base Google Drive folder ID: {path_google_drive}")
        
        # Create the tema_code folder inside path_google_drive with retry
        folder_name = json_parametros.get('tema_code')
        tema_folder = None
        last_error = None
        
        for attempt in range(max_retries):
            try:
                tema_folder = drive_client.find_or_create_folder(folder_name, parent_id=path_google_drive)
                if tema_folder:
                    logger.info(f"📁 Created/found tema folder with ID: {tema_folder} (attempt {attempt + 1})")
                    break
            except Exception as e:
                last_error = e
                logger.error(f"Erro ao criar pasta (tentativa {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Espera 1 segundo antes de tentar novamente
                else:
                    raise Exception(f"Falha ao criar pasta após {max_retries} tentativas: {str(last_error)}")

        if not tema_folder:
            raise Exception("Não foi possível criar/encontrar a pasta do tema")

        # Get the folder link after creating/finding it
        folder_link = None
        for attempt in range(max_retries):
            try:
                folder_link = drive_client.get_file_link(tema_folder)
                if folder_link:
                    logger.info(f"📁 Tema folder public link: {folder_link}")
                    break
            except Exception as e:
                last_error = e
                logger.error(f"Erro ao obter link da pasta (tentativa {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    raise Exception(f"Falha ao obter link da pasta após {max_retries} tentativas: {str(last_error)}")

        if not folder_link:
            raise Exception("Não foi possível obter o link da pasta")
        
        # Process the content and save to the tema folder
        processor = CloudContentProcessor(tema_code, process_type)
        result = None
        for attempt in range(max_retries):
            try:
                result = await processor.process_file_async(json_content, folder_id=tema_folder, json_parametros=json_parametros)
                if result:
                    logger.info(f"✅ Conteúdo processado com sucesso (tentativa {attempt + 1})")
                    break
            except Exception as e:
                last_error = e
                logger.error(f"Erro ao processar arquivo (tentativa {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    raise Exception(f"Falha ao processar arquivo após {max_retries} tentativas: {str(last_error)}")

        if not result:
            raise Exception("Falha ao processar o conteúdo")

        global_metrics.print_table()
        return ProcessorResponse(
            success=True,
            message="File processed successfully",
            data=result,
            folder_link=folder_link
        )
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return ProcessorResponse(
            success=False,
            message="Failed to process file",
            error=str(e)
        )

# Example usage
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # If a file path is provided as argument, process that single file
        file_path = sys.argv[1]
        asyncio.run(process_single_nc(file_path, tema_code="00908", process_type=ProcessType.CONTEXTUALIZATION_TO_ENGENHARIA_00221))
        #Para rodar:
        #python contextualizationN2.py "/Users/User/OneDrive/Documentos/GitHub/estacio/Temas/00962/Modulo 1/nc 3.txt"

    else:
        # Otherwise run the full process
        asyncio.run(main())