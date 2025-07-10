
from flask import Blueprint, jsonify, request
from app.services.video_service import gerar_video_template_3_roteiro
import logging
from app.services.audiobook_service import audiobook
from app.services.podcast_service import podcast
from app.services.audioqa_service import audioqa
from app.services.microlearning_service import microlearning


audiovideo_bp = Blueprint('api', __name__)

@audiovideo_bp.route("/generate", methods=['POST'])
def create_video_audio():
    logging.info("Recebendo requisição para gerar vídeo e áudio")
    envato = True

    try:
        data = request.get_json()
        if not data:
            raise ValueError("JSON de entrada está vazio ou inválido")
    except Exception as e:
        logging.error(f"Erro ao obter JSON: {e}")
        return jsonify({"error": "Erro ao processar o JSON"}), 400

    try:
        #audiobook_response = audiobook(data)
        #if not audiobook_response.get("success", False):
        #    raise ValueError(audiobook_response.get('error', 'Erro desconhecido'))
        
        #podcast_response = podcast(data)
        #if not podcast_response.get("success", False):
        #    raise ValueError(podcast_response.get('error', 'Erro desconhecido'))
        
        #qa_response = audioqa(data)
        #if not qa_response.get("success", False):
        #    raise ValueError(qa_response.get('error', 'Erro desconhecido'))
        
        #microlearning_response = microlearning(data)
        #if not microlearning_response.get("success", False):
        #    raise ValueError(microlearning_response.get('error', 'Erro desconhecido'))

        resultado = gerar_video_template_3_roteiro(data, envato)
        return jsonify(resultado), 200
    except ValueError as e:
        logging.error(f"Erro ao gerar audiobook: {e}")
        return jsonify({"error": "Falha ao gerar audio", "detalhes": str(e)}), 500
    except Exception as e:
        logging.error(f"Erro ao gerar vídeo: {e}")
        return jsonify({"error": "Erro interno ao gerar vídeo"}), 500
