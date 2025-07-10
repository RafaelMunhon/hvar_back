# audiobook_service.py (Atualizado)

import logging
import os
import uuid
import re
import tempfile
from google.cloud import texttospeech
from app.bd.bd import inserir_audio
from datetime import datetime
from app.services.vertexai_service import melhorar_texto_com_gemini
from app.common.audiobookprompt import audiobookprompt
from google.cloud import storage
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configurações do GCS
PROJECT_ID = "conteudo-autenticare"
BUCKET_NAME = "conteudo-autenticare-audios"

logging.info(f"PROJECT_ID: {PROJECT_ID}")
logging.info(f"BUCKET_NAME: {BUCKET_NAME}")

# Define as coleções de vozes
FEMALE_VOICES = [
    "pt-BR-Chirp3-HD-Aoede",
    "pt-BR-Chirp3-HD-Kore",
    "pt-BR-Chirp3-HD-Leda",
    "pt-BR-Chirp3-HD-Zephyr"
]

MALE_VOICES = [
    "pt-BR-Chirp3-HD-Charon",
    "pt-BR-Chirp3-HD-Fenrir",
    "pt-BR-Chirp3-HD-Orus",
    "pt-BR-Chirp3-HD-Puck"
]

# Variáveis para controlar a rotação sequencial de vozes
_last_female_index = -1
_last_male_index = -1

# Função de seleção de vozes com rotação sequencial
def select_voices(content_id=None):
    """
    Seleciona um par de vozes (uma feminina, uma masculina) usando rotação sequencial.
    Garante que cada audiobook consecutivo use vozes diferentes.

    Args:
        content_id: Ignorado nesta implementação para garantir rotação contínua

    Returns:
        tuple: (female_voice, male_voice) nomes para usar
    """
    global _last_female_index, _last_male_index

    # Avança para a próxima voz feminina
    _last_female_index = (_last_female_index + 1) % len(FEMALE_VOICES)
    female_voice = FEMALE_VOICES[_last_female_index]

    # Avança para a próxima voz masculina
    _last_male_index = (_last_male_index + 1) % len(MALE_VOICES)
    male_voice = MALE_VOICES[_last_male_index]

    logging.info(f"Selecionando próximas vozes na rotação: Feminina={female_voice}, Masculina={male_voice}")

    return female_voice, male_voice

# Função para criar parâmetros de voz
def create_voice_params(voice_name):
    """
    Cria parâmetros de seleção de voz para o nome de voz especificado.

    Args:
        voice_name: Nome da voz a ser usada

    Returns:
        Objeto VoiceSelectionParams
    """
    return texttospeech.VoiceSelectionParams(
        language_code="pt-BR",
        name=voice_name
    )

# ====== FUNÇÃO APRIMORADA PARA LIMPAR TEXTO ANTES DA NARRAÇÃO ======

def limpar_texto_para_narrar(texto):
    """
    Remove marcações de pontuação explícitas e timestamps antes da narração.
    Versão aprimorada com tratamento mais abrangente.

    Args:
        texto: Texto com possíveis marcações de pontuação e timestamps

    Returns:
        Texto limpo pronto para narração
    """
    if not texto:
        return texto

    # 1. Remover timestamps entre parênteses - Ex: (0:00), (1:23)
    texto = re.sub(r'\(\d+:\d+\)', '', texto)

    # 2. Remover menções explícitas de pontuação (versão melhorada)
    pontuacoes = [
        "vírgula", "virgula", "VÍRGULA", "VIRGULA",
        "ponto", "PONTO", "ponto final", "PONTO FINAL",
        "dois pontos", "DOIS PONTOS",
        "ponto e vírgula", "ponto e virgula",
        "interrogação", "interrogacao",
        "exclamação", "exclamacao"
    ]

    # Substituir todas as pontuações por seus equivalentes
    for palavra in pontuacoes:
        # Determinar qual caractere substituir
        if "virgula" in palavra.lower() or "vírgula" in palavra.lower():
            substituir_por = ','
        elif "ponto final" in palavra.lower():
            substituir_por = '.'
        elif "ponto e virgula" in palavra.lower() or "ponto e vírgula" in palavra.lower():
            substituir_por = ';'
        elif "dois pontos" in palavra.lower():
            substituir_por = ':'
        elif "interrogacao" in palavra.lower() or "interrogação" in palavra.lower():
            substituir_por = '?'
        elif "exclamacao" in palavra.lower() or "exclamação" in palavra.lower():
            substituir_por = '!'
        elif "ponto" in palavra.lower():
            substituir_por = '.'
        else:
            substituir_por = ''

        # Substituir todas as ocorrências, com limites de palavra e insensível a case
        padrao = r'\b' + re.escape(palavra) + r'\b'
        texto = re.sub(padrao, substituir_por, texto, flags=re.IGNORECASE)

    # 3. Remover palavras de marcação especial
    texto = re.sub(r'\b(parágrafo|capitulo|capítulo|seção|secao|título|titulo)\b', '', texto, flags=re.IGNORECASE)

    # 4. Normalizar espaços extras e pontuação duplicada
    texto = re.sub(r'\s+', ' ', texto)  # Espaços múltiplos
    texto = re.sub(r'([.,;:!?])\s*\1+', r'\1', texto)  # Pontuação repetida
    texto = re.sub(r'\s+([.,;:!?])', r'\1', texto)  # Espaço antes de pontuação

    # 5. Normalizar espaço depois de pontuação
    texto = re.sub(r'([.,;:!?])([A-Za-z0-9])', r'\1 \2', texto)

    # 6. Varredura final para remover quaisquer menções isoladas
    for palavra_base in ["ponto", "virgula", "vírgula"]:
        texto = re.sub(r'\b' + palavra_base + r'\b', '', texto, flags=re.IGNORECASE)

    return texto.strip()

# ====== FUNÇÃO PARA LIMPAR TEXTO ANTES DE ENVIAR PARA PROMPT ======

def limpar_texto_antes_de_prompt(texto):
    """
    Limpa o texto antes de passar para o gerador de prompt.
    Isso evita que o texto base contenha indicações de pontuação.
    """
    return limpar_texto_para_narrar(texto)

# ====== FUNÇÕES PARA GERAÇÃO DE PAUSAS EFETIVAS ======

def gerar_pausa_hd_melhorado(duracao_ms=1000):
    """
    Versão melhorada que gera uma pausa MP3 compatível com a continuidade do áudio.
    Usa um método diferente que mantém a continuidade do fluxo de áudio.

    Args:
        duracao_ms: duração da pausa em milissegundos

    Returns:
        bytes: contendo um MP3 silencioso real
    """
    try:
        # Tentar usar pydub se disponível
        try:
            from pydub import AudioSegment

            # Criar um segmento de áudio silencioso com taxa de amostragem compatível
            silence = AudioSegment.silent(duration=duracao_ms, frame_rate=44100)

            # Garantir que o formato seja compatível com o restante do áudio
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_path = temp_file.name

            # Exportar com parâmetros específicos para garantir compatibilidade
            silence.export(
                temp_path,
                format="mp3",
                bitrate="192k",
                parameters=["-ac", "1"]  # Mono, compatível com a voz
            )

            # Ler o arquivo MP3 como bytes
            with open(temp_path, 'rb') as f:
                audio_bytes = f.read()

            # Limpar o arquivo temporário
            os.unlink(temp_path)

            return audio_bytes

        except ImportError:
            logging.warning("Pydub não está instalado. Usando método alternativo simplificado para pausas.")
            # Fallback para um método muito simples que não causa quebras
            # Nesta abordagem, geramos um arquivo de silêncio muito pequeno e o repetimos

            # Criar um arquivo WAV simples com bytes de baixo volume
            with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as f:
                # 1 segundo de silêncio a 44.1kHz, 16 bits, mono
                num_samples = int(44100 * (duracao_ms / 1000))

                # Gerar um sinal quase silencioso (não totalmente zero)
                almost_silence = bytearray()
                for i in range(num_samples):
                    # Valor muito baixo, praticamente inaudível (128 é silêncio para PCM)
                    value = 128
                    almost_silence.append(value)

                f.write(almost_silence)
                temp_file = f.name

            # Ler o arquivo bruto como bytes
            with open(temp_file, 'rb') as f:
                audio_bytes = f.read()

            # Limpar arquivo temporário
            os.unlink(temp_file)

            return audio_bytes

    except Exception as e:
        logging.error(f"Erro ao gerar pausa HD: {e}", exc_info=True)
        # Usar método alternativo simples como último recurso
        tamanho = max(1000, int(duracao_ms * 48))  # Aumentado significativamente
        return bytearray([127] * tamanho)  # Usar valor neutro (127) em vez de zeros

