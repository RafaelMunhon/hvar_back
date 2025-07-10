import json


@staticmethod
def cria_roteiro_prompt_template_1(texto):

    schema_texto = json.dumps(response_schema_roteiro, indent=2)

    prompt = f"""
        Você é um professor ou professora, não vamos especificar seu genero e tambem vai criar vídeoaulas em EAD para uma conceituada faculdade.
        Nessa aula, precisamos que tenha até 7 slides, com 6 cenas, e o vídeo precisa ter de 8 a 10 minutos. Na ultima cena, quero que fale sobre a aula. Apenas na ultima frase, pode se despedir.
        Esse vídeo será processado pelo site HeyGen, então vamos precisar de suas variáveis.
        Quero também que extraia palavras-chave para mostrar na tela. Com as palavras-chave, quero uma breve descrição abaixo, como tópico e subtópico.
        Adicione variáveis de imagem onde for necessário.
        Vou precisar que crie o nome das variáveis que vamos mostrar as palavras-chave (ex: titulo, subtitulo, tópico, descrição do que está sendo falado). Use urlImg para a url da imagem e decricaoImagem para a descrição da imagem.
        Quero uma aula mais aprofundada sobre o assunto, que recebemos pelo JSON.
        Com base no texto fornecido, crie um roteiro formatado em JSON, seguindo a estrutura abaixo.
        Muito Importante: O tempo e o script devem ser coerentes, para que o vídeo não fique muito longo nem muito curto. Aprofunde mais no assunto e traga mais informações no script.
        Me dê uma descrição da imagem para que eu possa criar a imagem correta.
        Pegue a URL que contenha as imagens e vídeos e coloque no array de imagens e vídeos, caso tiver.
        Faça com que a imagem recebida no JSON fique nas variáveis de imagem em urlImg.
        Só no slide 4 colocar imagens, mas pode continuar com os outros itens tambem .
        No Slide 3, quando for na metade do script falar sobre os 4 primeiros tópicos e colocar no schema correto, e na aula falar sobre eles e citar, não precisa topico 1, topico 2, topico 3 e topico 4 apenas falar as palavras e dissertar sobre eles.
        Fale mais sobre os topicos 1, 2, 3 e 4.
        Coloque as imagens e os vídeos no array de imagens e vídeos.
        Se caso não tiver o mesmo numero de imagens para os slides 2,3 e 4, repita a imagem.
        Todos as cenas precisam ter no array de elementos_visuais texto (contendo o Titulo e Subtitulo.) e se caso tiver imagem (contendo a url da imagem e a descrição da imagem).

        no Slide 7, apenas termine a apresentação e se despeça. Coloque um titulo de despedida com até 10 palavras. (quando não tiver mais nada, coloque no texto alguma string para não quebrar o json subtitulo_7 e breveDesc_7 não pode ser null).

        Crie um JSON que siga esta estrutura, preenchendo os campos com informações do texto fornecido.
        
        Vou passando as instruçõe de como eu quero o texto da seguinte forma, Instruções para roteiro: texto descritivo do que deve ser feito.

        {texto}

        Isso é Muito Importante:
        Siga exatamente o schema fornecido e retorne apenas a string em formato JSON, sem nenhuma outra instrução, texto ou formatação.
        O schema JSON a seguir descreve a estrutura da resposta que você precisa gerar, não o valor de retorno:
        Retorne o JSON como texto puro, sem nenhuma formatação adicional. Forneça o JSON abaixo como uma string de texto simples, sem ```json ou qualquer outro código de formatação. Envie o JSON sem qualquer marcação de bloco de código. 
        Quero apenas o texto do JSON.

        {schema_texto}
        """
    
    return prompt

