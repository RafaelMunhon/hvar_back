"""FFMPEG configuration module.

This module provides configuration and path management for FFMPEG operations.
"""

import os
import logging
import shutil
from pathlib import Path
from app.core.config_manager import get_config_manager

logger = logging.getLogger(__name__)

def get_base_path() -> str:
    """Get the base path for the application"""
    return str(Path(__file__).parent.parent)

def get_root_path() -> str:
    """Get the root path of the project (one level above app)"""
    return str(Path(__file__).parent.parent.parent)

def get_temp_files_path() -> str:
    """Get the path for temporary files"""
    config = get_config_manager()
    return config.get_resource_config().temp_file_base_path

def get_videos_finalized_path():
    """
    Obtém o caminho para a pasta de arquivos temporários.

    Retorna:
    - Caminho para a pasta de arquivos temporários
    """
    base_path = get_base_path()
    return os.path.join(base_path, "videosFinalizados")

def get_temp_files_pexel_path() -> str:
    """Get the path for Pexel temporary files"""
    return os.path.join(get_base_path(), "videoPexel")

def get_files_estudio_videos_path() -> str:
    """Get the path for studio video files"""
    return os.path.join(get_base_path(), "downloadEstudio")

def get_temp_output_jsons_path() -> str:
    """Get the path for temporary JSON output files"""
    return os.path.join(get_base_path(), "output_jsons")

def get_videos_heygen_path() -> str:
    """Get the path for HeyGen video files"""
    return os.path.join(get_base_path(), "downloadHeygen")

def get_json_output_zip_path() -> str:
    """Get the path for zipped JSON output files"""
    return os.path.join(get_base_path(), "json_output_zip")

def get_output_jsons_path() -> str:
    """Get the path for JSON output files"""
    return os.path.join(get_base_path(), "output_jsons")

def get_envato_images_path() -> str:
    """Get the path for Envato images"""
    return os.path.join(get_base_path(), "downloadEnvato")

class Error(Exception):
    """Base exception for FFMPEG errors"""
    def __init__(self, message: str, stderr: str = None):
        super().__init__(message)
        self.stderr = stderr

def ensure_directories():
    """Ensure all required directories exist"""
    directories = [
        get_temp_files_path(),
        get_temp_output_jsons_path(),
        get_videos_heygen_path(),
        get_json_output_zip_path(),
        get_output_jsons_path(),
        get_envato_images_path(),
        get_temp_files_pexel_path(),
        get_files_estudio_videos_path()
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            raise

def clean_temp_directories():
    """Clean up temporary directories.
    
    This function removes all files from temporary directories while preserving
    the directory structure. It uses the ResourceManager's configuration for
    the temporary file path.
    """
    try:
        # Get paths to clean
        temp_paths = [
            get_temp_files_path(),
            get_temp_output_jsons_path(),
            get_videos_heygen_path(),
            get_json_output_zip_path(),
            get_envato_images_path(),
            get_files_estudio_videos_path(),
            get_videos_finalized_path(),
        ]
        
        for path in temp_paths:
            if os.path.exists(path):
                logger.info(f"Cleaning directory: {path}")
                try:
                    # Remove directory contents but keep the directory
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        try:
                            if os.path.isfile(item_path):
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                        except Exception as e:
                            logger.warning(f"Failed to remove {item_path}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Failed to clean directory {path}: {str(e)}")
            else:
                logger.info(f"Directory does not exist, creating: {path}")
                os.makedirs(path, exist_ok=True)
                
        logger.info("Temporary directories cleaned successfully")
    except Exception as e:
        logger.error(f"Error cleaning temporary directories: {str(e)}")
        raise

# Initialize directories on module import
ensure_directories()