# Função para concatenar áudios de forma segura
def concatenar_audios_seguro(lista_audios):
    """
    Concatena múltiplos blocos de áudio de forma segura preservando a continuidade.
    Usa pydub se disponível para garantir compatibilidade.

    Args:
        lista_audios: Lista de bytes contendo os blocos de áudio

    Returns:
        bytes: Áudio concatenado
    """
    try:
        # Tentar usar pydub para concatenação segura
        try:
            from pydub import AudioSegment

            # Converter cada bloco em um AudioSegment
            segments = []
            for i, audio_bytes in enumerate(lista_audios):
                if not audio_bytes:  # Pular blocos vazios
                    continue

                # Salvar bytes em arquivo temporário
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_file.write(audio_bytes)
                    temp_path = temp_file.name

                try:
                    # Carregar como AudioSegment
                    segment = AudioSegment.from_file(temp_path, format="mp3")
                    segments.append(segment)
                except Exception as e:
                    logging.warning(f"Erro ao carregar bloco {i}: {e}")
                finally:
                    # Remover arquivo temporário
                    os.unlink(temp_path)

            # Concatenar todos os segments
            if segments:
                resultado = segments[0]
                for segment in segments[1:]:
                    resultado += segment

                # Exportar resultado
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_path = temp_file.name

                resultado.export(temp_path, format="mp3", bitrate="192k")

                # Ler resultado
                with open(temp_path, 'rb') as f:
                    audio_final = f.read()

                # Limpar arquivo temporário
                os.unlink(temp_path)

                return audio_final
            else:
                return b''

        except ImportError:
            logging.warning("Pydub não está instalado. Usando concatenação simples.")
            # Fallback para concatenação simples
            return b''.join([audio for audio in lista_audios if audio])

    except Exception as e:
        logging.error(f"Erro ao concatenar áudios: {e}", exc_info=True)
        # Retornar a concatenação simples como fallback
        return b''.join([audio for audio in lista_audios if audio])

# ====== FUNÇÃO DE MODIFICAÇÃO DE PROMPT ======

def modificar_prompt_gemini(prompt):
    """
    Modifica o prompt enviado ao Gemini para evitar que ele gere marcações de pontuação.
    Versão melhorada com instruções mais específicas.
    """
    # Adicionar instruções explícitas para não incluir pontuação falada
    instrucoes_adicionais = """
    INSTRUÇÕES IMPORTANTES:
    1. NÃO inclua palavras de pontuação como "vírgula", "virgula", "ponto", "dois pontos" no texto.
    2. Use os símbolos de pontuação diretamente (,.;:!?) sem escrever seus nomes.
    3. NÃO inclua marcações de tempo como (0:00), (1:23), etc.
    4. NÃO use nenhuma marcação de formatação como "parágrafo", "título", etc.
    5. NÃO escreva a palavra "ponto" ou "vírgula" em nenhuma circunstância.
    """

    # Adicionar ao prompt original
    prompt_modificado = prompt + instrucoes_adicionais

    return prompt_modificado

# ====== FUNÇÕES DE PROCESSAMENTO DE TEXTO E PAUSAS ======

def adicionar_pausas_estrategicas(roteiro):
    """
    Versão aprimorada que adiciona pausas estratégicas em um roteiro para torná-lo mais fluido e natural.

    Args:
        roteiro: O texto do roteiro

    Returns:
        Texto do roteiro com pausas estratégicas adicionadas
    """
    import re

    logging.info("Adicionando pausas estratégicas ao roteiro")

    # Limpar o texto antes de adicionar pausas
    roteiro = limpar_texto_para_narrar(roteiro)

    # Preservar as pausas de seção existentes
    partes = roteiro.split('[pausa]')
    resultado = []

    # Palavras-chave que indicam necessidade de pausas
    palavras_chave_pausa = [
        "Primeiramente", "Em primeiro lugar", "Por exemplo", "Nesse sentido",
        "Portanto", "Assim", "Contudo", "Entretanto", "Além disso",
        "Consequentemente", "No entanto", "Em contrapartida", "Em síntese",
        "Concluindo", "Vale ressaltar", "É importante destacar"
    ]

    # Processamento de cada parte principal do roteiro
    for i, parte in enumerate(partes):
        parte = parte.strip()
        if not parte:
            continue

        # Dividir em parágrafos
        paragrafos = re.split(r'\n\s*\n', parte)
        nova_parte = []

        for p_idx, paragrafo in enumerate(paragrafos):
            paragrafo = paragrafo.strip()
            if not paragrafo:
                continue

            # Adicionar pausas entre frases para todas as seções (não apenas o conteúdo principal)
            # Dividir em frases
            frases = re.split(r'(?<=[.!?])\s+', paragrafo)
            frases_com_pausas = []
            buffer = ""

            for f_idx, frase in enumerate(frases):
                frase = frase.strip()
                if not frase:
                    continue

                # Preservar termos em outros idiomas e técnicos
                frase = frase.replace("ownership", "**ownership**")

                # Verificar condições para adicionar pausa
                adicionar_pausa = False

                # 1. Se o buffer já tem conteúdo suficiente
                if buffer and len(buffer + frase) > 120:  # Reduzindo para melhorar a fluência
                    adicionar_pausa = True
                    tipo_pausa = "média"  # Para frases longas
                # 2. Se esta frase contém palavras-chave que indicam mudança de fluxo
                elif any(palavra in frase for palavra in palavras_chave_pausa):
                    adicionar_pausa = True
                    tipo_pausa = "longa"  # Para transições importantes
                # 3. Se é uma frase longa, complexa ou contém elementos específicos
                elif (len(frase) > 80 or
                      ":" in frase or
                      ";" in frase or
                      " – " in frase or
                      "entre outros" in frase.lower() or
                      "por exemplo" in frase.lower()):
                    adicionar_pausa = True
                    tipo_pausa = "média"  # Para frases complexas
                # 4. Se é a última frase de um parágrafo e não é o último parágrafo
                elif f_idx == len(frases) - 1 and p_idx < len(paragrafos) - 1:
                    if buffer:
                        buffer += " " + frase
                    else:
                        buffer = frase
                    frases_com_pausas.append(f"{buffer}\n**(PausaLonga)**")
                    buffer = ""
                    continue

                # Aplicar a pausa se necessário
                if adicionar_pausa:
                    if buffer:
                        if tipo_pausa == "longa":
                            frases_com_pausas.append(f"{buffer}\n**(PausaLonga)**")
                        else:
                            frases_com_pausas.append(f"{buffer}\n**(PausaMédia)**")
                        buffer = frase
                    else:
                        if tipo_pausa == "longa":
                            frases_com_pausas.append(f"{frase}\n**(PausaLonga)**")
                        else:
                            frases_com_pausas.append(f"{frase}\n**(PausaMédia)**")
                        buffer = ""
                else:
                    # Caso contrário, adicione ao buffer
                    if buffer:
                        buffer += " " + frase
                    else:
                        buffer = frase

                    # Se for a última frase e ainda temos conteúdo no buffer
                    if f_idx == len(frases) - 1 and buffer:
                        frases_com_pausas.append(buffer)
                        buffer = ""

            # Adicionar o buffer restante, se houver
            if buffer:
                frases_com_pausas.append(buffer)

            nova_parte.append("\n".join(frases_com_pausas))

        resultado.append("\n".join(nova_parte))

    # Reconstruir o roteiro com as pausas de seção originais
    roteiro_com_pausas = '[pausa]'.join(resultado)

    # Substituir os marcadores de termos especiais
    roteiro_com_pausas = roteiro_com_pausas.replace("**ownership**", "ownership")

    return roteiro_com_pausas


