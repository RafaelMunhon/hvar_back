def generate_new_script(context, new_context_prompt ):

    prompt = (f"""
    Você é um especialista em transformar dados JSON. O usuário irá fornecer um texto extraído de um JSON.
    Seu objetivo é analisar esse texto e gerar um novo roteiro, adaptado para o contexto de: {new_context_prompt}.
    Mantenha a mesma lógica e estilo do texto original. Transforme o conteúdo para o novo tema fornecido.

    Texto Original:

    {context}

    Responda SOMENTE com o novo roteiro, adaptado para o tema "{new_context_prompt}".
    """)

    return prompt

def generate_new_script_json(json_data, new_script ):

    prompt_json = (f"""
        Você é um especialista em transformar dados JSON. O usuário irá fornecer um roteiro textual e um JSON.
        Seu objetivo é transformar esse roteiro textual em um novo arquivo JSON, mantendo a estrutura do JSON original.

        JSON Original: {json_data}
        Novo roteiro: {new_script}

        Responda SOMENTE com o novo JSON.
    """)

    return prompt_json