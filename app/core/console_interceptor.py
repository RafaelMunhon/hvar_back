import sys
import logging
import traceback
from io import StringIO
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ConsoleInterceptor:
    """Intercepts and logs all console output"""
    
    def __init__(self):
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.stdout_buffer = StringIO()
        self.stderr_buffer = StringIO()
        
    def start(self):
        """Start intercepting console output"""
        sys.stdout = self
        sys.stderr = self
        
        # Override sys.excepthook to catch unhandled exceptions
        sys.excepthook = self.handle_exception
        
        logger.info("Console interception started")
        
    def stop(self):
        """Stop intercepting console output"""
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        sys.excepthook = sys.__excepthook__
        
        # Log any remaining output
        stdout_content = self.stdout_buffer.getvalue()
        stderr_content = self.stderr_buffer.getvalue()
        
        if stdout_content:
            logger.info(f"Console output:\n{stdout_content}")
        if stderr_content:
            logger.error(f"Console errors:\n{stderr_content}")
            
        logger.info("Console interception stopped")
        
    def write(self, text: str):
        """Write to both original stream and buffer"""
        timestamp = datetime.utcnow().isoformat()
        
        # Write to original stream
        if sys.stdout == self:
            self.original_stdout.write(text)
            self.stdout_buffer.write(f"[{timestamp}] {text}")
        else:
            self.original_stderr.write(text)
            self.stderr_buffer.write(f"[{timestamp}] {text}")
            
    def flush(self):
        """Flush both original stream and buffer"""
        if sys.stdout == self:
            self.original_stdout.flush()
            self.stdout_buffer.flush()
        else:
            self.original_stderr.flush()
            self.stderr_buffer.flush()
            
    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle unhandled exceptions"""
        # Format the exception
        exception_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        # Log the exception
        logger.error(f"Unhandled exception:\n{exception_text}")
        
        # Call the original excepthook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Global interceptor instance
_console_interceptor: Optional[ConsoleInterceptor] = None

def start_console_interception():
    """Start intercepting console output"""
    global _console_interceptor
    if _console_interceptor is None:
        _console_interceptor = ConsoleInterceptor()
        _console_interceptor.start()

def stop_console_interception():
    """Stop intercepting console output"""
    global _console_interceptor
    if _console_interceptor is not None:
        _console_interceptor.stop()
        _console_interceptor = None 