def processar_pausas_no_audio_melhorado(roteiro, client, voice, audio_config):
    """
    Versão melhorada para processar pausas que preserva a continuidade do áudio.

    Args:
        roteiro: O texto do roteiro com marcações de pausa
        client: Cliente do Text-to-Speech
        voice: Parâmetros de voz
        audio_config: Configuração de áudio

    Returns:
        Conteúdo do áudio em bytes
    """
    try:
        logging.info("Processando áudio com pausas estratégicas melhoradas")

        # IMPORTANTE: Limpar o texto antes de processá-lo
        roteiro = limpar_texto_para_narrar(roteiro)

        # Substituir todos os tipos de pausas por um formato uniforme para dividir o texto
        roteiro_normalizado = (roteiro
                               .replace("**(PausaCurta)**", "|||PAUSA_CURTA|||")
                               .replace("**(PausaMédia)**", "|||PAUSA_MEDIA|||")
                               .replace("**(PausaLonga)**", "|||PAUSA_LONGA|||")
                               .replace("**(Pausa)**", "|||PAUSA_MEDIA|||"))

        # Dividir o roteiro nos marcadores de pausa
        partes = re.split(r'\|\|\|PAUSA_(?:CURTA|MEDIA|LONGA)\|\|\|', roteiro_normalizado)

        # Identificar os tipos de pausa no texto original
        tipos_pausa = []
        if "|||PAUSA_CURTA|||" in roteiro_normalizado:
            tipos_pausa.extend(["curta" for _ in re.findall(r'\|\|\|PAUSA_CURTA\|\|\|', roteiro_normalizado)])
        if "|||PAUSA_MEDIA|||" in roteiro_normalizado:
            tipos_pausa.extend(["media" for _ in re.findall(r'\|\|\|PAUSA_MEDIA\|\|\|', roteiro_normalizado)])
        if "|||PAUSA_LONGA|||" in roteiro_normalizado:
            tipos_pausa.extend(["longa" for _ in re.findall(r'\|\|\|PAUSA_LONGA\|\|\|', roteiro_normalizado)])

        # Garantir que temos n-1 tipos de pausas para n blocos
        if len(tipos_pausa) < len(partes) - 1:
            tipos_pausa.extend(["media"] * (len(partes) - 1 - len(tipos_pausa)))

        # Lista para armazenar todos os segmentos
        segmentos = []

        # Gerar o áudio para cada bloco e adicionar uma pausa após cada um
        for i, bloco in enumerate(partes):
            bloco = bloco.strip()
            if not bloco:
                continue

            logging.info(f"Processando bloco de pausa {i+1}/{len(partes)}: {bloco[:50]}...")

            # Limpar novamente antes de sintetizar
            bloco_limpo = limpar_texto_para_narrar(bloco)

            # Sintetizar o áudio deste bloco
            audio_bloco = sintetizar_audio(bloco_limpo, client, voice, audio_config)
            if audio_bloco: # Adiciona apenas se a síntese foi bem-sucedida
                segmentos.append(audio_bloco)

                # Adicionar uma pausa de duração variável após cada bloco (exceto o último)
                if i < len(partes) - 1:
                    tipo_pausa = tipos_pausa[i] if i < len(tipos_pausa) else "media"

                    if tipo_pausa == "curta":
                        pausa = gerar_pausa_hd_melhorado(500)  # Pausa curta: 500ms
                        logging.info("Adicionando pausa CURTA")
                    elif tipo_pausa == "longa":
                        pausa = gerar_pausa_hd_melhorado(1000)  # Pausa longa: 1000ms
                        logging.info("Adicionando pausa LONGA")
                    else:  # pausa média
                        pausa = gerar_pausa_hd_melhorado(700)  # Pausa média: 700ms
                        logging.info("Adicionando pausa MÉDIA")

                    segmentos.append(pausa)
            else:
                logging.warning(f"Síntese do bloco {i+1} falhou ou retornou vazio, pulando.")

        # Concatenar todos os segmentos de forma segura
        return concatenar_audios_seguro(segmentos)

    except Exception as e:
        logging.error(f"Erro ao processar áudio com pausas: {e}", exc_info=True)
        texto_limpo = limpar_texto_para_narrar(roteiro.replace("**(PausaCurta)**", "")
                                .replace("**(PausaMédia)**", "")
                                .replace("**(PausaLonga)**", "")
                                .replace("**(Pausa)**", ""))
        return sintetizar_audio(texto_limpo, client, voice, audio_config)

def limpar_nome_nucleo(nucleo):
    """Limpa o nome do núcleo de todos os prefixos e extensões indesejados"""
    if nucleo is None:
        return ""

    nucleo = str(nucleo)  # Garantir que seja string
    nucleo = nucleo.replace("nc-", "")
    nucleo = nucleo.replace("nc ", "")  # Espaço depois de nc
    nucleo = nucleo.replace(" nc", "")  # Espaço antes de nc
    nucleo = nucleo.replace(".json", "")
    nucleo = nucleo.replace(".txt", "")
    nucleo = nucleo.replace("original", "") # Remove 'original'
    nucleo = nucleo.strip() # Remove espaços extras no início/fim
    return nucleo


def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        logging.info(f"Iniciando upload para o GCS. Bucket: {bucket_name}, Arquivo de origem: {source_file_name}, Destino: {destination_blob_name}")
        storage_client = storage.Client(project=PROJECT_ID)  # Especifica o projeto
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        logging.info(f"Fazendo upload do arquivo {source_file_name} para o bucket {bucket_name}.")
        blob.upload_from_filename(source_file_name)

        logging.info(
            f"Arquivo {source_file_name} foi uploadado para {destination_blob_name} no bucket {bucket_name}."
        )
        gcs_url = f"https://storage.cloud.google.com/{bucket_name}/{destination_blob_name}"

        logging.info(f"URL do GCS: {gcs_url}")  # Log da URL gerada
        return gcs_url  # Retorna a URL do objeto no GCS
    except Exception as e:
        logging.error(f"Erro ao fazer upload para o GCS: {e}", exc_info=True)
        return None


def salvar_arquivo_audio(nome_arquivo_saida, output_dir=None, relative_path=None, audio_content=None):
    try:
        logging.info(f"Iniciando salvamento do arquivo de áudio. Nome do arquivo: {nome_arquivo_saida}, Output dir: {output_dir}, Relative path: {relative_path}")

        # Gerar um nome de arquivo único
        unique_id = uuid.uuid4()
        filename = f"audiobook_{unique_id}.mp3"

        # Cria um nome de arquivo temporário
        temp_file_path = os.path.join(tempfile.gettempdir(), filename)  # Use o filename
        logging.info(f"Caminho do arquivo temporário: {temp_file_path}")

        if audio_content:
            logging.info("Conteúdo de áudio detectado. Escrevendo no arquivo temporário.")
            with open(temp_file_path, "wb") as out:
                out.write(audio_content)
            logging.info("Arquivo temporário escrito com sucesso.")

            # Define o nome do blob no bucket
            # Certifique-se de que relative_path não seja None
            destination_blob_name = os.path.join(relative_path if relative_path else "audios", filename)
            logging.info(f"Destination blob name: {destination_blob_name}")

            # Faz o upload para o GCS
            logging.info(f"Iniciando upload para o GCS. Bucket: {BUCKET_NAME}, Arquivo de origem: {temp_file_path}, Destino: {destination_blob_name}")
            gcs_url = upload_blob(BUCKET_NAME, temp_file_path, destination_blob_name)

            # Remove o arquivo temporário
            logging.info(f"Removendo arquivo temporário: {temp_file_path}")
            os.remove(temp_file_path)
            logging.info("Arquivo temporário removido com sucesso.")

            if gcs_url:
                logging.info(f"URL do GCS obtida com sucesso: {gcs_url}")
                return gcs_url  # Retorna a URL do GCS
            else:
                logging.warning("Falha ao obter a URL do GCS após o upload.")
                return None  # Retorna None em caso de falha no upload
        else:
            logging.warning("Nenhum conteúdo de áudio para salvar.")
            return None  # Retorna None se não houver conteúdo de áudio
    except Exception as e:
        logging.error(f"Erro ao salvar arquivo de áudio: {e}", exc_info=True)
        return None

