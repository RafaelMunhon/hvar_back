def audioqaprompt(texto, resumido=False):
    if resumido:
        return _audioqaprompt_resumido(texto)
    else:
        return _audioqaprompt_nao_resumido(texto)


def _audioqaprompt_nao_resumido(texto):
    prompt = (
        "Transforme o seguinte texto em um roteiro para um áudio de perguntas e respostas (Q&A), no formato de um FAQ em áudio. "
        "O áudio deve começar com uma breve introdução ao tema central do texto, como se fosse um especialista (professor) apresentando o assunto. "
        "Após a introdução, cada pergunta deve ser lida claramente e seguida pela resposta do professor. "
        "Use um tom de voz de um professor experiente, claro e acessível, com uma dicção calma e articulada. "
        "Mantenha o foco no conteúdo das perguntas e respostas, evitando informações adicionais desnecessárias. "
         "Use a tag [pausa] após a introdução, após a leitura da pergunta e antes de iniciar a resposta para uma transição natural. "
        "O roteiro deve ser fluido e contínuo, sem marcadores de seção ou títulos. "
        "Não inclua nenhuma descrição de música, transição ou áudio, apenas o conteúdo a ser falado.\n\n"
        f"Texto a ser transformado:\n{texto}"
    )
    return prompt


def _audioqaprompt_resumido(texto):
    prompt = (
         "Transforme o seguinte texto em um roteiro conciso para um áudio de perguntas e respostas (Q&A), no formato de um FAQ em áudio. "
        "O áudio deve começar com uma breve introdução ao tema central do texto, como se fosse um professor apresentando o assunto de forma resumida. "
         "Após a introdução, a leitura das perguntas e respostas devem ser objetivas, como um professor respondendo rapidamente às principais dúvidas. "
        "Use uma linguagem clara e direta, evitando repetições ou floreios. "
        "Use a tag [pausa] após a introdução e após a leitura da pergunta e antes de iniciar a resposta. "
        "O roteiro deve apresentar uma narrativa contínua, sem marcadores de seção ou títulos. "
        "Não inclua nenhuma descrição de música, transição ou áudio, apenas o conteúdo a ser falado.\n\n"
        f"Texto a ser transformado:\n{texto}"
    )
    return prompt