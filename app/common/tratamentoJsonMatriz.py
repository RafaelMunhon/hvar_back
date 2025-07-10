import sys
import os
from google.cloud import bigquery
from pydantic import BaseModel
import logging
import re
from typing import Dict, Optional, Union, List, Any

# Adicionar o diretório raiz do projeto ao sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from app.models import model


def get_component_classes():
    """
    Obtém as classes de componentes disponíveis.

    Retorna:
    - Dicionário com as classes de componentes
    """
    return {
        cls.component: cls
        for name in dir(model)
        if (cls := getattr(model, name))
        and isinstance(cls, type)
        and issubclass(cls, BaseModel)
        and hasattr(cls, "component")
    }

def buscaPromptMatriz(data: Union[Dict, List[Dict]], component_classes):
    """
    Busca o prompt da matriz de componentes.

    Recebe:
    - data: Dados para buscar o prompt
    - component_classes: Classes de componentes disponíveis 

    Retorna:
    - Texto completo com os prompts das matrizes de componentes
    """
    componentes = []

    #Verifica se data é uma lista, se for, usa o tratamento anterior.
    if isinstance(data, list):
          conteudo_do_componente = data
    elif isinstance(data, dict) and  ('conteudo' in data or 'conteudo_introducao' in data):
      conteudo_do_componente = data.get('conteudo') or data.get('conteudo_introducao')
    else:
          # Caso o data seja diretamente um componente (json sem "conteudo")
        conteudo_do_componente = [data]

    if conteudo_do_componente:
        for item in conteudo_do_componente:
            componente = item.get('__component')
            variante = item.get('variante')
            prompt = consultar_bigquery(componente, variante) if componente else None
            
            if componente:
                
                componente_obj = mapear_componente(componente, item, component_classes)
                componentes.append({
                    "componente": componente,
                    "variante": variante,
                    "prompt": prompt,
                    "objeto": componente_obj,
                   "nao_mapeado": False,
                  "sem_prompt":True if prompt == None else False
                })
            else: # componente não mapeado (novo else)
                 componentes.append({
                      "componente": componente,
                      "variante": variante,
                      "prompt": prompt,
                      "objeto": item,
                      "nao_mapeado":True,
                      "sem_prompt":True if prompt == None else False
                  })
    resultado = tratamentoObjetoComponentes(componentes)
    return resultado

def tratamentoObjetoComponentes(arrayMatriz):
    """
    Trata os objetos de componentes.

    Recebe:
    - arrayMatriz: Lista de dicionários com informações sobre os componentes

    Retorna:
    - Texto completo com os prompts das matrizes de componentes
    """
    texto_completo = ""

    for item in arrayMatriz:
        promptMatriz = f"Informações para o Roteiro: {item.get('prompt')}\n\n" if item.get('prompt') else ""
        objeto = item.get('objeto')
        componente = item.get('componente')
        texto_componente = ""
    
         # Adiciona o prompt no início de cada iteração
        texto_componente += f"{promptMatriz} Texto:\n"

        if item.get("nao_mapeado"): #Tratamento caso não tenha mapeado o component
            texto_componente += f"Atenção: O texto abaixo também faz parte do conteúdo, mesmo que o componente '{componente}' não tenha um tratamento específico configurado. \n"

        elif item.get("sem_prompt"): #Tratamento caso o prompt não seja encontrado para determinado component
            texto_componente += f"Atenção: O texto abaixo também faz parte do conteúdo, e não foi encontrado um prompt específico no BigQuery para o componente '{componente}'. \n"
            if componente in component_extractors: # se o componente é mapeado ele é processado da mesma forma que antes, por garantia. 
               texto_extraido = component_extractors[componente](objeto)
               texto_componente += f"{texto_extraido if texto_extraido else ''}\n" 

        elif componente in component_extractors: # Tratamento para o component que esta mapeado e existe um prompt associado. 
                texto_extraido = component_extractors[componente](objeto)
                texto_componente += f"{texto_extraido if texto_extraido else ''}\n"


        texto_completo += "\n" + texto_componente + "\n"

    return texto_completo