async def audiobook(data, relative_path=None, output_dir=None, next_titulo_nc=None, is_conteudo_inicial=False, titulo_atual=None, modulo=None, nucleo=None, content_id=None, theme=None):
    """
    Gera um audiobook a partir do conteúdo JSON.
    """
    try:
        logging.info("Iniciando processo de criação do audiobook.")

        # Extrai o conteúdo do data
        conteudo = None
        json_data_para_extracao = None # Para passar para extrair_texto_do_json
        if isinstance(data, dict):
            json_data_para_extracao = data
            if 'conteudo' in data:
                conteudo = data['conteudo']
            elif 'conteudo_conclusao' in data:
                conteudo = data['conteudo_conclusao']
            elif 'conteudo_introducao' in data:
                conteudo = data['conteudo_introducao']
            else:
                # Se nenhuma chave conhecida for encontrada, tente usar o próprio 'data'
                # se ele contiver texto ou for uma lista de componentes
                 if isinstance(data.get('sections'), list) or isinstance(data.get('body'), list): # Exemplo de verificação
                      conteudo = data
                 else:
                     logging.warning("Estrutura de 'data' não reconhecida para extração de conteúdo principal.")
                     conteudo = data # Tenta mesmo assim
        elif isinstance(data, list): # Se data for diretamente a lista de componentes
            conteudo = data
            json_data_para_extracao = {"conteudo": data} # Cria um dict para extrair_texto_do_json
        else:
            conteudo = data  # Se data já for o conteúdo (ex: string)
            json_data_para_extracao = {"conteudo": data}

        logging.info(f"Conteúdo a ser processado: {str(conteudo)[:200]}...") # Mostra início do conteúdo

        # Gerar/Extrair Slug (mantido para compatibilidade, mas não usado para a decisão da intro)
        slug = None
        if isinstance(conteudo, dict):
            slug = conteudo.get("slug")
        elif isinstance(conteudo, list) and len(conteudo) > 0 and isinstance(conteudo[0], dict):
            slug = conteudo[0].get("slug")

        if not slug:
            if titulo_atual:
                slug = titulo_atual.lower().replace(' ', '-')
            else:
                slug = f"audiobook-{uuid.uuid4()}"
            logging.info(f"Gerando slug a partir do título ou UUID: {slug}")
        else:
             logging.info(f"Slug extraído ou mantido: {slug}")

        if not conteudo:
            logging.error("Conteúdo vazio ou inválido após extração inicial")
            return {"error": "Conteúdo vazio ou inválido"}

        # Selecionar vozes com base no content_id
        female_voice_name, male_voice_name = select_voices(content_id)

        # Criar objetos de parâmetros de voz
        voice_intro_resumo = create_voice_params(female_voice_name)
        voice_conteudo = create_voice_params(male_voice_name)

        logging.info(f"Usando voz feminina: {female_voice_name} para introdução/resumo")
        logging.info(f"Usando voz masculina: {male_voice_name} para conteúdo principal")

        # Extrair texto do conteúdo usando a estrutura JSON completa
        texto_extraido = extrair_texto_do_json(json_data_para_extracao if json_data_para_extracao else {"conteudo": conteudo})

        if not texto_extraido:
             # Tenta extrair da forma alternativa se a primeira falhar
             texto_extraido = extrair_texto_do_conteudo(conteudo)
             if not texto_extraido:
                  raise ValueError("Não foi possível extrair texto do JSON de entrada usando nenhum método.")

        logging.info(f"Texto extraído para IA e TTS: {texto_extraido[:200]}...")

        logging.info(f"relative_path: {relative_path}, output_dir: {output_dir}")

        # Chama gerar_audiobook passando todos os dados relevantes
        audio_content = await gerar_audiobook(texto=texto_extraido, slug=slug, # slug ainda é passado, mas não para a decisão da intro
                                       next_titulo_nc=next_titulo_nc,
                                       is_conteudo_inicial=is_conteudo_inicial,
                                       data=data, # Passa o 'data' original para 'conteudo_inicial'
                                       titulo_atual=titulo_atual,
                                       modulo=modulo, nucleo=nucleo,
                                       voice_intro_resumo=voice_intro_resumo,
                                       voice_conteudo=voice_conteudo)

        logging.info("Geração do conteúdo de áudio concluída.")

        if audio_content:
            gcs_url = salvar_arquivo_audio(nome_arquivo_saida="", output_dir=output_dir, relative_path=relative_path, audio_content=audio_content)
            if gcs_url:
                logging.info("Áudio salvo no GCS com sucesso.")
                # Certifica-se de que content_id não é None antes de inserir
                if content_id:
                    inserir_audio(content_id, gcs_url, "audiobook", theme, titulo_atual)
                    logging.info("Registro do áudio inserido no BigQuery.")
                else:
                    logging.warning("content_id é None, não foi possível inserir registro no BigQuery.")

                return {"success": True, "message": "Audiobook gerado com sucesso!",
                        "file_url": gcs_url}
            else:
                 logging.error("Falha ao salvar o áudio no GCS.")
                 return {"success": False, "error": "Erro ao salvar o audiobook no GCS."}
        else:
            logging.error("Falha na geração do conteúdo de áudio (audio_content está vazio).")
            return {"success": False, "error": "Erro interno durante a geração do áudio."}

    except Exception as e:
        logging.error(f"Erro no processo de criação do audiobook: {e}", exc_info=True)
        return {"success": False, "error": f"Erro interno ao criar audiobook: {str(e)}"}


def extrair_texto_do_conteudo(conteudo):
    """
    Extrai texto de uma lista de componentes ou de um dicionário genérico (forma alternativa).
    """
    try:
        texto = ""

        # Se for uma lista, itera sobre os itens
        if isinstance(conteudo, list):
            for item in conteudo:
                if isinstance(item, dict):
                    # Extrai texto de componentes de tipografia
                    if item.get('__component') == 'principais.tipografia' and 'texto' in item:
                        texto_item = item['texto']
                        if texto_item and isinstance(texto_item, str):
                             # Remove tags HTML apenas se for string
                             texto_limpo = re.sub(r'<[^>]+>', ' ', texto_item)
                             texto += texto_limpo + " "
                    # Extrai texto de outros tipos de componentes (tentativa genérica)
                    elif 'texto' in item:
                         texto_item = item['texto']
                         if texto_item and isinstance(texto_item, str):
                              texto += texto_item + " "
                    elif 'conteudo' in item and isinstance(item['conteudo'], str):
                         texto += item['conteudo'] + " "
                    # Adicione outras chaves comuns se necessário: 'descricao', 'enunciado', etc.

        # Se for um dicionário (tentativa genérica)
        elif isinstance(conteudo, dict):
            for key, value in conteudo.items():
                 if isinstance(value, str) and key in ['texto', 'conteudo', 'descricao', 'enunciado', 'title', 'label']: # Campos comuns
                      texto += value + " "
                 elif isinstance(value, list): # Se um valor for outra lista, tenta extrair dela recursivamente
                      texto += extrair_texto_do_conteudo(value) + " "

        # Limpa o texto extraído antes de retornar
        texto_final = limpar_texto_para_narrar(texto)
        logging.info(f"Texto extraído (método alternativo): {texto_final[:100]}...")
        return texto_final.strip()

    except Exception as e:
        logging.error(f"Erro ao extrair texto do conteúdo (método alternativo): {e}", exc_info=True)
        return "" # Retorna vazio em caso de erro


