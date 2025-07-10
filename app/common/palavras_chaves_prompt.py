import json


def prompt_palavras_chaves_imagem(texto, quantidade_palavras_chaves, quantidade_imagens):

    schema_texto = json.dumps(response_schema_roteiro, indent=2)

    prompt = f"""
        Você é um especialista em análise de texto e extração de palavras-chave. Sua tarefa é identificar as palavras e frases mais importantes e relevantes no texto fornecido abaixo. Essas palavras-chave devem representar os principais tópicos, conceitos e ideias centrais do texto.

        **Instruções:**
        Palavras-chave:
            1. **Extraia palavras-chave que apareçam EXATAMENTE no texto original**. Não modifique ou parafraseie as palavras.
            2. **Leia atentamente o texto:** Compreenda o tema principal, os argumentos e as informações chave apresentadas.
            3. **Identifique os termos mais relevantes:** Procure por palavras e frases que se repetem, que são centrais para o entendimento do texto.
            4. **Priorize substantivos e frases nominais:** Termos como "computador", "processamento de dados", "inteligência artificial" são mais úteis que verbos ou adjetivos isolados.
            5. **Extraia pelo menos {quantidade_palavras_chaves} palavras-chave/frases:** Selecione um número grande de palavras-chave que capturem a essência do texto.
            6. **Apresente as palavras-chave/frases em uma lista:** Liste cada palavra-chave ou frase separadamente, de forma clara e organizada.
        
        Imagens:
            7. **Máximo de {quantidade_imagens} imagens.**
            8. **Forneça uma descrição da imagem em inglês (15-20 palavras) que seja CONCRETA e ESPECÍFICA.**
            9. **Evite termos abstratos ou conceituais. Use descrições visuais concretas que possam ser facilmente encontradas em bancos de imagens.**
            10. **Para o momentoChave, copie EXATAMENTE frases do texto original (10-15 palavras).**
            11. **Escolha momentoChave que sejam fáceis de identificar na transcrição.**
            12. **descricaoBuscaEnvato e momentoChave não podem estar no array de palavras_chaves[].**
            13. **Formato de saída: JSON (apenas a string JSON pura, sem formatação ou explicações adicionais). Siga o schema fornecido.**

        **Exemplos de boas descrições de imagem:**
        - "Person typing on laptop with code visible on screen in modern office setting"
        - "Close-up of computer motherboard with colorful components and circuits"
        - "Student raising hand in classroom with computers and teacher at whiteboard"
        - "Binary code projection over human face profile in dark room with blue light"

        **Exemplos de descrições ruins (muito abstratas):**
        - "Technology concept" (muito vago)
        - "Human computer interaction" (muito abstrato)
        - "Digital transformation journey" (muito conceitual)
        - "Modern computing paradigm" (não descreve uma imagem concreta)

        **Texto a ser analisado:**

        {texto}

        **Saída esperada:**

        {schema_texto}
    """
    
    return prompt

response_schema_roteiro = {
                        "type": "object",
                        "properties": {
                            "palavras_chaves": {
                            "type": "array",
                            "items": { 
                                "type": "string", 
                                "description": "Palavras chaves que contem no texto." 
                            }
                            },
                            "imagens": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                "momentoChave": {
                                    "type": "string", 
                                    "description": "texto que a imagem deve aparecer, igual ao texto original até 15 palavras"
                                },
                                "descricaoBuscaEnvato": {
                                    "type": "string", 
                                    "description": "Descricao da imagem de 15 a 20 palavras em ingles" 
                                }
                                }
                            }
                            }
                        }
                    }