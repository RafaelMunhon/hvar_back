def audiobookprompt(texto):
    prompt = (
        "Transforme o seguinte texto em um roteiro detalhado para um audiobook educativo, com tom formal e acadêmico, adequado para alunos em níveis avançados de um curso. "
        "O roteiro deve apresentar informações precisas, detalhadas e aprofundadas, evitando explicações superficiais. "
        "Concentre-se na apresentação clara e objetiva de conceitos, informações relevantes e essenciais para a compreensão do tema, com rigor técnico e científico. "
        
        
        "IMPORTANTE: Inclua apenas um elemento ilustrativo - que pode ser um microcaso (história curta de 3-5 frases) OU um exemplo prático que ilustre o conceito principal. "
        "Este exemplo deve ser relevante para o contexto organizacional e profissional, como um dilema empresarial, situação de trabalho ou caso real. "
        "Introduza o exemplo com frases como 'Para ilustrar este conceito, considere o seguinte exemplo...' ou 'Um caso que demonstra esta situação seria...'. "
        
        "Inclua informações cruciais e relevantes como: critérios diagnósticos, diagnósticos diferenciais, tratamentos, etiologia, prevalência, aspectos epidemiológicos e considerações importantes para o entendimento do ouvinte. "
        "Use uma linguagem que engaje o ouvinte de forma profissional e informada, utilizando terminologia técnica e acadêmica apropriada, mantendo o foco no tema central e evitando divagações ou redundâncias desnecessárias. "
        "As informações devem ser baseadas em fontes confiáveis e reconhecidas na área, como manuais de referência (por exemplo, DSM ou CID), artigos científicos e livros de referência. "
        "O roteiro deve apresentar uma estrutura lógica, com introdução, desenvolvimento (com aprofundamento) e conclusão, mas não inclua os títulos de seção como 'Introdução', 'Desenvolvimento' ou 'Conclusão'. "
        """
        Utilize a tag [pausa] para indicar pausas lógicas entre as seções, seguindo o seguinte padrão:

          Introdução: Comece sempre com a frase 'Nessa aula, vamos abordar' seguida de uma breve apresentação dos principais tópicos que serão discutidos, utilizando no máximo 2 frases para situar o ouvinte.
          [pausa]
          Desenvolvimento: Um bloco longo explicando o conteúdo central de forma detalhada, incluindo critérios diagnósticos, diagnósticos diferenciais e outras informações técnicas relevantes. Coloque o exemplo ou microcaso em um ponto estratégico desta seção para ilustrar o conceito mais importante.
          [pausa]
          Resumo: Um parágrafo conciso com as ideias centrais do tema abordado, sumarizando os principais pilares da aula. NÃO adicione perguntas reflexivas no resumo - estas serão adicionadas posteriormente pelo sistema.
          [pausa]
          Previa da próxima aula: NÃO INCLUA A PREVIA DA PRÓXIMA AULA. A previa será adicionada posteriormente.
        """
        "Não inclua nenhuma descrição de música, transição, título de roteiro ou áudio, apenas o conteúdo a ser falado.\n\n"
        f"Texto a ser transformado:\n{texto}"
    )
    return prompt