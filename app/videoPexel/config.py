# Configurações e constantes do projeto
PEXELS_API_KEY = "Yuyg91HW4pxA7DPLVrJiacMnmiBcNvHgp0rT8hs00SEyJmRSANHUeuwB"
PEXELS_API_URL = "https://api.pexels.com/videos/search?query={query}&per_page=30"
MIN_DURATION = 5
MAX_DURATION = 20
BACKGROUND_MUSIC_VOLUME = 0.25  # Volume da música de fundo (25% do volume original)
VOICEOVER_VOLUME = 1.0  # Volume da narração (100%)
DEFAULT_PROMPT = "Educação e tecnologia transformando o futuro"

# Configurações de vídeo
VIDEO_FORMATS = {
    "desktop": {
        "width": 3840,
        "height": 2160,
        "min_width": 1920,
        "min_height": 1080
    },
    "mobile": {
        "width": 1080,
        "height": 1920,
        "min_width": 720,
        "min_height": 1280
    }
}

# Configurações de música
JAMENDO_CLIENT_ID = "1b32d833"
JAMENDO_API_URL = "https://api.jamendo.com/v3.0"
JAMENDO_FORMATS = {
    "mp32": "MP3 192k",
    "mp31": "MP3 128k",
    "ogg": "Ogg Vorbis q5",
}

# Configurações de logo
LOGO_SCALE = {
    "mobile": 0.21,
    "desktop": 0.30,
}

# Dicionário de palavras preservadas e suas formas corretas
PRESERVED_WORDS = {
    'autenticar': 'Autenticare',
    'autenticare': 'Autenticare',
    'Autenticar': 'Autenticare',
    'Hilux': 'YDUQS',
    # Outras palavras podem ser adicionadas aqui
}

# Função para adicionar novas palavras preservadas
def add_preserved_word(word, correct_form):
    """
    Adiciona uma nova palavra ao dicionário de palavras preservadas
    Args:
        word: palavra original
        correct_form: forma correta da palavra
    """
    PRESERVED_WORDS[word.lower()] = correct_form
    PRESERVED_WORDS[word.upper()] = correct_form
    PRESERVED_WORDS[word.capitalize()] = correct_form