def cria_roteiro_prompt_template_3(texto, numCenas):
    """
    Cria o prompt para gerar um roteiro usando o modelo de template 3.

    Recebe:
    - texto: Texto para gerar o roteiro
    - numCenas: Número de cenas desejado

    Retorna:
    - Prompt para gerar o roteiro
    """ 
    schema_texto = json.dumps(response_schema_roteiro, indent=2)

    prompt = f"""
            
            *** Objetivos da Aula:

            Criar uma vídeoaula , utilizando até {numCenas} slides ({numCenas} cenas).
            Reescreva de uma forma dialogica, utilizando uma linguagem mais simples.
            Utilizar o HeyGen para o processamento do vídeo, empregando variáveis.
            """
    
    if numCenas == 1:
        prompt += f"""
            O Heygen aceita até 5000 caracteres, escreva o texto de forma clara para que todo mundo entenda.
            Quando necessario escreva um resumo que tenha menos de 5000 caracteres.
            """
        
    prompt += f"""
            Formato da Resposta:
                    
            *** Roteiro formatado em JSON.
            Variáveis: Utilizar titulo, subtitulo, topico, descricao, urlImg e decricaoImagem.
            Estrutura elementos_visuais: Arrays contendo objetos com texto (para título e subtítulo) e, quando aplicável, imagem (com urlImg e decricaoImagem).
            As frases de momentoChave das imagens devem corresponder exatamente ao que é dito no script sem ponto final.
            O momentoChave obrigatoriamente precisa estar no script com as mesmas palavras.
            Na última cena, apresentar um resumo da aula e realizar a despedida.
            Não escrever frases que se referencie a vídeo. Exemplo: "acompanhe uma explicação em vídeo", "observe o vídeo a seguir", "no vídeo a seguir".

            Instruções Detalhadas:

            *** Palavras-chave/Frases:
                REQUISITOS OBRIGATÓRIOS:
                1. Quantidade e Qualidade:
                    - 10-15 palavras-chave por cena (mais focadas e relevantes)
                    - Cada palavra-chave deve representar um conceito completo
                    - Priorizar conceitos técnicos e definições importantes
                    - Evitar frases incompletas ou sem contexto claro
                
                2. Critérios de Seleção:
                    - Conceitos fundamentais do tema
                    - Definições técnicas importantes
                    - Exemplos práticos significativos
                    - Relações de causa e efeito claras
                    - Conclusões relevantes
                    - Analogias completas e bem estruturadas
                
                3. Estrutura das Palavras-chave:
                    - Deve formar uma frase completa e significativa
                    - Deve transmitir um conceito claro quando lida isoladamente
                    - Deve ter entre 1 e 3 palavras
                    - Deve manter coerência com o contexto da cena
                
                4. Exemplos de Boas Palavras-chave:
                    - "computador"
                    - "programadores transformam necessidades"
                    - "soluções complexas"
                    - "Algoritmos"
                
                5. Exemplos de Palavras-chave a Evitar:
                    - Frases incompletas ("lê o problema e Peraí")
                    - Conceitos vagos ("surge a dúvida")
                    - Frases sem contexto ("mas e se o carro")
                    - Expressões genéricas ("pense num motorista")
                
                6. Validação das Palavras-chave:
                    - A frase deve existir no script
                    - Deve transmitir um conceito completo
                    - Deve fazer sentido quando lida isoladamente
                    - Deve contribuir para o entendimento do tema

                PROCESSO DE SELEÇÃO:
                1. Identificar os conceitos principais da cena
                2. Selecionar as definições técnicas importantes
                3. Capturar exemplos práticos completos
                4. Incluir relações causais relevantes
                5. Adicionar conclusões significativas

            *** Variáveis e Descrições:
            Utilizar as variáveis titulo, subtitulo, topico, descricao para palavras-chave e descrições textuais.
            Usar urlImg para indicar o link da imagem e decricaoImagem para descrevê-la.

            *** Profundidade do Roteiro:
            Elaborar um roteiro aprofundado, com informações detalhadas sobre o assunto de cada tópico/trecho.
            Garantir a coerência entre a duração do vídeo e a quantidade de conteúdo abordado.

            *** Imagens:
                REQUISITOS OBRIGATÓRIOS:
                1. Quantidade e Distribuição:
                    - Usar todas as imagens fornecidas no texto original
                    - Criar 5-6 imagens adicionais para enriquecer o conteúdo
                    - Distribuir as imagens uniformemente entre as cenas
                    - Máximo de 2 imagens por cena
                
                2. Formato do momentoChave:
                    - Deve ter entre 5 e 10 palavras
                    - DEVE ser uma frase EXATA do script
                    - Não pode estar no início ou fim do script
                    - Deve aparecer no mesmo contexto da imagem
                    - Não usar pontuação final
                
                3. Validação do momentoChave:
                    - Copiar e colar a frase diretamente do script
                    - Verificar se a frase existe ipsis litteris no script
                    - Garantir que a frase faça sentido isoladamente
                    - Confirmar que a frase representa o contexto da imagem
                
                4. Descrições de Imagem:
                    - decricaoImagem: 2-3 palavras em português
                    - descricaoBuscaEnvato: 10-15 palavras em inglês
                    - Descrições devem ser claras e específicas
                    - Evitar termos genéricos como "Imagem" ou "Foto"
                
                5. URLs e Referências:
                    - Usar formato urlImg para todas as imagens
                    - URLs devem ser válidas e acessíveis
                    - Manter consistência no formato das URLs
                    - Inserir no array de imagens, urlImg, momentoChave e a descricaoBuscaEnvato
                
                6. Proibições:
                    - NÃO usar momentoChave que não exista no script
                    - NÃO repetir o mesmo momentoChave
                    - NÃO usar frases genéricas
                    - NÃO usar momentoChave da introdução ou conclusão
                    - NÃO usar apenas palavras soltas como momentoChave

                PROCESSO DE SELEÇÃO DO MOMENTO CHAVE:
                1. Localizar o trecho do script onde a imagem será usada
                2. Identificar frases completas que representem o contexto
                3. Selecionar uma frase que tenha entre 5 e 10 palavras
                4. Copiar exatamente como está no script
                5. Validar se a frase faz sentido isoladamente
                
                DICAS PARA BOAS DESCRIÇÕES:
                - Ser específico sobre o conteúdo da imagem
                - Incluir elementos visuais importantes
                - Descrever o contexto da imagem
                - Usar terminologia apropriada
                - Manter consistência nas descrições

            *** Array de Imagens:
                REQUISITOS OBRIGATÓRIOS:
                1. Estrutura:
                    - Criar array "imagens" no nível raiz do JSON
                    - Cada imagem deve ter urlImg, momentoChave e descricaoBuscaEnvato
                    - Array deve conter todas as imagens do roteiro
                    - Garantir que cada imagem tenha momentoChave do script
                
                2. Conteúdo:
                    - Incluir TODAS as imagens mencionadas nas cenas
                    - Adicionar imagens do texto original
                    - Incluir imagens adicionais criadas
                    - Garantir que cada imagem tenha momentoChave do script
                
                3. Validação:
                    - Verificar correspondência com elementos_visuais das cenas
                    - Confirmar que todas as URLs estão no array
                    - Garantir que todos os momentoChave existem no script
                    - Validar descrições em inglês para Envato
                
                4. Organização:
                    - Listar imagens na ordem de aparição no roteiro
                    - Não duplicar imagens no array
                    - Manter consistência com as cenas
                    - Incluir todas as imagens antes das cenas

                IMPORTANTE: O array de imagens é OBRIGATÓRIO e deve ser incluído antes das cenas no JSON final.

            *** Vídeos:
            Não teremos vídeos.
            Quando aparecer um vídeo, não escrever falas referente a vídeo.
            Não escrever frases que se referencia a um vídeo. "acompanhe uma explicação em vídeo", "observe o vídeo a seguir", "Imagine um vídeo".

            *** Codigos:
            Quando receber um coigo (principais.code-snippet), escreva detalhadamente o codigo.

            *** Formulas:
            Quando receber uma formula (principais.tipografia), escreva detalhadamente a formula.
            Escreva a formula no array de formulas.

            *** Elementos Visuais:
            Cada cena/slide deve incluir um array elementos_visuais.
            Este array conterá objetos com texto (composto pelo titulo e subtitulo), e, se aplicável, objetos com imagem (com urlImg e decricaoImagem).
            Não abordar elementos HTML, CSS ou qualquer outro tema que não seja o conteúdo da aula.

            *** Última Cena:
            A última cena deve conter um breve resumo do conteúdo apresentado na aula.
            A despedida deve ocorrer somente na última frase.

            Formato JSON:
            Seguir a estrutura definida no schema fornecido para criar o JSON da resposta.
            Saída JSON: Retornar apenas a string do JSON, em formato puro (sem formatação, código ou instruções adicionais).
                

            **Entrada:**
                {texto}

            **Schema JSON:**
            {schema_texto}

            Ao final do json, verifque se todos os momentosChaves estão no script de narração. se não estiver, refaça o momento chave.

    """
    
    with open('prompt.txt', 'w', encoding='utf-8') as f:
        f.write(prompt)

    return prompt

