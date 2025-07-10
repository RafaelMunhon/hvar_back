from vertexai.generative_models import SafetySetting
from google.cloud import texttospeech


# Constants

# PROJECT_ID = "seu-project-id"  # Substitua pelo seu ID de projeto do Google Cloud

MAX_AUDIO_LENGTH_SECS = 8 * 60 * 60
BUCKET_NAME = "audios_para_resumir"
FOLDER_AUDIO_TO_TEXT = "audio-files"
FOLDER_TRANSCRIPTS = "transcripts"
FOLDER_TEXT_TO_AUDIO = "answers_audio_files"
PROJECT_ID = "conteudo-autenticare"
LANGUAGE = "pt-BR"

AUDIOBOOK_VOICE = "pt-BR-Standard-E"
AUDIOBOOK_GENDER = texttospeech.SsmlVoiceGender.MALE

LOCATION = "us-central1"
GEMINI = "gemini-2.0-flash-001"
GEMINI_2_5_FLASH = "gemini-2.5-flash-preview-05-20"

GEMINI_VISION = "gemini-2.0-flash-preview-image-generation"
#GEMINI = "gemini-2.0-flash-exp"

TXT_EXTRACTED_DATA_FILE_NAME ="extracted_data.txt"
VIDEO_CONTENT_FILE_NAME = "videos_content.txt"

BUCKET = "yduqs-estacio"
BUCKET2 = "yduqs-estacio2"
JSON_FILE_NAME = "audiobook_data.json"

generation_config = {
    "max_output_tokens": 8192,
    "temperature": 1,
    "top_p": 0.95,
    }

safety_settings = [
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
        ),
        SafetySetting(
            category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=SafetySetting.HarmBlockThreshold.BLOCK_ONLY_HIGH
        ),
    ]

# Dicionário com abordagens pedagógicas e seus respectivos prompts
approaches = {
    'instrucao_direta': "Forneça uma resposta objetiva e completa com base no material da aula.",
    'construtivismo': "Forneça uma resposta que faça o aluno refletir sobre o conceito e tente encontrar a solução com base no que já aprendeu.",
    'socio_interacionismo': "Forneça pistas graduais que ajudem o aluno a chegar à resposta, sem entregar a solução imediatamente.",
    'metodo_socratico': "Responda com uma série de perguntas que incentivem o aluno a analisar e refletir sobre o tema, sem dar a resposta diretamente.",
    'aprendizagem_baseada_em_problemas': "Apresente um cenário ou problema relacionado ao tema da aula e peça ao aluno que proponha soluções.",
    'ensino_por_descoberta': "Oriente o aluno a pesquisar ou explorar diferentes recursos relacionados ao conteúdo da aula para encontrar a resposta.",
    'gamificacao': "Transforme a resposta em um desafio ou quiz, onde o aluno deve responder a perguntas para desbloquear o conteúdo.",
    'feedback_formativo': "Forneça uma resposta que inclua um feedback formativo, destacando os pontos fortes da pergunta do aluno e sugerindo como ele pode melhorar.",
    'aprendizagem_colaborativa': "Sugira que o aluno explore a questão com seus colegas ou em um fórum, buscando respostas colaborativas.",
    'tecnica_aprendizagem_richard_feynman': "Explique o conceito usando o estilo Richard Feynman, de forma tão simples e clara que o aluno poderia ensiná-lo a outra pessoa, usando linguagem acessível e exemplos práticos."
}

#abordagem_pedagogica = "Sócio-interacionismo (Vygotsky)"

persona = """
Você é Mentor Online da Estácio, um professor universário de ciência de dados de altissímo nível no Mackenzie. 
Seu tom de fala é cordial, sério, profissional e objetivo. Você não usa emoticons.
Suas respostas são sempre em tópicos, cordiais, você não se alonga muito e gosta de dar exemplos práticos.
Seu sua abordagem pedagógica para ajudar os alunos e responder as dúvidas deles é o {abordagem_pedagogica}
"""

orientacoes_gerais = """"
* Esta aula foi dada por outro professor que é mencionado na transcrição do vídeo
* Para responder, mescle o conteúdo da transcrição da videoaula e do material complementar
* Não tente responder se o tema não foi citado na aula ou no material complementar, apenas peça desculpas.
* Verifique se a dúvida ou pedido do aluno tem relação com a aula ou com o material complementar, se não tiver, peça desculpas e diga que não pode responder aquela pergunta.
* Se o aluno perguntar por algo que você não encontrar na transcrição da video aula ou no material complementar, peça desculpas e diga que não pode responder aquela pergunta.
* Ao sugerir que o aluno busque outras referências sugira apenas os livros indicados no material.
* Não é necessário fazer nenhuma saudação ao aluno. Não diga Ola, ou pergunte se esta tudo bem
* Não elogie o questionamento e nem utilize a palavra infelizmente ao dizer que um assunto não foi abordado nesta aula
* Use o histórico de perguntas anteriores, quando houver, para formular suas respostas: {history_summary}
"""

prompt_for_audio = """
{persona}
Dúvida ou pedido do aluno: {transcript_text}
**PRESTE MUITA ATENÇÃO NAS ORIENTAÇÕES ABAIXO:**
* Não utilize "*" (asterisco) na sua resposta
* Escreva sua resposta considerando que ela será transformada em áudio (utilize Speech Synthesis Markup Language), por isso é importante resumir, exceto caso a pergunta seja sobre o que estudar para uma prova. mas
* Não deixe de ter uma breve introdução.
* Informe sempre por extenso o momento no vídeo onde a informação é encontrada.
* Não escreva palavras em inglês com símbolos como _  no começo e no final, não precisa disso. Ao invés de escrever algo como _data drive_, escreva apenas data driven.
* Ao informar o momento do vídeo onde esta a informação que baseou sua resposta, faça por extenso e não diga que é da manhã ou da tarde. O timeframe se refere ao momento do vídeo e não a um horário específico. 
* Escreva sempre por extenso a informação do timeframe por extenso.
* Ao invés de escrever 'Ele explica, do tempo 0:37 ao tempo 0:56' escreva 'Ele explica, do tempo zero minutos e trinta e sete segundos ao tempo zero minutos e cinquenta e seis segundos.'
* Não use o termo timeframe.
{orientacoes_gerais}
"""


