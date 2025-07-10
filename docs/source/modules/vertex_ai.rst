Vertex AI
========

Configuração e Integração
----------------------
.. automodule:: app.config.vertexAi
   :members:
   :undoc-members:
   :show-inheritance:

Principais Funcionalidades
----------------------

Inicialização
~~~~~~~~~~~
.. autofunction:: app.config.vertexAi.init_vertex_ai

Configuração do Modelo
~~~~~~~~~~~~~~~~~~
.. autofunction:: app.config.vertexAi.get_model
.. autofunction:: app.config.vertexAi.get_generation_config

Geração de Conteúdo
~~~~~~~~~~~~~~~~
.. autofunction:: app.config.vertexAi.generate_content
.. autofunction:: app.config.vertexAi.generate

Configurações de Segurança
~~~~~~~~~~~~~~~~~~~~~~~
.. autofunction:: app.config.vertexAi.get_safety_settings

Fluxo de Trabalho
---------------

1. Inicialização do Vertex AI
   - Carrega credenciais
   - Configura projeto
   - Inicializa cliente

2. Configuração do Modelo
   - Define parâmetros do modelo
   - Ajusta configurações de geração
   - Define limites de tokens

3. Geração de Conteúdo
   - Recebe prompt
   - Processa com modelo selecionado
   - Aplica configurações de segurança
   - Retorna resposta gerada

4. Tratamento de Respostas
   - Valida saída do modelo
   - Formata resposta
   - Trata erros e exceções

Parâmetros de Configuração
-----------------------

Modelo
~~~~~
- Temperatura: Controla criatividade
- Top-k: Limita opções de tokens
- Top-p: Amostragem núcleo
- Candidate count: Número de respostas

Segurança
~~~~~~~~
- Harm categories: Categorias de conteúdo impróprio
- Threshold: Limites de segurança
- Blocklist: Termos bloqueados 