def consultar_bigquery(componente, variante=None):
  """
  Consulta o prompt da matriz de componentes no BigQuery.

  Recebe:
  - componente: Nome do componente a ser consultado
  - variante: Variante do componente a ser consultada (opcional)
  """
  client = bigquery.Client()
  
  query = """
    SELECT PROMPT
      FROM `conteudo-autenticare.poc_dataset.PROMPT_IA`
      WHERE COMPONENT = @componente
    """
  job_config = bigquery.QueryJobConfig(
    query_parameters=[
      bigquery.ScalarQueryParameter("componente", "STRING", componente)
      ])
    
  if variante and componente == "principais.tipografia":
     query = """
    SELECT PROMPT
    FROM `conteudo-autenticare.poc_dataset.PROMPT_IA`
    WHERE COMPONENT = @componente AND VARIANTE = @variante
    """
     job_config = bigquery.QueryJobConfig(
         query_parameters=[
            bigquery.ScalarQueryParameter("componente", "STRING", componente),
            bigquery.ScalarQueryParameter("variante", "STRING", variante)
            ]
         )
        
  query_job = client.query(query, job_config=job_config)
  results = query_job.result()
  
  return next((row.PROMPT for row in results), None)

def mapear_componente(componente, item, component_classes):
    """
    Mapeia o componente para a classe correspondente.

    Recebe:
    - componente: Nome do componente a ser mapeado
    - item: Item a ser mapeado
    - component_classes: Classes de componentes disponíveis

    Retorna:
    - Objeto mapeado ou None se não encontrado
    """
    componente_classe = component_classes.get(componente)
    if componente_classe:
        return componente_classe(**item)
    else:
        logging.warning(f"Componente não mapeado: {componente}")
        return None
    
def extrair_texto_de_html(html_string: Optional[str]) -> Optional[str]:
    if not isinstance(html_string, str):
        return None
    textos_p = re.findall(r'<p.*?>(.*?)</p>', html_string, flags=re.IGNORECASE)
    return '\n'.join(textos_p)


def _extrair_texto_card(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'titulo_card'):
      textos.append(f"Título do Card: {getattr(objeto, 'titulo_card', None)}")
    if objeto and hasattr(objeto, 'descricao_card'):
      textos.append(f"Descrição do Card: {getattr(objeto, 'descricao_card', None)}")

    return '\n'.join([t for t in textos if t]) or None

def _extrair_texto_item_carrossel(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'titulo_texto'):
        textos.append(f"Título do Item do Carrossel: {getattr(objeto, 'titulo_texto', None)}")
    if objeto and hasattr(objeto, 'conteudo_texto'):
        conteudo_texto = getattr(objeto, 'conteudo_texto', None)
        textos.append(f"Conteúdo do Item do Carrossel: {extrair_texto_de_html(conteudo_texto) if conteudo_texto else None}")
    if objeto and hasattr(objeto, 'legenda'):
        textos.append(f"Legenda: {getattr(objeto, 'legenda', None)}")

    if objeto and hasattr(objeto, 'imagem') and objeto.imagem and hasattr(objeto.imagem, 'formats') and objeto.imagem.formats and 'medium' in objeto.imagem.formats:
       medium_url = objeto.imagem.formats.get('medium').get('url',None)
       textos.append(f"URL da Imagem (Medium): {medium_url}")

    return '\n'.join([t for t in textos if t]) or None

def _extrair_texto_alternativa(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto, 'alternativa_resposta'):
     textos.append(f"Alternativa Resposta: {getattr(objeto, 'alternativa_resposta', None)}")
  if objeto and hasattr(objeto, 'legenda'):
     textos.append(f"Legenda: {getattr(objeto, 'legenda', None)}")
  return '\n'.join([t for t in textos if t]) or None