def extrair_dados_do_path(json_path):
    """Extrai título e slug do path do arquivo JSON."""
    try:
        normalized_path = os.path.normpath(json_path)
        parts = normalized_path.split(os.sep)

        if len(parts) >= 3:
            modulo = parts[-2]
            nome_arquivo = parts[-1].replace(".json", "")
            slug = f"{modulo}//{nome_arquivo}".replace(" ", "-").lower()
        else:
            slug = parts[-1].replace(".json", "").lower()

        titulo_nc = parts[-1].replace(".json", "").replace("-", " ").strip()

        return titulo_nc, slug
    except Exception as e:
        logging.error(f"Erro ao extrair dados do path: {e}", exc_info=True)
        return "Tema Desconhecido", "Módulo Desconhecido"


def extrair_texto_do_json(dados):
    """
    Extrai texto de forma mais estruturada a partir de um dicionário JSON.
    Esta função é mais específica para a estrutura esperada.
    """
    try:
        texto = ""
        processed_keys = set()

        def extract_recursive(item):
            nonlocal texto
            if isinstance(item, dict):
                # Prioriza chaves conhecidas
                for key in ["texto", "conteudo", "descricao", "enunciado", "titulo_tema", "alternativa_resposta", "enunciado_questao"]:
                    if key in item and key not in processed_keys:
                        value = item[key]
                        if isinstance(value, str):
                            texto_limpo = re.sub(r'<[^>]+>', ' ', value) # Remove HTML
                            texto += texto_limpo + " "
                            processed_keys.add(key) # Marca como processado para evitar duplicação se aninhado
                        elif isinstance(value, list):
                             extract_recursive(value) # Processa listas aninhadas

                # Processa outras chaves se não foram pegas antes
                for key, value in item.items():
                     if key not in processed_keys:
                         extract_recursive(value) # Processa recursivamente

            elif isinstance(item, list):
                for sub_item in item:
                    extract_recursive(sub_item)
            elif isinstance(item, str):
                 # Se for uma string solta (menos comum no nível superior)
                 texto_limpo = re.sub(r'<[^>]+>', ' ', item)
                 texto += texto_limpo + " "


        # Inicia a extração recursiva a partir do dicionário principal 'dados'
        extract_recursive(dados)

        if not texto:
            logging.warning("Não foi possível encontrar texto usando extração estruturada.")
            # Não lança erro aqui, permite que a função audiobook tente o método alternativo
            return ""

        logging.info("Texto extraído do JSON (método estruturado) com sucesso.")
        texto_final = limpar_texto_para_narrar(texto)
        return texto_final.strip()

    except Exception as e:
        logging.error(f"Erro ao processar JSON (método estruturado): {e}", exc_info=True)
        return "" # Retorna vazio em caso de erro


def gerar_nome_arquivo(titulo_nc):
    """Gera um nome de arquivo único usando UUID e o título."""
    titulo_limpo = re.sub(r'[^\w\s-]', '', titulo_nc).strip()
    titulo_hifenizado = re.sub(r'\s+', '-', titulo_limpo).lower()
    unique_id = uuid.uuid4()
    return f"audiobook__{titulo_hifenizado}__{unique_id}.mp3"


def extrair_info_modulo_nucleo(slug):
    """
    Extrai informações do módulo e núcleo conceitual do slug (usado anteriormente, mantido para referência).
    !! ESTA FUNÇÃO NÃO É MAIS USADA PARA DECIDIR A GERAÇÃO DA INTRODUÇÃO !!
    """
    if not isinstance(slug, str) or not slug:
        logging.warning("Slug inválido para extração de informações: %s", slug)
        return None
    match = re.search(r"modulo-(\d+).*page-(\d+)", slug)
    if match:
        numero_modulo = match.group(1)
        numero_nucleo = match.group(2)
        return {"numero_modulo": numero_modulo, "numero_nucleo": numero_nucleo}
    return None

# NOVA FUNÇÃO: Gerar perguntas reflexivas
async def gerar_perguntas_reflexivas(texto, titulo_nc):
    """
    Gera perguntas reflexivas baseadas no conteúdo do texto e no título do núcleo conceitual.
    Utiliza o Gemini AI para criar perguntas relevantes e estimulantes.

    Args:
        texto: O texto do conteúdo principal
        titulo_nc: O título do núcleo conceitual

    Returns:
        String contendo 2-3 perguntas reflexivas
    """
    try:
        from app.services.vertexai_service import melhorar_texto_com_gemini

        # Determinar se este NC deve receber perguntas reflexivas (alternando)
        # Podemos usar o hash do título para tornar isto determinístico
        import hashlib

        # Se título_nc for None ou vazio, retornar string vazia
        if not titulo_nc:
            logging.info("Título NC vazio ou None, pulando geração de perguntas reflexivas")
            return ""

        hash_value = int(hashlib.md5(titulo_nc.encode()).hexdigest(), 16)
        # Adicionar perguntas a aproximadamente 50% dos NCs
        should_add_questions = hash_value % 2 == 0

        if not should_add_questions:
            logging.info(f"Núcleo '{titulo_nc}' não receberá perguntas reflexivas (determinado via hash)")
            return ""

        logging.info(f"Gerando perguntas reflexivas para o núcleo '{titulo_nc}'")

        # Criar o prompt para o Gemini AI
        prompt = f"""
        Com base no seguinte conteúdo educacional, crie 2-3 perguntas reflexivas que estimulem o pensamento crítico
        e a conexão com a experiência profissional do estudante. As perguntas devem:

        1. Ser abertas (sem resposta única)
        2. Estimular a reflexão sobre aplicações práticas do conteúdo
        3. Encorajar conexões com a realidade profissional do estudante
        4. Ser formuladas em segunda pessoa (você)

        As perguntas devem ter um tom convidativo e não avaliativo, estimulando o estudante a pensar
        além do conteúdo apresentado.

        Título do Núcleo Conceitual: {titulo_nc}

        Conteúdo:
        {texto[:1500]}  # Usar apenas uma parte do texto para evitar tokens excessivos

        Retorne APENAS as perguntas, sem introdução ou conclusão, uma por linha.
        """

        # Modificar o prompt para evitar que gere pontuação narrada
        prompt_modificado = modificar_prompt_gemini(prompt)

        # Gerar as perguntas usando o Gemini
        perguntas = await melhorar_texto_com_gemini(prompt_modificado)

        # Limpar o texto gerado
        perguntas_limpas = limpar_texto_para_narrar(perguntas)

        # Criar o texto de introdução para as perguntas
        texto_final = "\n\nPara estimular sua reflexão sobre este tema, considere as seguintes perguntas: " + perguntas_limpas

        logging.info(f"Perguntas reflexivas geradas com sucesso: {texto_final[:100]}...")
        return texto_final

    except Exception as e:
        logging.error(f"Erro ao gerar perguntas reflexivas: {e}", exc_info=True)
        return ""  # Em caso de erro, retornar string vazia para não afetar o restante do processamento