response_schema_roteiro = {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "O título do vídeo"},
            "subtitulo": {"type": "string", "description": "Descrição do vídeo"},
            "imagens": {
                "type": "array",
                    "items": {
                    "type": "object",
                    "properties": {
                         "urlImg":{"type": "string", "description": "Conteúdo do elemento visual (URL da imagem)"},
                         "momentoChave":{"type": "string", "description": "DEVE ser uma frase EXATA do script"},
                         "descricaoBuscaEnvato":{"type": "string", "description": "Texto correspondente a descrição da imagem até 15 palavras em inglês"},
                        }
                    }
                },
            "codigo": {
                "type": "array",
                    "items": {
                    "type": "object",
                    "properties": {
                         "code-snippet":{"type": "string", "description": "Texto igual como foi recebido no JSON"},
                         "momentoChaveCodigo":{"type": "string", "description": "Texto completo referente ao code-snippet."},
                         "fimMomentoChaveCodigo":{"type": "string", "description": "final do Texto referente ao code-snippet."},
                        }
                    }
                },
            "formulas": {
                "type": "array",
                    "items": {
                    "type": "object",
                    "properties": {
                         "formula":{"type": "string", "description": "Texto igual como foi recebido no JSON"},
                         "momentoChaveFormula":{"type": "string", "description": "Texto completo referente a formula."},
                         "fimMomentoChaveFormula":{"type": "string", "description": "final do Texto referente a formula."},
                        }
                    }
                },
            "cenas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "cena": {"type": "integer", "description": "Número da cena"},
                        "tempo": {"type": "string", "description": "Tempo da cena no vídeo (ex: 0:00-1:00)"},
                        "script": {"type": "string", "description": "Narração da cena"},
                        "elementos_visuais": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tipo": {"type": "string", "description": "Tipo do elemento visual (texto, imagem)"},
                                    "titulo": {"type": "string", "description": "Titulo sobre o texto que esta sendo falado na cena "},
                                    "subtitulo": {"type": "string", "description": "Breve descrição sobre o texto que esta sendo falado na cena (até 20 palavras)"},
                                    "breveDescricao": {"type": "string", "description": "Breve resumo do que esta sendo falado no script, com ate 60 palavras"},
                                    "topico_1": {"type": "string", "description": "Breve descrição sobre o topico que esta sendo falado (até 20 palavras)"},
                                    "topico_2": {"type": "string", "description": "Breve descrição sobre o topico que esta sendo falado (até 20 palavras)"},
                                    "topico_3": {"type": "string", "description": "Breve descrição sobre o topico que esta sendo falado (até 20 palavras)"},
                                    "topico_4": {"type": "string", "description": "Breve descrição sobre o topico que esta sendo falado (até 20 palavras)"},
                                    "urlImg": {"type": "string", "description": "Conteúdo do elemento visual (URL da imagem)"},
                                    "decricaoImagem": {"type": "string", "description": "Conteúdo do elemento visual (texto ou URL da imagem até 3 palavras)"},
                                    "descricaoBuscaEnvato":{"type": "string", "description": "Texto correspondente a descrição da imagem até 15 palavras"},
                                    "estilo": {"type": "string", "description": "Estilo do elemento visual"}
                                },
                                "required": ["tipo", "variavel", "conteudo", "estilo"]
                            },
                            "description": "Elementos visuais da cena"
                        },
                        "palavras_chave": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Palavras-chave de 10 a 15 palavras na cena (podendo ser uma, duas ou tres palavras), devem ser palavras que estão no script da cena."
                        }
                    },
                    "required": ["cena", "tempo", "narracao", "elementos_visuais", "palavras_chave"]
                },
                "description": "Lista de cenas do vídeo"
            }
        },
        "required": ["titulo", "cenas"]
    }

