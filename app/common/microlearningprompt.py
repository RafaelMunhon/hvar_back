def microlearningprompt(texto, resumido=False):
    if resumido:
        return _microlearningprompt_resumido(texto)
    else:
        return _microlearningprompt_nao_resumido(texto)


def _microlearningprompt_nao_resumido(texto):
    prompt = (
        "Transforme o seguinte texto em um roteiro para um áudio de microlearning, com foco em um único conceito ou habilidade. "
        "O áudio deve ser conciso e direto ao ponto, como se fosse um especialista explicando um tema específico de forma rápida e eficiente. "
        "Use um tom de voz de um especialista no assunto, claro, acessível e confiante. "
        "Apresente o conteúdo de forma lógica e bem estruturada, seja uma explicação direta, uma dica rápida, um resumo de artigo ou um mini-case. "
        "Use a tag [pausa] para indicar pausas lógicas entre as partes do conteúdo, para que a leitura flua naturalmente. "
        "O roteiro deve ser contínuo, sem marcadores de seção ou títulos. "
         "Não inclua nenhuma descrição de música, transição ou áudio, apenas o conteúdo a ser falado.\n\n"
        f"Texto a ser transformado:\n{texto}"
    )
    return prompt


def _microlearningprompt_resumido(texto):
    prompt = (
        "Transforme o seguinte texto em um roteiro conciso para um áudio de microlearning, com foco na essência de um único conceito ou habilidade. "
        "O áudio deve ser o mais direto e objetivo possível, como um especialista dando um resumo rápido e impactante do tema. "
        "Use uma linguagem clara e simples, sem repetições ou informações desnecessárias. "
        "Use a tag [pausa] para indicar pausas lógicas entre os principais pontos do conteúdo, para que a leitura flua naturalmente. "
        "O roteiro deve apresentar uma narrativa contínua, sem marcadores de seção ou títulos. "
        "Não inclua nenhuma descrição de música, transição ou áudio, apenas o conteúdo a ser falado.\n\n"
         f"Texto a ser transformado:\n{texto}"
    )
    return prompt