def _extrair_texto_card_timeline(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'label'):
      textos.append(f"Label do Card Timeline: {getattr(objeto, 'label', None)}")
   if objeto and hasattr(objeto, 'titulo'):
      textos.append(f"Título do Card Timeline: {getattr(objeto, 'titulo', None)}")
   if objeto and hasattr(objeto, 'subtitulo'):
       textos.append(f"Subtítulo do Card Timeline: {getattr(objeto, 'subtitulo', None)}")
   if objeto and hasattr(objeto, 'descricao'):
        textos.append(f"Descrição do Card Timeline: {getattr(objeto, 'descricao', None)}")
   if objeto and hasattr(objeto, 'legenda'):
       textos.append(f"Legenda: {getattr(objeto, 'legenda', None)}")
   
   return '\n'.join([t for t in textos if t]) or None


def _extrair_texto_imagem(objeto) -> Optional[str]:
   if objeto and hasattr(objeto, 'imagem') and hasattr(objeto.imagem,'url') and isinstance(getattr(objeto.imagem, 'url'), str):
        url = getattr(objeto.imagem, 'url')
        legenda = getattr(objeto,'legenda',None)

        if url or legenda:
            textos = []
            if url:
                textos.append(f"URL da Imagem: {url}")
            if legenda:
                textos.append(f"Legenda: {legenda}")
            return "\n".join(textos)
   return None

def _extrair_texto_zoom(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto, 'legenda'):
        textos.append(f"Legenda: {getattr(objeto, 'legenda', None)}")
  if objeto and hasattr(objeto,'imagem_zoom') and hasattr(objeto.imagem_zoom, 'url') and isinstance(getattr(objeto.imagem_zoom, 'url'), str):
          url_imagem_zoom = getattr(objeto.imagem_zoom, 'url')
          textos.append(f"URL Imagem Zoom: {url_imagem_zoom}")

  return '\n'.join([t for t in textos if t]) or None



def _extrair_texto_antes_depois(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'descricao'):
        textos.append(f"Descrição: {getattr(objeto, 'descricao', None)}")

   return "\n".join(textos) or None



def _extrair_texto_atividade_pratica(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto, 'enunciado_atividade_pratica'):
      textos.append(f"Enunciado: {getattr(objeto, 'enunciado_atividade_pratica', None)}")
  if objeto and hasattr(objeto, 'titulo_atividade_pratica'):
       textos.append(f"Título: {getattr(objeto, 'titulo_atividade_pratica', None)}")

  return "\n".join([t for t in textos if t]) or None

def _extrair_texto_caixa_formula(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'titulo'):
      textos.append(f"Título da Caixa Fórmula: {getattr(objeto, 'titulo', None)}")
   if objeto and hasattr(objeto, 'legenda'):
       textos.append(f"Legenda da Caixa Fórmula: {getattr(objeto, 'legenda', None)}")
   if objeto and hasattr(objeto, 'transcricao'):
       textos.append(f"Transcrição da Caixa Fórmula: {getattr(objeto, 'transcricao', None)}")
   if objeto and hasattr(objeto, 'formula'):
       textos.append(f"Formula da Caixa Fórmula: {getattr(objeto, 'formula', None)}")
   
   return "\n".join([t for t in textos if t]) or None


def _extrair_texto_card_comparativo(objeto) -> Optional[str]:
   textos = []
   card1_text = _extrair_texto_card(getattr(objeto, 'card1', None)) if hasattr(objeto, 'card1') else None
   card2_text = _extrair_texto_card(getattr(objeto, 'card2', None)) if hasattr(objeto, 'card2') else None
   if card1_text:
     textos.append(f"Card 1:\n{card1_text}")
   if card2_text:
      textos.append(f"Card 2:\n{card2_text}")
   return "\n".join(textos) or None

def _extrair_texto_card_feedback(objeto) -> Optional[str]:
     card = getattr(objeto, 'card', None)
     if card:
          card_text =  _extrair_texto_card(card) if hasattr(objeto,'card') else None
          return  f"Card Feedback:\n{card_text}"  if card_text else None
     return None
def _extrair_texto_card_player(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'titulo_card'):
        textos.append(f"Título do Card Player: {getattr(objeto, 'titulo_card', None)}")
    if objeto and hasattr(objeto, 'descricao_card'):
        textos.append(f"Descrição do Card Player: {getattr(objeto, 'descricao_card', None)}")
    return '\n'.join([t for t in textos if t]) or None
  