momento_chave_exemplo = {
  "titulo": "Exemplo Curto: Desvendando o Computador",
  "subtitulo": "Demonstração de correspondência entre momentoChave e script.",
  "imagens": [
    {
      "urlImg": "https://img.freepik.com/free-vector/brain-thinking-bulb-concept_1017-28433.jpg",
      "momentoChave": "habilidade de reflexão e análise crítica",
      "descricaoBuscaEnvato": "Brain with light bulb, symbolizing idea and thinking."
    },
    {
      "urlImg": "https://img.freepik.com/free-vector/businessman-showing-gears-mechanism_107791-1400.jpg",
      "momentoChave": "entender o funcionamento básico dos computadores",
      "descricaoBuscaEnvato": "Businessman pointing at gears, representing system mechanism."
    }
  ],
  "codigo": [],
  "cenas": [
    {
      "cena": 1,
      "tempo": "0:00-0:30",
      "script": "Olá! Sejam bem-vindos. Em um mundo onde tudo acontece muito rápido, é fácil deixar de lado a habilidade de reflexão e análise crítica. Mas, pare um pouco e pense.",
      "elementos_visuais": [
        {
          "tipo": "imagem",
          "urlImg": "https://img.freepik.com/free-vector/brain-thinking-bulb-concept_1017-28433.jpg",
          "decricaoImagem": "Cérebro pensando",
          "descricaoBuscaEnvato": "Brain with light bulb, symbolizing idea and thinking."
        }
      ],
      "palavras_chave": [
        "reflexão",
        "análise crítica"
      ]
    },
    {
      "cena": 5,
      "tempo": "2:00-2:30",
      "script": "Então, qual a solução? Renegar a tecnologia não é o caminho. A melhor saída é entender o funcionamento básico dos computadores. Assim, mesmo com as mudanças tecnológicas, vamos compreender o sentido das atualizações.",
      "elementos_visuais": [
        {
          "tipo": "imagem",
          "urlImg": "https://img.freepik.com/free-vector/businessman-showing-gears-mechanism_107791-1400.jpg",
          "decricaoImagem": "Funcionamento do computador",
          "descricaoBuscaEnvato": "Businessman pointing at gears, representing system mechanism."
        }
      ],
      "palavras_chave": [
        "tecnologia de ponta",
        "análises críticas"
      ]
    }
  ]
}


