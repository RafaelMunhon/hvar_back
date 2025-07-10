import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import logging
import pickle
from typing import Union

logger = logging.getLogger(__name__)

class GoogleEmailSender:
    def __init__(self, credentials_path: str = None, sender_email: str = None):
        """
        Initialize the email sender with Google credentials
        Args:
            credentials_path: Path to the credentials JSON file
            sender_email: Email address to send from
        """
        self.credentials_path = credentials_path or os.path.join(os.path.dirname(__file__), '../../credentials.json')
        self.token_path = os.path.join(os.path.dirname(__file__), '../../token.pickle')
        self.scopes = ['https://www.googleapis.com/auth/gmail.send']
        self.service = None
        self.sender_email = sender_email
        
    def _get_gmail_service(self):
        """
        Get authenticated Gmail service
        """
        creds = None
        
        # Tenta carregar as credenciais do arquivo pickle
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
                
        # Se não há credenciais válidas, solicita ao usuário que faça login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Arquivo de credenciais não encontrado em: {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                creds = flow.run_local_server(port=0)
                
            # Salva as credenciais para o próximo uso
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
                
        return build('gmail', 'v1', credentials=creds)
    
    def send_email(self, to_email: Union[str, list], subject: str, body: str, is_html: bool = False):

        """
        Send email using Gmail API
        Args:
            to_email: Single recipient email address or list of recipient email addresses
            subject: Email subject
            body: Email body content
            is_html: Whether the body content is HTML
        """
        try:
            if not self.service:
                self.service = self._get_gmail_service()
                
            message = MIMEMultipart()
            # Converte to_email para lista se for uma string
            if isinstance(to_email, str):
                to_email = [to_email]
                
            # Junta múltiplos e-mails com vírgula
            message['to'] = ', '.join(to_email)
            if self.sender_email:
                message['from'] = self.sender_email
            message['subject'] = subject
            
            # Add body with appropriate MIME type
            content_type = 'html' if is_html else 'plain'
            message.attach(MIMEText(body, content_type))
            
            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send the email
            sent_message = self.service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {len(to_email)} recipient(s). Message ID: {sent_message['id']}")
            return True, sent_message['id']
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False, str(e)

def test_send_email():
    # Inicializa o sender com seu email
    sender = GoogleEmailSender(sender_email="rafael@autenticare.com.br")  # Coloque aqui o email que você usou para criar as credenciais
    
    # Configurações do e-mail
    to_email = "rafael@autenticare.com.br"
    subject = "E-mail de Teste - API Gmail"
    body = """
    <h1>Teste de E-mail</h1>
    <p>Este é um e-mail de teste enviado através da API do Gmail.</p>
    <p>Se você está vendo esta mensagem, o sistema está funcionando corretamente!</p>
    """
    
    # Envia o e-mail (usando HTML)
    success, result = sender.send_email(
        to_email=to_email,
        subject=subject,
        body=body,
        is_html=True
    )
    
    if success:
        print(f"E-mail enviado com sucesso! ID da mensagem: {result}")
    else:
        print(f"Erro ao enviar e-mail: {result}")

if __name__ == "__main__":
    test_send_email() 