def _extrair_texto_card_tematico(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto, 'titulo_card_tematico'):
    textos.append(f"Título do Card Temático: {getattr(objeto, 'titulo_card_tematico', None)}")
  if objeto and hasattr(objeto, 'conteudo_card_tematico'):
      conteudo =  getattr(objeto, 'conteudo_card_tematico', None)
      textos.append(f"Conteúdo do Card Temático: {extrair_texto_de_html(conteudo) if conteudo else None}")
    
  return '\n'.join([t for t in textos if t]) or None


def _extrair_texto_carrossel(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'itens_carrossel') and isinstance(getattr(objeto, 'itens_carrossel'),list):
        for item_carrossel in  getattr(objeto, 'itens_carrossel', []):
            item_carrossel_text = _extrair_texto_item_carrossel(item_carrossel) if item_carrossel else None
            if item_carrossel_text:
               textos.append(item_carrossel_text)
   return "\n".join([t for t in textos if t]) or None

def _extrair_texto_chave_resposta(objeto) -> Optional[str]:
  if objeto and hasattr(objeto, 'conteudo_feedback'):
    textos = []
    for item_feedback in getattr(objeto, 'conteudo_feedback'):
          for key, value in item_feedback.items():
            textos.append(f"Chave Resposta {key}: {extrair_texto_de_html(value) if value else None}")
    return '\n'.join(textos) or None
  return None


def _extrair_texto_code_snippet(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'snippet_codigo'):
        textos.append(f"Snippet de Código: {getattr(objeto, 'snippet_codigo', None)}")
   if objeto and hasattr(objeto, 'linguagem'):
      textos.append(f"Linguagem do Snippet de Código: {getattr(objeto, 'linguagem', None)}")
   return '\n'.join(textos) or None


def _extrair_texto_code_compiler(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'codigo_padrao'):
         textos.append(f"Código Padrão: {getattr(objeto, 'codigo_padrao', None)}")
    if objeto and hasattr(objeto, 'linguagem'):
        textos.append(f"Linguagem: {getattr(objeto, 'linguagem', None)}")
    return '\n'.join(textos) or None
 

def _extrair_texto_destaque_texto(objeto) -> Optional[str]:
    if objeto and hasattr(objeto, 'conteudo'):
       return f"Conteúdo do Destaque: {extrair_texto_de_html(getattr(objeto, 'conteudo', None))}"
    return None


def _extrair_texto_grupo_accordion(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'accordions') and isinstance(getattr(objeto, 'accordions'),list):
    for item_accordion in getattr(objeto, 'accordions', []):
        textos_item = []
        for key, value in item_accordion.items():
             textos_item.append(f"{key} : {extrair_texto_de_html(value) if value else None}")

        textos.append('\n'.join(textos_item) )
    return '\n'.join([t for t in textos if t]) or None
   return None

def _extrair_texto_grupo_card_player(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto, 'cards') and isinstance(getattr(objeto,'cards'),list):
     for card_player in  getattr(objeto,'cards', []):
         card_player_text = _extrair_texto_card_player(card_player)
         if card_player_text:
              textos.append(f"Card Player:\n {card_player_text}")

  return "\n".join(textos) if textos else None


def _extrair_texto_grupo_card(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'cards') and isinstance(getattr(objeto, 'cards'), list):
        for card in getattr(objeto,'cards',[]):
            card_text = _extrair_texto_card(card)
            if card_text:
               textos.append(f"Card:\n{card_text}")
            
            if card and hasattr(card,'imagem') and card.imagem and hasattr(card.imagem,'url') and isinstance(getattr(card.imagem, 'url'), str):
                url_imagem = card.imagem.url
                textos.append(f"URL da Imagem: {url_imagem}")
                
    return '\n'.join([t for t in textos if t]) or None

def _extrair_texto_grupo_imagem(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto, 'imagens') and isinstance(getattr(objeto,'imagens'), list):
      for imagem in  getattr(objeto,'imagens', []):
           text_imagem = _extrair_texto_imagem(imagem)
           if text_imagem:
            textos.append(f"Imagem:\n{text_imagem}")

  return '\n'.join([t for t in textos if t]) or None

