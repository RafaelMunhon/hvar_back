from app.videoPexel.config import PRESERVED_WORDS

def process_text(text):
    """
    Processa um texto substituindo palavras que precisam ter sua grafia preservada.
    
    Recebe um texto e verifica cada palavra contra um dicionário de palavras preservadas,
    substituindo-as pela forma correta quando encontradas. Por exemplo, nomes próprios
    ou siglas que devem manter uma grafia específica.

    Args:
        text (str): O texto a ser processado

    Returns:
        str: O texto processado com as palavras preservadas substituídas por suas formas corretas.
             Se o texto de entrada for vazio, retorna o próprio texto.
    """
    if not text:
        return text
        
    words = text.split()
    for i, word in enumerate(words):
        lower_word = word.lower()
        if lower_word in PRESERVED_WORDS:
            words[i] = PRESERVED_WORDS[lower_word]
    
    return ' '.join(words)

def add_preserved_word(word, correct_form):
    """
    Adiciona uma nova palavra ao dicionário de palavras preservadas com suas variações.

    Recebe uma palavra e sua forma correta e adiciona ao dicionário PRESERVED_WORDS
    em três variações: minúscula, maiúscula e capitalizada.

    Args:
        word (str): A palavra a ser preservada
        correct_form (str): A forma correta/padronizada da palavra

    Returns:
        None
    """
    PRESERVED_WORDS[word.lower()] = correct_form
    PRESERVED_WORDS[word.upper()] = correct_form
    PRESERVED_WORDS[word.capitalize()] = correct_form 