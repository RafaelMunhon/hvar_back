Video Studio API
==============

API Principal
------------
.. automodule:: app.api.video_studio
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Processamento de Vídeo
--------------------

Editor de Vídeo
~~~~~~~~~~~~~
.. automodule:: app.editandoVideo.editando_video_studio
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Processamento de Texto e Overlay
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. automodule:: app.services.text_overlay_service_studio
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Processamento de Áudio
~~~~~~~~~~~~~~~~~~~
.. automodule:: app.services.speech_service
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Serviços de IA
------------

Vertex AI
~~~~~~~~
.. automodule:: app.services.vertexai_service
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Busca de Imagens
--------------

Envato
~~~~~
.. automodule:: app.searchImagens.searchImagens_Envato
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Pexels
~~~~~
.. automodule:: app.searchImagens.searchImagens_Pexel
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Banco de Dados
------------
.. automodule:: app.bd.bd
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

Fluxo de Trabalho
---------------

1. Recebe o conteúdo do vídeo e configurações
2. Processa o texto e gera o roteiro
3. Busca imagens no Envato/Pexels conforme necessário
4. Gera narração usando serviço de voz
5. Aplica efeitos e sobreposições de texto
6. Renderiza o vídeo final com ffmpeg
7. Salva o vídeo e metadados no banco de dados 