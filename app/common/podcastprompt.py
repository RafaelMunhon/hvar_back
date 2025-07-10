def cria_roteiro_prompt(texto):
    prompt = (
        "Crie um roteiro para um podcast educativo em formato de diálogo entre um professor e um aluno sobre o tema fornecido. "
        "O professor deve explicar o tema de forma clara e didática, utilizando exemplos práticos quando possível, e o aluno deve fazer perguntas pertinentes ao que o professor está explicando."
        "As perguntas do aluno devem ser específicas e relacionadas aos exemplos do professor. Formate o roteiro da seguinte forma: \n\n"
        "essa parte é importante para o modelo entender o que é pergunta e o que é resposta\n\n"
        "Professor: [FALA DO PROFESSOR]\n"
        "Aluno: [PERGUNTA DO ALUNA]\n\n"
        f"Tema: {texto}"
    )
    return prompt