# NOVA FUNÇÃO: Quebrar frases longas para evitar erros de síntese
def quebrar_frases_longas(texto, max_chars=200):
    """
    Quebra frases muito longas em frases menores, adicionando pontuação quando necessário.

    Args:
        texto: O texto a ser processado
        max_chars: Tamanho máximo de cada frase em caracteres

    Returns:
        Texto com frases divididas de forma adequada
    """
    import re

    # Se o texto for muito curto, retorne sem alterações
    if len(texto) <= max_chars:
        return texto

    # Quebrar o texto em frases existentes (com pontuação)
    frases = re.split(r'(?<=[.!?])\s+', texto)

    # Para cada frase longa, quebrar em partes menores
    resultado = []
    for frase in frases:
        # Se a frase for curta o suficiente, adicione como está
        if len(frase) <= max_chars:
            resultado.append(frase)
            continue

        # Caso contrário, precisamos quebrar esta frase longa
        # Primeiro, procurar por separadores naturais como vírgulas, ponto-e-vírgula, dois pontos
        partes = re.split(r'((?<=[:;,])\s+)', frase)

        # Juntar as partes respeitando o limite de caracteres
        buffer = ""
        for parte in partes:
            if len(buffer + parte) <= max_chars:
                buffer += parte
            else:
                # Se o buffer não estiver vazio, adicione-o ao resultado
                if buffer:
                    # Garantir que termine com alguma pontuação
                    if not re.search(r'[.!?;,:]$', buffer.strip()):
                        buffer += "."
                    resultado.append(buffer.strip())
                    buffer = parte
                else:
                    # Se o buffer estiver vazio, a parte atual é muito longa,
                    # então precisamos dividi-la em pedaços menores
                    palavras = parte.split()
                    parte_atual = ""
                    for palavra in palavras:
                        if len(parte_atual + " " + palavra) <= max_chars:
                            parte_atual = (parte_atual + " " + palavra).strip()
                        else:
                            # Adicionar a parte atual ao resultado
                            if parte_atual:
                                # Garantir que termine com alguma pontuação
                                if not re.search(r'[.!?;,:]$', parte_atual.strip()):
                                    parte_atual += "."
                                resultado.append(parte_atual.strip())
                                parte_atual = palavra
                            else:
                                # Se a palavra for mais longa que max_chars, divida-a
                                # (caso extremo, mas precisamos tratar)
                                chunks = [palavra[i:i+max_chars] for i in range(0, len(palavra), max_chars)]
                                for chunk in chunks[:-1]:
                                    resultado.append(chunk + "-")
                                parte_atual = chunks[-1]

                    # Adicionar qualquer texto restante no buffer de parte
                    if parte_atual:
                        buffer = parte_atual

        # Não esquecer de adicionar qualquer conteúdo restante no buffer
        if buffer:
            # Garantir que termine com alguma pontuação
            if not re.search(r'[.!?;,:]$', buffer.strip()):
                buffer += "."
            resultado.append(buffer.strip())

    # Juntar todas as frases processadas
    return " ".join(resultado)

