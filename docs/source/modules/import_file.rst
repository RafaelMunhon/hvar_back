File Import API
=============

API de Importação
---------------
.. automodule:: app.api.import_file
   :members:
   :undoc-members:
   :show-inheritance:

Funcionalidades
-------------

Verificação de Arquivos
~~~~~~~~~~~~~~~~~~~~~
.. autofunction:: app.api.import_file.check_file_exists

Importação de JSON
~~~~~~~~~~~~~~~~
.. autofunction:: app.api.import_file.import_json_to_db

Processamento de Arquivos
~~~~~~~~~~~~~~~~~~~~~~
Funções internas para processamento de arquivos ZIP e JSON.

Fluxo de Trabalho
---------------

1. Recebe arquivo (ZIP/JSON/TXT)
2. Verifica existência do arquivo no sistema
3. Se ZIP:
   - Extrai e processa todos os arquivos
   - Identifica conteúdo inicial
   - Processa arquivos adicionais
4. Se JSON/TXT:
   - Valida formato do conteúdo
   - Processa arquivo único
5. Salva ou atualiza no banco de dados
6. Retorna confirmação do processamento 