def criar_payload_heygen(roteiro_json): # adicionado heygen_response
    """
    Cria o payload para a API do HeyGen com base no roteiro e na resposta do HeyGen.
    """

    payload = {
        "caption": False,
        "title": roteiro_json["titulo"],  # Título do vídeo
        "variables": {},
    }

    # Preenche os scripts do roteiro
    for i, cena in enumerate(roteiro_json["cenas"], start=1):
        script = cena["script"]
        payload["variables"][f"script_{i}"] = {
            "name": f"script_{i}",
            "type": "text",
            "properties": {"content": script}
        }

        if cena.get("elementos_visuais"):
            for elemento in cena["elementos_visuais"]: # Lidar com chave ausente
                print(elemento)
                if elemento["tipo"] == "imagem":
                    imagem_url = elemento.get("urlImg")
                    print(f"Imagem URL: {imagem_url}")
                    if imagem_url and imagem_url.startswith("Utilizar a imagem"): #Improved check
                        try:
                            imagem_index = int(imagem_url.split(" ")[3].rstrip("do JSON")) - 1 #Improved index extraction
                            imagem_url = roteiro_json["imagens"][imagem_index]["urlimg"]
                        except (IndexError, ValueError, KeyError):
                            print(f"Warning: Invalid image reference '{imagem_url}' in scene {i}. Using placeholder.")
                            imagem_url = "placeholder_image.jpg" # Or some other default
                    
                    payload["variables"][f"image_{i}"] = {
                        "name": f"image_{i}",
                        "type": "image",
                        "properties": {
                            "url": imagem_url if imagem_url else None, #None is still correctly handled here.
                            "asset_id": None,
                            "fit": "contain"
                        }
                    }

                elif elemento["tipo"] == "texto":
                    titulo = elemento.get("titulo", "") 
                    subtitulo = elemento.get("subtitulo", "")

                    print(f"Título: {titulo}, Subtítulo: {subtitulo}")

                    payload["variables"][f"titulo_{i}"] = {
                        "name": f"titulo_{i}",
                        "type": "text",
                        "properties": {
                            "content": titulo
                            }
                    }
                    payload["variables"][f"subtitulo_{i}"] = {
                        "name": f"subtitulo_{i}",
                        "type": "text",
                        "properties": {
                            "content": subtitulo
                            }
                    }

    return payload



