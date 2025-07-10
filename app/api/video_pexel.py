from flask import Blueprint, jsonify, request
from app.config.ffmpeg import clean_temp_directories
from app.videoPexel.generate_video_pexel import generate_video
from app.videoPexel.narration import get_available_voices
from app.bd.bd import consultar_videos_pexel  # Vamos criar esta função
import logging

video_pexel_bp = Blueprint('video_pexel', __name__)
logger = logging.getLogger(__name__)

@video_pexel_bp.route("/generate", methods=['POST'])
async def create_video():
    """
    Cria um vídeo Pexel com base nos dados recebidos.

    Tenta criar um vídeo Pexel com base nos dados recebidos.

    Retorna:
        JSON com o resultado da criação do vídeo Pexel  
    """
    try:
        data = request.json
        logger.info(f"Dados recebidos: {data}")

        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400

        # Mapeia os campos recebidos para o formato esperado
        formatted_data = {
            'format_type': 'mobile' if data.get('format') == '1' else 'desktop',
            'music_type': data.get('music_style'),
            'num_scenes': data.get('num_scenes'),
            'theme_text': data.get('theme'),
            'voice': data.get('voice'),
            'site': data.get('site')
        }

        # Validar campos obrigatórios
        required_fields = ['format_type', 'music_type', 'num_scenes', 'theme_text']
        missing_fields = [field for field in required_fields if not formatted_data.get(field)]
        
        if missing_fields:
            return jsonify({"error": f"Campos obrigatórios ausentes: {missing_fields}"}), 400

        # Gerar vídeo
        result = await generate_video(**formatted_data)
        clean_temp_directories()

        if result:
            return jsonify(result), 200
        else:
            return jsonify({"error": "Falha ao gerar vídeo"}), 500

    except Exception as e:
        logger.error(f"Erro ao gerar vídeo: {str(e)}", exc_info=True)
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

@video_pexel_bp.route("/voices", methods=['GET'])
def get_voices():
    """
    Endpoint para obter as vozes disponíveis para narração.
    
    Returns:
        JSON com as vozes disponíveis e seus detalhes
    """
    try:
        voices = get_available_voices()
        if voices:
            return jsonify({"voices": voices}), 200
        else:
            return jsonify({"error": "Nenhuma voz disponível encontrada"}), 404
            
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar vozes: {str(e)}"}), 500

@video_pexel_bp.route("/list", methods=['GET'])
def list_videos():
    """
    Lista todos os vídeos Pexel salvos no banco de dados.

    Tenta listar todos os vídeos Pexel salvos no banco de dados.

    Retorna:
        JSON com o resultado da lista de vídeos Pexel   
    """
    try:
        videos = consultar_videos_pexel()
        return jsonify({
            "status": "success",
            "videos": videos
        }), 200
    except Exception as e:
        logger.error(f"Erro ao listar vídeos: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Erro ao buscar vídeos"
        }), 500