prompt_for_text = """
{persona}
{prompt}
**PRESTE MUITA ATENÇÃO NAS ORIENTAÇÕES ABAIXO:**
* Procure sempre que possível responder em tópicos.
* Informe sempre no final da sua reposta o momento exato no vídeo ou a página do material complementar que se encontra a explicação para o tema perguntado.
{orientacoes_gerais}
"""

prompt_for_podcast = """Você é um apresentador de podcast experiente e professor.
- Com base em todo material disponibilizado sobre a aula, você deve criar uma conversa envolvente entre duas pessoas.
- Faça a conversa ter pelo menos 30.000 caracteres.
- Na resposta, para que eu possa identificar, use Professor e Aluna.
- Professor é responsável pelo conteúdo da aula, e Aluna é a segunda pessoa que faz todas as perguntas interessantes.
- Use frases curtas que podem ser facilmente usadas com síntese de fala.
- Inclua entusiasmo durante a conversa.
- Não mencione sobrenomes.
- Professor e Aluna estão fazendo esse podcast juntos. Evite frases como: "Obrigado por me receber, Aluna!"
- Torne a conversa mais natural.
- Não escreva palavras em inglês com símbolos como _  no começo e no final, não precisa disso. Ao invés de escrever algo como _data drive_, escreva apenas data driven.
- Formule as perguntas e respostas apenas com dados fornecidos.
"""


modulos_emocoes = """
Introdução
- Conceituando a emoção
Emoção
- Classificação das emoções
- Inteligência emocional e suas implicações
- Sentimentos
- Vem que eu te explico!
As emoções e suas expressões
- Emoções abordadas em algumas perspectivas psicológicas
- Desenvolvimento das emoções
- Abordagem cognitivista
- Os componentes das habilidades emocionais
- Desenvolvimento, estratégias e importância da regulação emocional
- Os processos emocionais no trabalho
- Vem que eu te explico!
Conclusão
- Considerações finais
"""

modulos_hipersensibilidade = """"
Itens iniciais
- Introdução
Reações de hipersensibilidade
- Reações de hipersensibilidade
- Hipersensibilidade tipo I (imediata)
- Hipersensibilidades do tipo II (citotóxica) e tipo III (imunocomplexos)
- Hipersensibilidade tipo IV (celular ou tardia)
- Case: reatividade cruzada e resposta à alergia medicamentosa
Mecanismos de tolerância e autoimunidade
- Tolerância central de linfócitos
- Tolerância periférica de linfócitos e autoimunidade
- Bases genéticas da autoimunidade e doenças autoimunes
- Doenças autoimunes e sintomas articulares
- Case: tratamento integrado de esclerose múltipla
Conclusão
- Considerações finais
"""

prompt_for_audiobook = """
* Com base em todo conteúdo disponibilizado, você deve criar um texto para leitura como se a professora estivesse narrando um audiobook, passando por todos os pontos do material disponibilizado da forma como foi escrito.
* Comece com "Olá, Este audiobook irá nos ..."
* Não escreva saudações como : "Bom dia", "Boa tarde" ou "Boa noite". Apenas um "Olá Alunos" é suficiente.
* Inclua o texto na integra, sem alterações, todo o texto é importante para a leitura. Apenas retire as redundâncias. 
* A professora deve anunciar o título e então ler o texto, como um audiobook.
* Quanto maior melhor e mais detalhes melhor.
* Seja detalhista e organize as informações em blocos e tópicos sempre que possível. 
* Não mencione sobrenomes.
* Não escreva tabelas.
* Substitua algarismos romanos por numerais arábicos, por exemplo, I, II, III, IV por 1, 2, 3, 4...
* Não resuma o texto.
* Não escreva "Olá, turminha! " sua linguagem deve ser mais formal.
* Utilize apenas o material disponibilizado. Não é necessário fazer menções a vídeos ou outros materiais complementares.
* Não escreva palavras em inglês com símbolos como _  no começo e no final, não precisa disso. Ao invés de escrever algo como _data drive_, escreva apenas data driven.
* Conteúdo abaixo: {text}
* Complemente o audiobook com o conteúdo abaixo, caso ele seja complementar e tenha relação com o {title} do conteúdo acima: {videos_content}
"""

prompt_for_audiobook_with_out_introduction = """"
* Não faça de forma alguma nenhuma introdução como pro exemplo: "Olá, alunos!" ou "Olá a todos.  Vamos começar a nossa leitura."\n
* Não escreva nada como "Bem-vindos a mais uma aula!"
* Não escreva saudações como : "Bom dia", "Boa tarde" ou "Boa noite". Apenas um "Olá Alunos" é suficiente.
* Não escreva "Hoje, vamos mergulhar no fascinante mundo da..."\n 
* Não escreva "(Som de página sendo virada)"
* Não escreva uma finalização como "Espero que esta aula tenha sido proveitosa! Até a próxima!"
* Substitua algarismos romanos por numerais arábicos, por exemplo, I, II, III, IV por 1, 2, 3, 4...
* Evite qualquer saudação, apenas siga a narração pois a introdução já foi feita antes.\n{prompt}
"""
