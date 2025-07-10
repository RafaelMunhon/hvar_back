import ssl
import certifi
import logging
from dataclasses import dataclass
from typing import Optional, Dict
from aiohttp import TCPConnector
from OpenSSL import SSL

logger = logging.getLogger(__name__)

@dataclass
class SSLConfig:
    verify_ssl: bool = True
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    ca_path: Optional[str] = None
    ciphers: str = 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384'
    minimum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2
    verify_hostname: bool = True

class SSLContextBuilder:
    """Builder for creating secure SSL contexts with modern settings."""
    
    def __init__(self, config: SSLConfig = SSLConfig()):
        self.config = config
        self._context = None
    
    def create_context(self) -> ssl.SSLContext:
        """Create a new SSL context with secure defaults."""
        # Create context with secure protocol
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=certifi.where()
        )
        
        # Set minimum version
        context.minimum_version = self.config.minimum_version
        
        # Disable older versions
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1
        
        # Enable host name checking
        context.check_hostname = self.config.verify_hostname
        
        # Set cipher suites
        context.set_ciphers(self.config.ciphers)
        
        # Additional security options
        context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE  # Prefer server's cipher order
        context.options |= ssl.OP_SINGLE_DH_USE  # Ensure perfect forward secrecy
        context.options |= ssl.OP_SINGLE_ECDH_USE
        context.options |= ssl.OP_NO_COMPRESSION  # Disable compression (CRIME attack)
        
        # Load certificates if provided
        if self.config.cert_path and self.config.key_path:
            try:
                context.load_cert_chain(
                    self.config.cert_path,
                    self.config.key_path
                )
            except Exception as e:
                logger.error(f"Failed to load certificate chain: {e}")
                raise
        
        # Load custom CA if provided
        if self.config.ca_path:
            try:
                context.load_verify_locations(self.config.ca_path)
            except Exception as e:
                logger.error(f"Failed to load CA certificate: {e}")
                raise
        
        self._context = context
        return context
    
    def create_tcp_connector(self, **kwargs) -> TCPConnector:
        """Create an aiohttp TCPConnector with SSL context."""
        if not self._context:
            self.create_context()
        
        connector_kwargs = {
            'ssl': self._context if self.config.verify_ssl else False,
            **kwargs
        }
        
        return TCPConnector(**connector_kwargs)

def verify_ssl_config() -> Dict[str, bool]:
    """Verify SSL/TLS configuration and return status."""
    status = {}
    
    # Check OpenSSL version
    openssl_version = SSL.SSLeay_version(SSL.SSLEAY_VERSION).decode()
    status['openssl_version'] = openssl_version
    
    # Check available protocols
    context = ssl.create_default_context()
    
    # Check TLS support without using supported_versions
    try:
        # Try to set minimum version to TLS 1.2 and 1.3
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        status['tls_1_2_supported'] = True
    except (AttributeError, ValueError):
        status['tls_1_2_supported'] = False
        
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        status['tls_1_3_supported'] = True
    except (AttributeError, ValueError):
        status['tls_1_3_supported'] = False
    
    # Check if using system certificates
    status['using_system_certs'] = certifi.where() is not None
    
    # Check cipher suites
    try:
        ciphers = context.get_ciphers()
        status['strong_ciphers_available'] = any(
            cipher['protocol'] in ('TLSv1.2', 'TLSv1.3')
            and 'GCM' in cipher['name']
            for cipher in ciphers
        )
    except Exception as e:
        logger.error(f"Failed to check cipher suites: {e}")
        status['strong_ciphers_available'] = False
    
    return status

def log_ssl_config(config: SSLConfig):
    """Log SSL configuration details."""
    logger.info("SSL Configuration:")
    logger.info(f"- Verify SSL: {config.verify_ssl}")
    logger.info(f"- Verify Hostname: {config.verify_hostname}")
    logger.info(f"- Minimum TLS Version: {config.minimum_version.name}")
    logger.info(f"- Custom Cert Path: {'Yes' if config.cert_path else 'No'}")
    logger.info(f"- Custom Key Path: {'Yes' if config.key_path else 'No'}")
    logger.info(f"- Custom CA Path: {'Yes' if config.ca_path else 'No'}")
    
    status = verify_ssl_config()
    logger.info("SSL Status:")
    for key, value in status.items():
        logger.info(f"- {key}: {value}") 