def criar_payload_heygen_template_1(roteiro_json): # adicionado heygen_response
    """
    Cria o payload para a API do HeyGen com base no roteiro e na resposta do HeyGen.
    """

    payload = {
        "caption": False,
        "title": roteiro_json["titulo"],  # Título do vídeo
        "variables": {},
    }

    # Preenche os scripts do roteiro
    for i, cena in enumerate(roteiro_json["cenas"], start=1):
        script = cena["script"]
        payload["variables"][f"script_{i}"] = {
            "name": f"script_{i}",
            "type": "text",
            "properties": {"content": script}
        }

        if cena.get("elementos_visuais"):
            for elemento in cena["elementos_visuais"]: # Lidar com chave ausente
                if elemento["tipo"] == "imagem" and i == 4:
                    imagem_url = elemento.get("urlImg")
                    print(f"Imagem URL: {imagem_url}")
                    if imagem_url and imagem_url.startswith("Utilizar a imagem"): #Improved check
                        try:
                            imagem_index = int(imagem_url.split(" ")[3].rstrip("do JSON")) - 1 #Improved index extraction
                            imagem_url = roteiro_json["imagens"][imagem_index]["urlimg"]
                        except (IndexError, ValueError, KeyError):
                            print(f"Warning: Invalid image reference '{imagem_url}' in scene {i}. Using placeholder.")
                            imagem_url = "placeholder_image.jpg" # Or some other default
                    
                    payload["variables"][f"image_{i}"] = {
                        "name": f"image_{i}",
                        "type": "image",
                        "properties": {
                            "url": imagem_url if imagem_url else None, #None is still correctly handled here.
                            "asset_id": None,
                            "fit": "contain"
                        }
                    }

                elif elemento["tipo"] == "texto":
                    titulo = elemento.get("titulo", "") 
                    subtitulo = elemento.get("subtitulo", "")
                    breveDescricao = elemento.get("breveDescricao", "")            


                    print(f"Título: {titulo}, Subtítulo: {subtitulo}", f"Breve Descrição: {breveDescricao}")

                    payload["variables"][f"titulo_{i}"] = {
                        "name": f"titulo_{i}",
                        "type": "text",
                        "properties": {
                            "content": titulo
                            }
                    }
                    payload["variables"][f"subtitulo_{i}"] = {
                        "name": f"subtitulo_{i}",
                        "type": "text",
                        "properties": {
                            "content": subtitulo
                            }
                    }
                    payload["variables"][f"breveDesc_{i}"] = {
                        "name": f"breveDesc_{i}",
                        "type": "text",
                        "properties": {
                            "content": breveDescricao
                            }
                    }
                    if "topico_1" in elemento and i == 3:
                        topico_1 = elemento.get("topico_1", "")
                        topico_2 = elemento.get("topico_2", "")
                        topico_3 = elemento.get("topico_3", "")
                        topico_4 = elemento.get("topico_4", "")

                        print(f"Topico 1: {topico_1}, Topico 2: {topico_2}, Topico 3: {topico_3}, Topico 4: {topico_4}")

                        payload["variables"][f"topico_1"] = {
                            "name": f"topico_1",
                            "type": "text",
                            "properties": {
                                "content": topico_1
                            }
                        }
                        payload["variables"][f"topico_2"] = {
                            "name": f"topico_2",
                            "type": "text",
                            "properties": {
                                "content": topico_2
                            }
                        }
                        payload["variables"][f"topico_3"] = {
                            "name": f"topico_3",
                            "type": "text",
                            "properties": {
                                "content": topico_3
                            }
                        }
                        payload["variables"][f"topico_4"] = {
                            "name": f"topico_4",
                            "type": "text",
                            "properties": {
                                "content": topico_4
                            }
                        }

    return payload

def criar_payload_heygen_template_3(roteiro_json): # adicionado heygen_response
    """
    Cria o payload para a API do HeyGen com base no roteiro e na resposta do HeyGen.

    Recebe:
    - roteiro_json: Roteiro em formato JSON

    Retorna:
    - Payload para a API do HeyGen
    """

    payload = {
        "caption": False,
        "title": roteiro_json["titulo"],  # Título do vídeo
        "dimension": {
            "width": 1280,
            "height": 720
        },
       

        "variables": {},
    }

    # Preenche os scripts do roteiro
    for i, cena in enumerate(roteiro_json["cenas"], start=1):
        script = cena["script"]
        payload["variables"][f"script_{i}"] = {
            "name": f"script_{i}",
            "type": "text",
            "properties": {"content": script}
        }            

    return payload