async def gerar_audiobook(texto, slug, next_titulo_nc=None,
                    is_conteudo_inicial=False, data=None, titulo_atual=None, modulo=None,
                    nucleo=None, voice_intro_resumo=None, voice_conteudo=None):
    """Gera o conteúdo de áudio completo, incluindo introdução, conteúdo e finalização."""
    logging.info("Entrou na função gerar_audiobook (next_titulo_nc): " + str(next_titulo_nc))

    try:
        logging.info("Configurando cliente e vozes para gerar_audiobook.")
        client = texttospeech.TextToSpeechClient()
        audio_config = configurar_audio()

        # Usar as vozes fornecidas ou criar vozes padrão
        if voice_intro_resumo is None:
            voice_intro_resumo = create_voice_params(FEMALE_VOICES[0])
            logging.info(f"Usando voz padrão para introdução/resumo: {FEMALE_VOICES[0]}")

        if voice_conteudo is None:
            voice_conteudo = create_voice_params(MALE_VOICES[0])
            logging.info(f"Usando voz padrão para conteúdo: {MALE_VOICES[0]}")

        # Lista para armazenar todos os segmentos de áudio
        segmentos_audio = []

        # --- INÍCIO DA LÓGICA DA INTRODUÇÃO FALADA (MODIFICADA) ---
        # REMOVIDO: info_modulo_nucleo = extrair_info_modulo_nucleo(slug)

        # Verifica diretamente os dados passados como argumento
        if modulo and nucleo and titulo_atual:
            logging.info(f"Tentando gerar introdução inicial falada para: Módulo='{modulo}', Núcleo='{nucleo}', Título='{titulo_atual}'")

            nucleo_limpo = limpar_nome_nucleo(nucleo)

            # Formata o texto do módulo com cuidado
            texto_modulo = ""
            if isinstance(modulo, str) and modulo.lower() != 'none':
                if "Modulo" in modulo and "Módulo" not in modulo:
                    texto_modulo = modulo.replace("Modulo", "Módulo")
                elif "Módulo" in modulo:
                    texto_modulo = modulo
                else:
                    texto_modulo = f"Módulo {modulo}"
            elif modulo is not None and not isinstance(modulo, str): # Números, etc.
                 texto_modulo = f"Módulo {modulo}"

            # Sintetiza áudio do módulo se válido
            if texto_modulo:
                logging.info(f"Sintetizando áudio para: {texto_modulo}")
                audio_modulo = sintetizar_audio(texto_modulo, client, voice_intro_resumo, audio_config, bloco=texto_modulo)
                if audio_modulo:
                    segmentos_audio.append(audio_modulo)
                    segmentos_audio.append(gerar_pausa_hd_melhorado(650)) # Pausa após módulo
                    logging.info("Áudio do módulo e pausa adicionados.")
                else:
                    logging.warning("Síntese do texto do módulo falhou ou retornou vazio.")
            else:
                logging.warning("Texto do módulo inválido ou vazio, pulando síntese.")

            # Formata o texto do núcleo
            texto_nucleo = ""
            if nucleo_limpo:
                texto_nucleo = f"Núcleo Conceitual {nucleo_limpo}"

            # Sintetiza áudio do núcleo se válido
            if texto_nucleo:
                logging.info(f"Sintetizando áudio para: {texto_nucleo}")
                audio_nucleo = sintetizar_audio(texto_nucleo, client, voice_intro_resumo, audio_config, bloco=texto_nucleo)
                if audio_nucleo:
                    segmentos_audio.append(audio_nucleo)
                    segmentos_audio.append(gerar_pausa_hd_melhorado(650)) # Pausa após núcleo
                    logging.info("Áudio do núcleo e pausa adicionados.")
                else:
                    logging.warning("Síntese do texto do núcleo falhou ou retornou vazio.")
            else:
                logging.warning("Texto do núcleo inválido ou vazio, pulando síntese.")

            # Formata o texto do tema (titulo_atual já foi verificado no if principal)
            texto_tema = f"Tema: {titulo_atual}"

            # Sintetiza áudio do tema
            logging.info(f"Sintetizando áudio para: {texto_tema}")
            audio_tema = sintetizar_audio(texto_tema, client, voice_intro_resumo, audio_config, bloco=texto_tema)
            if audio_tema:
                segmentos_audio.append(audio_tema)
                segmentos_audio.append(gerar_pausa_hd_melhorado(1000)) # Pausa após tema
                logging.info("Áudio do tema e pausa adicionados.")
            else:
                logging.warning("Síntese do texto do tema falhou ou retornou vazio.")

            logging.info("Bloco de introdução inicial falada processado.")
        else:
            # Log mais detalhado se a condição falhar
            logging.warning(f"Pulando introdução inicial falada. Dados recebidos: modulo='{modulo}', nucleo='{nucleo}', titulo_atual='{titulo_atual}'")
        # --- FIM DA LÓGICA DA INTRODUÇÃO FALADA (MODIFICADA) ---


        # Pausa antes da introdução/conteúdo principal
        pausa_antes_introducao = gerar_pausa_hd_melhorado(100) # Pequena pausa
        logging.info("Adicionando pausa antes da introdução/conteúdo principal")
        segmentos_audio.append(pausa_antes_introducao)

        # Processamento do conteúdo principal (introdução + conteúdo + resumo OU conteúdo inicial)
        if is_conteudo_inicial:
            logging.info("Gerando áudio especial para 'conteudo-inicial.json'")

            # Transforma data em dicionário se não for
            dict_data = {}
            if isinstance(data, dict):
                 dict_data = data
            elif isinstance(data, str):
                 try:
                      dict_data = json.loads(data)
                 except Exception as e:
                      logging.error(f"Erro ao converter 'data' (string) para dicionário: {e}")
            elif isinstance(data, list): # Se for lista, tenta colocar em 'conteudo_introducao'
                dict_data = {"conteudo_introducao": data}
            else:
                 logging.warning(f"Tipo de 'data' não esperado para conteudo_inicial: {type(data)}")


            # Extrai dados do JSON (se estiverem disponíveis)
            titulo_tema = dict_data.get("titulo_tema", "Tema Desconhecido")
            descricao = dict_data.get("descricao", "Descrição não disponível")
            conteudo_introducao_raw = dict_data.get("conteudo_introducao", [])

            objetivos_resumidos = ""
            if isinstance(conteudo_introducao_raw, list):
                for item in conteudo_introducao_raw:
                    if isinstance(item, dict) and item.get("__component") == "principais.tipografia":
                        texto_obj = item.get("texto", "")
                        if texto_obj and isinstance(texto_obj, str):
                            objetivos_resumidos += re.sub(r'<[^>]+>', ' ', texto_obj) + " " # Limpa HTML

            # Limpar as strings antes de construir o prompt
            titulo_tema = limpar_texto_para_narrar(titulo_tema)
            descricao = limpar_texto_para_narrar(descricao)
            objetivos_resumidos = limpar_texto_para_narrar(objetivos_resumidos.strip())

            # Constrói o prompt customizado para conteúdo inicial
            prompt_especial = (
            "Transforme o seguinte texto em um roteiro detalhado para um audiobook educativo de INTRODUÇÃO, com tom formal e acadêmico.\n"
            "O roteiro deve seguir a seguinte estrutura, utilizando as informações fornecidas:\n"
            f"1. **Apresentação:** Comece com 'Seja bem-vindo! Este é um áudio introdutório do tema \"{titulo_tema}\", onde serão apresentados os principais tópicos deste curso.'\n"
            f"2. **Visão Geral Direta:** Apresente o conteúdo de forma direta, sem explicações aprofundadas. Use as informações de 'descricao' para criar uma visão geral. Use frases como 'Durante este curso, abordaremos: {descricao}' ou 'Neste módulo, você vai aprender sobre: {descricao}'.\n"
            f"3. **Objetivos (Se disponíveis):** Se houver objetivos, resuma-os brevemente. Resumo dos objetivos: {objetivos_resumidos}\n"
            "4. **Encerramento da Introdução:** Finalize o áudio de introdução com a seguinte frase exata: 'Bem, espero que esta introdução tenha lhe dado uma visão geral sobre todos os pontos que abordaremos durante o curso! Nos vemos na próxima aula!'\n"
            "Não inclua nenhuma descrição de música, transição, título de roteiro ou áudio, apenas o conteúdo a ser falado.\n"
            f"Dados fornecidos:\n"
            f"Título: {titulo_tema}\nDescrição: {descricao}\nObjetivos: {objetivos_resumidos}\n"
            )

            prompt_completo = modificar_prompt_gemini(prompt_especial)
            roteiro_inicial = await melhorar_texto_com_gemini(prompt_completo)
            roteiro_inicial = limpar_texto_para_narrar(roteiro_inicial)
            roteiro_inicial = pos_processar_roteiro(roteiro_inicial)
            roteiro_inicial = adicionar_pausas_estrategicas(roteiro_inicial)

            # Sintetiza o conteúdo do roteiro inicial
            audio_content_inicial = processar_pausas_no_audio_melhorado(roteiro_inicial, client, voice_intro_resumo, audio_config)
            if audio_content_inicial:
                segmentos_audio.append(audio_content_inicial)
            else:
                logging.error("Falha ao sintetizar o áudio do conteúdo inicial.")

        else: # Processamento normal (não é conteúdo inicial)
            logging.info("Gerando áudio para conteúdo normal (não inicial).")

            is_verificando_aprendizado = "Verificando o aprendizado" in titulo_atual if titulo_atual else False

            # Limpar texto base antes de enviar para IA
            texto_limpo = limpar_texto_para_narrar(texto)
            if not texto_limpo:
                 logging.error("Texto base está vazio após limpeza. Não é possível gerar roteiro.")
                 raise ValueError("Texto base vazio.")

            prompt_base = audiobookprompt(texto_limpo)
            prompt_completo = modificar_prompt_gemini(prompt_base)

            roteiro_completo = await melhorar_texto_com_gemini(prompt_completo)
            roteiro_completo = limpar_texto_para_narrar(roteiro_completo)
            roteiro_completo = pos_processar_roteiro(roteiro_completo)
            roteiro_completo = adicionar_pausas_estrategicas(roteiro_completo)

            # Dividir o roteiro nas partes principais (intro, conteúdo, resumo)
            partes = roteiro_completo.split('[pausa]')
            roteiro_introducao = partes[0].strip() if len(partes) > 0 else ""
            roteiro_conteudo = partes[1].strip() if len(partes) > 1 else ""
            roteiro_resumo_base = partes[2].strip() if len(partes) > 2 else ""
            # A parte 3 (próxima aula) é gerada separadamente no final

            # Adicionar Introdução
            if roteiro_introducao:
                audio_content_introducao = processar_pausas_no_audio_melhorado(roteiro_introducao, client, voice_intro_resumo, audio_config)
                if audio_content_introducao:
                    segmentos_audio.append(audio_content_introducao)
                    # Pausa entre introdução e conteúdo
                    segmentos_audio.append(gerar_pausa_hd_melhorado(1000))
                    logging.info("Áudio da introdução e pausa adicionados.")
                else:
                    logging.warning("Falha ao sintetizar a introdução do roteiro.")
            else:
                logging.warning("Roteiro de introdução vazio.")

            # Adicionar Conteúdo Principal
            if roteiro_conteudo:
                audio_content_conteudo = processar_pausas_no_audio_melhorado(roteiro_conteudo, client, voice_conteudo, audio_config)
                if audio_content_conteudo:
                    segmentos_audio.append(audio_content_conteudo)
                    logging.info("Áudio do conteúdo principal adicionado.")
                else:
                    logging.warning("Falha ao sintetizar o conteúdo principal do roteiro.")
            else:
                 logging.warning("Roteiro de conteúdo principal vazio.")


            # Adicionar Resumo (e perguntas) - exceto para "Verificando o aprendizado"
            if not is_verificando_aprendizado:
                roteiro_resumo = roteiro_resumo_base
                perguntas_reflexivas = await gerar_perguntas_reflexivas(texto_limpo, titulo_atual) # Usa texto limpo
                if perguntas_reflexivas:
                    roteiro_resumo += " " + perguntas_reflexivas # Adiciona ao resumo

                if roteiro_resumo.strip(): # Verifica se há algo para falar no resumo
                    # Pausa forte antes do resumo
                    segmentos_audio.append(gerar_pausa_hd_melhorado(1000))
                    logging.info("Adicionando pausa antes do resumo.")

                    # Transição para o resumo
                    transicao_resumo = "Agora, vamos revisar os principais pontos desta aula."
                    transicao_resumo = limpar_texto_para_narrar(transicao_resumo)
                    audio_content_transicao = sintetizar_audio(transicao_resumo, client, voice_intro_resumo, audio_config)
                    if audio_content_transicao:
                        segmentos_audio.append(audio_content_transicao)

                    # Sintetiza o resumo (com ou sem perguntas)
                    audio_content_resumo = processar_pausas_no_audio_melhorado(roteiro_resumo, client, voice_intro_resumo, audio_config)
                    if audio_content_resumo:
                        segmentos_audio.append(audio_content_resumo)
                        logging.info("Áudio do resumo (com/sem perguntas) adicionado.")
                    else:
                        logging.warning("Falha ao sintetizar o resumo.")
                else:
                    logging.warning("Roteiro de resumo vazio, pulando.")
            else:
                 logging.info("Pulando resumo para 'Verificando o aprendizado'.")


        # Finalização (Próxima aula / Encerramento) - Sempre, exceto para conteúdo inicial
        if not is_conteudo_inicial:
            texto_finalizacao = ""
            if is_verificando_aprendizado:
                texto_finalizacao = "Chegamos ao final deste módulo. Esperamos que o conteúdo tenha sido proveitoso."
                logging.info("Usando mensagem de encerramento de módulo para 'Verificando o aprendizado'")
            elif next_titulo_nc and next_titulo_nc.strip():
                next_titulo_nc_limpo = limpar_texto_para_narrar(next_titulo_nc)
                # Verifica se o próximo é "Verificando..." para mensagem especial
                if "Verificando o aprendizado" in next_titulo_nc_limpo:
                     texto_finalizacao = "Na próxima aula, iremos revisar todo o conteúdo passado durante este módulo."
                else:
                     texto_finalizacao = f"Na próxima aula, abordaremos o tema: {next_titulo_nc_limpo}."
            else: # Último item da sequência ou next_titulo_nc vazio/nulo
                texto_finalizacao = "Chegamos ao final deste módulo. Esperamos que o conteúdo tenha sido proveitoso."
                logging.info("Usando mensagem de encerramento padrão (sem próximo título ou último item).")

            texto_finalizacao = limpar_texto_para_narrar(texto_finalizacao)

            if texto_finalizacao:
                # Pausa antes da finalização
                segmentos_audio.append(gerar_pausa_hd_melhorado(1000))
                logging.info("Adicionando pausa antes da finalização (próxima aula/encerramento).")

                # Sintetiza a finalização
                audio_finalizacao = sintetizar_audio(texto_finalizacao, client, voice_conteudo, audio_config) # Voz masculina
                if audio_finalizacao:
                    segmentos_audio.append(audio_finalizacao)
                    logging.info("Áudio da finalização adicionado.")
                else:
                    logging.warning("Falha ao sintetizar a finalização.")
            else:
                logging.warning("Texto de finalização vazio, pulando.")

        # Concatenar todos os segmentos de forma segura
        logging.info(f"Concatenando {len(segmentos_audio)} segmentos de áudio de forma segura.")
        audio_content = concatenar_audios_seguro(segmentos_audio)

        if not audio_content:
             logging.error("Falha na concatenação final ou nenhum segmento de áudio foi gerado.")
             return None # Retorna None se o áudio final estiver vazio

        logging.info("Conteúdo de áudio final gerado com sucesso.")
        return audio_content

    except Exception as e:
        logging.error(f"Erro DENTRO de gerar_audiobook: {e}", exc_info=True)
        raise # Re-levanta a exceção para ser pega pela função 'audiobook'


