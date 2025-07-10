from google.cloud import tasks_v2
from google.protobuf import duration_pb2
import json
import os
import logging
from google.auth.transport import requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

class CloudTasksService:
    def __init__(self):
        logger.info("Inicializando CloudTasksService...")
        self.client = tasks_v2.CloudTasksClient()
        self.project = os.getenv('GOOGLE_CLOUD_PROJECT')
        self.queue = os.getenv('CLOUD_TASKS_QUEUE', 'contextualizacao-queue')
        self.location = os.getenv('CLOUD_TASKS_LOCATION', 'us-central1')
        # URL base do serviço Cloud Run
        base_url = os.getenv('SERVICE_URL', 'https://microservice-yduqs-api-745371796940.us-central1.run.app')
        # Garante que não há barras duplicadas ao juntar URLs
        self.service_url = f"{base_url.rstrip('/')}/api/context/process"
        
        logger.info(f"CloudTasksService configurado com:")
        logger.info(f"- Project: {self.project}")
        logger.info(f"- Queue: {self.queue}")
        logger.info(f"- Location: {self.location}")
        logger.info(f"- Service URL: {self.service_url}")

    def create_contextualization_task(self, data, user_emails):
        """
        Cria uma task para processar a contextualização em background
        """
        try:
            logger.info("Criando task para contextualização...")
            parent = self.client.queue_path(self.project, self.location, self.queue)
            logger.info(f"Queue path: {parent}")
            
            # Configurar a task com autenticação OIDC
            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': self.service_url,
                    'headers': {
                        'Content-Type': 'application/json',
                    },
                    'body': json.dumps({
                        'data': data,
                        'user_emails': user_emails
                    }).encode(),
                    'oidc_token': {
                        'service_account_email': os.getenv('CLOUD_TASKS_SERVICE_ACCOUNT'),
                        'audience': self.service_url
                    }
                },
                'dispatch_deadline': duration_pb2.Duration(seconds=1800)  # 30 minutos (máximo permitido)
            }

            logger.info("Enviando requisição para criar task...")
            response = self.client.create_task(request={'parent': parent, 'task': task})
            logger.info(f"Task criada com sucesso: {response.name}")
            
            return {
                'success': True,
                'task_name': response.name
            }
        except Exception as e:
            logger.error(f"Erro ao criar task: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            } 