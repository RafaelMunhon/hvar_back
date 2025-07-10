Serviços de Áudio
===============

Audiobook
--------
.. automodule:: app.api.audiobook
   :members:
   :undoc-members:
   :show-inheritance:

Serviço de Audiobook
~~~~~~~~~~~~~~~~~
.. automodule:: app.services.audiobook_service
   :members:
   :undoc-members:
   :show-inheritance:

Audio Q&A
--------
.. automodule:: app.api.audioqa
   :members:
   :undoc-members:
   :show-inheritance:

Serviço de Q&A
~~~~~~~~~~~~
.. automodule:: app.services.audioqa_service
   :members:
   :undoc-members:
   :show-inheritance:

Podcast
------
.. automodule:: app.api.podcast
   :members:
   :undoc-members:
   :show-inheritance:

Serviço de Podcast
~~~~~~~~~~~~~~~
.. automodule:: app.services.podcast_service
   :members:
   :undoc-members:
   :show-inheritance:

Microlearning
-----------
.. automodule:: app.api.microlearning
   :members:
   :undoc-members:
   :show-inheritance:

Serviço de Microlearning
~~~~~~~~~~~~~~~~~~~~~
.. automodule:: app.services.microlearning_service
   :members:
   :undoc-members:
   :show-inheritance:

Fluxo de Trabalho
---------------

Audiobook
~~~~~~~~
1. Recebe o texto do conteúdo
2. Processa e melhora o texto usando IA
3. Converte o texto em áudio usando TTS
4. Salva o audiobook no GCS
5. Registra no banco de dados

Audio Q&A
~~~~~~~~
1. Recebe perguntas do usuário
2. Gera respostas usando IA
3. Converte respostas em áudio
4. Retorna áudio da resposta

Podcast
~~~~~~
1. Recebe conteúdo do tema
2. Gera roteiro de podcast
3. Converte em áudio
4. Adiciona efeitos e música
5. Salva o podcast finalizado

Microlearning
~~~~~~~~~~~
1. Recebe conteúdo educacional
2. Adapta para formato curto
3. Gera áudio do microconteúdo
4. Salva versão final 