def pos_processar_roteiro(roteiro):
    """
    Versão melhorada que remove marcações de roteiro e pontuação falada.
    """
    # Limpar o texto antes de processá-lo
    roteiro = limpar_texto_para_narrar(roteiro)

    # Executar a limpeza original
    roteiro = re.sub(r'Roteiro para Audiobook Educativo:.*', '', roteiro, flags=re.IGNORECASE)
    roteiro = re.sub(r'^Introdução\s*:', '', roteiro, flags=re.IGNORECASE | re.MULTILINE)
    roteiro = re.sub(r'^Desenvolvimento\s*:', '', roteiro, flags=re.IGNORECASE | re.MULTILINE)
    roteiro = re.sub(r'^Conclusão\s*:', '', roteiro, flags=re.IGNORECASE | re.MULTILINE)
    roteiro = re.sub(r'^Resumo\s*:', '', roteiro, flags=re.IGNORECASE | re.MULTILINE)
    roteiro = re.sub(r'\*+[\s\w]+\*+', '', roteiro) # Remove **negrito** etc.

    # Remove espaços extras e linhas vazias excessivas
    def replace_outside_tags(text):
        parts = re.split(r'(<[^>]*>)', text) # Mantém tags HTML se houver
        for i in range(0, len(parts), 2):
            # Normaliza espaços dentro das partes de texto
            parts[i] = re.sub(r'[ \t]+', ' ', parts[i])
            # Remove linhas em branco excessivas
            parts[i] = re.sub(r'\n\s*\n', '\n', parts[i])
            parts[i] = parts[i].strip()
        # Rejunta as partes, removendo as vazias
        return ' '.join(p for p in parts if p)

    roteiro = replace_outside_tags(roteiro)

    # Limpar o texto novamente para garantir
    roteiro = limpar_texto_para_narrar(roteiro)

    return roteiro.strip()


def configurar_audio():
    return texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
        # speaking_rate=1.0 # Removido para compatibilidade com vozes HD
    )


def sintetizar_audio(roteiro, client, voice, audio_config, bloco=None):
    """
    Sintetiza áudio a partir de texto, sem usar SSML.
    Modificada para limpar pontuação verbal, timestamps e lidar com frases longas.

    Args:
        roteiro: O texto a ser sintetizado
        client: Cliente do Text-to-Speech
        voice: Parâmetros de voz
        audio_config: Configuração de áudio
        bloco: Texto específico a ser usado no lugar do roteiro (opcional)

    Returns:
        Conteúdo do áudio em bytes ou b'' em caso de falha.
    """
    try:
        texto_a_processar = bloco if bloco else roteiro
        texto_a_processar = texto_a_processar.strip() # Garante que não tem espaços no início/fim

        if not texto_a_processar:
            logging.warning("Texto para sintetizar está vazio.")
            return b""

        # IMPORTANTE: Limpar o texto antes de sintetizá-lo
        texto_a_processar = limpar_texto_para_narrar(texto_a_processar)

        # NOVO: Quebrar frases muito longas
        texto_a_processar = quebrar_frases_longas(texto_a_processar, max_chars=250) # Limite seguro

        if not texto_a_processar:
            logging.warning("Texto para sintetizar ficou vazio após limpeza/quebra.")
            return b""

        # Log adicional para debug
        log_message = f"Sintetizando bloco ({voice.name}): '{texto_a_processar[:100]}...'"
        logging.info(log_message)

        # Configuração de áudio sem modificar a taxa de fala (para evitar o erro com vozes HD)
        custom_audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_config.audio_encoding
        )

        # Google limita o tamanho do input da API a 5000 bytes (não caracteres)
        # Para segurança, limitamos em caracteres e processamos em blocos menores.
        max_chars_api = 4500 # Limite conservador de caracteres por chamada API

        segmentos = []

        # Divide o texto em partes menores se necessário
        texto_restante = texto_a_processar
        while texto_restante:
            # Pega o próximo bloco respeitando o limite
            bloco_atual = texto_restante[:max_chars_api]
            texto_restante = texto_restante[max_chars_api:]

            # Tenta encontrar um ponto final para quebrar de forma mais natural
            if texto_restante: # Se ainda há texto depois
                # Procura o último ponto final, interrogação ou exclamação no bloco
                last_sentence_end = max(bloco_atual.rfind('.'), bloco_atual.rfind('?'), bloco_atual.rfind('!'))
                if last_sentence_end > 0: # Encontrou um ponto final razoável
                    # Ajusta o bloco atual e o texto restante
                    texto_restante = bloco_atual[last_sentence_end+1:] + texto_restante
                    bloco_atual = bloco_atual[:last_sentence_end+1]

            bloco_atual = bloco_atual.strip()
            if not bloco_atual:
                continue

            try:
                # Log do bloco sendo enviado
                logging.debug(f"Enviando para API TTS ({voice.name}): {bloco_atual[:100]}...")

                input_text = texttospeech.SynthesisInput(text=bloco_atual)
                response = client.synthesize_speech(
                    input=input_text,
                    voice=voice,
                    audio_config=custom_audio_config
                )
                if response.audio_content:
                    segmentos.append(response.audio_content)
                else:
                    logging.warning(f"API TTS retornou conteúdo vazio para o bloco: {bloco_atual[:100]}...")

            except Exception as e:
                logging.error(f"Erro ao sintetizar bloco com API TTS ({voice.name}): {e}")
                logging.error(f"Texto problemático: {bloco_atual[:100]}...")
                # Considerar tentar novamente ou dividir mais? Por ora, apenas logamos.


        # Concatenar os segmentos de forma segura
        if not segmentos:
             logging.error(f"Nenhum segmento de áudio foi sintetizado com sucesso para o texto original: {texto_a_processar[:100]}...")
             return b""
        elif len(segmentos) == 1:
             return segmentos[0]
        else:
            logging.info(f"Concatenando {len(segmentos)} segmentos para o bloco original.")
            return concatenar_audios_seguro(segmentos)


    except Exception as e:
        logging.error(f"Erro GERAL ao sintetizar áudio ({voice.name}): {e}", exc_info=True)
        return b"" # Retornar bytes vazios em caso de erro geral