def _extrair_texto_grupo_zoom(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'imagens') and isinstance(getattr(objeto, 'imagens'), list):
       for zoom in  getattr(objeto, 'imagens', []):
            text_zoom = _extrair_texto_zoom(zoom)
            if text_zoom:
                textos.append(f"Zoom:\n{text_zoom}")

    return "\n".join([t for t in textos if t]) if textos else None


def _extrair_texto_patterns_imagem(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'texto'):
       textos.append(f"Texto do Pattern Imagem: {getattr(objeto, 'texto', None)}")
    if objeto and hasattr(objeto,'legenda'):
          textos.append(f"Legenda do Pattern Imagem: {getattr(objeto,'legenda', None)}")

    if objeto and hasattr(objeto, 'imagem') and hasattr(objeto.imagem,'url') and isinstance(getattr(objeto.imagem, 'url'), str):
            url = getattr(objeto.imagem, 'url')
            textos.append(f"URL da Imagem do Pattern: {url}")
    
    return '\n'.join([t for t in textos if t]) or None
    

def _extrair_texto_questao(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'enunciado_questao'):
        textos.append(f"Enunciado da Questão: {getattr(objeto, 'enunciado_questao', None)}")

   if objeto and hasattr(objeto, 'alternativas') and isinstance(getattr(objeto, 'alternativas'),list):
      for alternativa in  getattr(objeto,'alternativas',[]):
           alternativa_text = _extrair_texto_alternativa(alternativa)
           if alternativa_text:
              textos.append(f"Alternativa:\n{alternativa_text}")
           
   if objeto and hasattr(objeto,'feedback_positivo') :
        textos.append(f"Feedback Positivo: {getattr(objeto,'feedback_positivo', None)}")

   if objeto and hasattr(objeto,'feedback_negativo'):
         textos.append(f"Feedback Negativo: {getattr(objeto, 'feedback_negativo', None)}")
        
   return "\n".join(textos) or None
        

def _extrair_texto_quote(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'texto'):
         textos.append(f"Texto do Quote: {extrair_texto_de_html(getattr(objeto,'texto', None))}")
   if objeto and hasattr(objeto, 'autor'):
      textos.append(f"Autor do Quote: {getattr(objeto,'autor', None)}")

   return '\n'.join([t for t in textos if t]) or None

def _extrair_texto_tab_destaque(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto,'tabs') and isinstance(getattr(objeto, 'tabs'), list):
        for item_tab in getattr(objeto,'tabs',[]):
          textos_item = []
          for key, value in item_tab.items():
               textos_item.append(f"{key} : {extrair_texto_de_html(value) if value else None}")
          textos.append('\n'.join(textos_item))

    return '\n'.join([t for t in textos if t]) or None

def _extrair_texto_texto(objeto) -> Optional[str]:
  textos = []
  if objeto and hasattr(objeto,'titulo'):
    textos.append(f"Título do Texto: {getattr(objeto, 'titulo', None)}")
  if objeto and hasattr(objeto,'conteudo_texto'):
        conteudo_texto =  getattr(objeto,'conteudo_texto', None)
        textos.append(f"Conteúdo do Texto: {extrair_texto_de_html(conteudo_texto) if conteudo_texto else None}")

  return "\n".join(textos) or None
    
def _extrair_texto_texto_com_background(objeto) -> Optional[str]:
  if objeto and hasattr(objeto, 'texto'):
        return f"Texto: {extrair_texto_de_html(getattr(objeto,'texto', None))}"
  return None

def _extrair_texto_timeline(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'cards_timeline') and isinstance(getattr(objeto,'cards_timeline'), list):
       for card_timeline in getattr(objeto, 'cards_timeline',[]):
           card_timeline_text = _extrair_texto_card_timeline(card_timeline)
           if card_timeline_text:
                textos.append(f"Card Timeline:\n {card_timeline_text}")
   return "\n".join(textos) or None


def _extrair_texto_timeline_horizontal(objeto) -> Optional[str]:
   textos = []
   if objeto and hasattr(objeto, 'cards_timeline') and isinstance(getattr(objeto, 'cards_timeline'), list):
       for card_timeline in getattr(objeto, 'cards_timeline',[]):
           card_timeline_text = _extrair_texto_card_timeline(card_timeline)
           if card_timeline_text:
                textos.append(f"Card Timeline:\n {card_timeline_text}")
   return "\n".join(textos) or None


