import logging
from app.utils.enviar_email import GoogleEmailSender

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        # Inicializa o sender com seu email
        sender = GoogleEmailSender(sender_email="rafael@autenticare.com.br")
        
        # Configurações do e-mail
        to_email = "rafael@autenticare.com.br"  # Você pode alterar para o email desejado
        subject = "Teste de Email - Sistema de Contextualização"
        body = """
        <h1>Teste do Sistema de Email</h1>
        <p>Olá!</p>
        <p>Este é um email de teste do sistema de contextualização.</p>
        <p>Se você está recebendo este email, significa que:</p>
        <ul>
            <li>O sistema de email está funcionando corretamente</li>
            <li>As credenciais do Gmail estão válidas</li>
            <li>A conexão com a API do Gmail está estabelecida</li>
        </ul>
        <p>Por favor, não responda a este email.</p>
        <br>
        <p>Atenciosamente,</p>
        <p>Sistema de Contextualização</p>
        """
        
        # Envia o e-mail (usando HTML)
        logger.info("Tentando enviar email de teste...")
        success, result = sender.send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            is_html=True
        )
        
        if success:
            logger.info(f"✓ Email enviado com sucesso! ID da mensagem: {result}")
        else:
            logger.error(f"❌ Erro ao enviar email: {result}")
            
    except Exception as e:
        logger.error(f"❌ Erro inesperado: {str(e)}")

if __name__ == "__main__":
    main() 