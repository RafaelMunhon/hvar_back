Video 100% IA API
===============

API Principal
-----------
.. automodule:: app.api.video
   :members:
   :undoc-members:
   :show-inheritance:

Serviços Principais
----------------

Serviço de Vídeo
~~~~~~~~~~~~~~
.. automodule:: app.services.video_service
   :members:
   :undoc-members:
   :show-inheritance:

Serviço de IA
~~~~~~~~~~~
.. automodule:: app.services.vertexai_service
   :members:
   :undoc-members:
   :show-inheritance:

Processamento de Mídia
-------------------

Edição de Vídeo
~~~~~~~~~~~~~
.. automodule:: app.editandoVideo.edicao_video
   :members:
   :undoc-members:
   :show-inheritance:

Processamento de Áudio
~~~~~~~~~~~~~~~~~~~
.. automodule:: app.services.speech_service
   :members:
   :undoc-members:
   :show-inheritance:

Sobreposição de Texto
~~~~~~~~~~~~~~~~~~
.. automodule:: app.services.text_overlay_service
   :members:
   :undoc-members:
   :show-inheritance:

Busca de Imagens
-------------

Envato
~~~~~
.. automodule:: app.searchImagens.searchImagens_Envato
   :members:
   :undoc-members:
   :show-inheritance:

Pexels
~~~~~
.. automodule:: app.searchImagens.searchImagens_Pexel
   :members:
   :undoc-members:
   :show-inheritance:

Utilitários
---------

Gerenciamento de Arquivos
~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: app.core.file_manager
   :members:
   :undoc-members:
   :show-inheritance:

Banco de Dados
~~~~~~~~~~~
.. automodule:: app.bd.bd
   :members:
   :undoc-members:
   :show-inheritance:

Fluxo de Trabalho
---------------

1. O usuário faz uma requisição através da API principal
2. O serviço de vídeo coordena o processo
3. O serviço de IA (Vertex AI) gera o conteúdo
4. As imagens são buscadas no Envato e Pexels
5. O áudio é processado e sincronizado
6. O texto é sobreposto no vídeo
7. O vídeo final é editado e renderizado
8. O resultado é salvo no banco de dados 