def _extrair_texto_tipografia(objeto) -> Optional[str]:
    if objeto and hasattr(objeto, 'texto'):
        texto = getattr(objeto, 'texto')
        return extrair_texto_de_html(texto) if isinstance(texto,str) and  "<p" in texto else texto
    return None


def _extrair_texto_tipografia_modal(objeto) -> Optional[str]:
    textos = []
    if objeto and hasattr(objeto, 'texto'):
          texto = getattr(objeto,'texto')
          textos.append(f"Texto da Tipografia Modal: {extrair_texto_de_html(texto) if isinstance(texto,str) and '<p' in texto  else texto if texto else None }")
    if objeto and hasattr(objeto,'modais') and isinstance(getattr(objeto,'modais'), list):
       for modal in  getattr(objeto,'modais', []):
          textos_modal = []
          for key,value in modal.items():
              textos_modal.append(f"{key}: {extrair_texto_de_html(value) if isinstance(value,str) and  '<p' in value else value if value else None }")
          textos.append( '\n'.join(textos_modal) if textos_modal else "")

    return '\n'.join([t for t in textos if t]) if textos else None


def _extrair_texto_video(objeto) -> Optional[str]:
   if objeto and hasattr(objeto, 'urlVideo'):
      return f"URL do Video: {getattr(objeto, 'urlVideo', None)}"
   return None


def _extrair_texto_audio(objeto) -> Optional[str]:
    if objeto and hasattr(objeto, 'url_audio'):
      return  f"URL do Audio: {getattr(objeto,'url_audio', None)}"
    return None


component_extractors = {
    "aux-card.card": _extrair_texto_card,
    "aux-carrossel.item-carrossel": _extrair_texto_item_carrossel,
    "aux-questao.alternativa": _extrair_texto_alternativa,
    "aux-card.card-timeline": _extrair_texto_card_timeline,
    "aux-imagem.imagem": _extrair_texto_imagem,
    "aux-zoom.zoom": _extrair_texto_zoom,
    "principais.antes-depois": _extrair_texto_antes_depois,
    "principais.atividade-pratica": _extrair_texto_atividade_pratica,
    "principais.caixa-formula": _extrair_texto_caixa_formula,
    "principais.card-comparativo": _extrair_texto_card_comparativo,
     "principais.card-feedback": _extrair_texto_card_feedback,
     "principais.card-player": _extrair_texto_card_player,
    "principais.card-tematico": _extrair_texto_card_tematico,
    "principais.carrossel": _extrair_texto_carrossel,
     "principais.chave-resposta": _extrair_texto_chave_resposta,
     "principais.code-snippet": _extrair_texto_code_snippet,
    "principais.code-compiler": _extrair_texto_code_compiler,
    "principais.destaque-texto": _extrair_texto_destaque_texto,
    "principais.grupo-accordion": _extrair_texto_grupo_accordion,
    "principais.grupo-card-player": _extrair_texto_grupo_card_player,
    "principais.grupo-card": _extrair_texto_grupo_card,
    "principais.grupo-imagem": _extrair_texto_grupo_imagem,
      "principais.grupo-zoom": _extrair_texto_grupo_zoom,
    "principais.patterns-imagem": _extrair_texto_patterns_imagem,
     "principais.questao": _extrair_texto_questao,
    "principais.quote": _extrair_texto_quote,
    "principais.tab-destaque": _extrair_texto_tab_destaque,
     "principais.texto": _extrair_texto_texto,
    "principais.texto-com-background": _extrair_texto_texto_com_background,
    "principais.timeline": _extrair_texto_timeline,
    "principais.timeline-horizontal": _extrair_texto_timeline_horizontal,
    "principais.tipografia": _extrair_texto_tipografia,
    "principais.tipografia-modal": _extrair_texto_tipografia_modal,
    "principais.video": _extrair_texto_video,
     "principais.audio": _extrair_texto_audio
}