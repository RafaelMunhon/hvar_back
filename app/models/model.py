from typing import List, Dict, Optional, Union, ClassVar
from pydantic import BaseModel

class CustomBaseModel(BaseModel):
    class Config:
       extra = "allow"

class Media(CustomBaseModel):
    id: Optional[int] = None
    url: Optional[str] = None
    name: Optional[str] = None
    mime: Optional[str] = None
    component: Optional[str] = None


class Card(CustomBaseModel):
    component: ClassVar[str] = "aux-card.card"
    titulo_card: Optional[str] = "Título"
    descricao_card: Optional[str] = None
    icone_card: Optional[str] = "Sem Icone"
    imagem: Optional[Media] = None
    imagem_sensivel: Optional[bool] = False
    creditos: Optional[str] = None
    texto_alternativo: Optional[str] = None
    variante_cor: Optional[str] = "default"


class ItemCarrossel(CustomBaseModel):
    component: ClassVar[str] = "aux-carrossel.item-carrossel"
    imagem: Optional[Media] = None
    imagem_sensivel: Optional[bool] = False
    legenda: Optional[str] = None
    titulo_texto: Optional[str] = None
    conteudo_texto: Optional[str] = None
    creditos: Optional[str] = None
    texto_alternativo: Optional[str] = None


class Alternativa(CustomBaseModel):
  component: ClassVar[str] = "aux-questao.alternativa"
  alternativa_resposta: Optional[str] = None
  imagem_sensivel: Optional[bool] = False
  creditos: Optional[str] = None
  legenda: Optional[str] = None
  texto_alternativo: Optional[str] = None
  imagem: Optional[Media] = None


class CardTimeline(CustomBaseModel):
    component: ClassVar[str] = "aux-card.card-timeline"
    label: Optional[str] = None
    titulo: Optional[str] = None
    subtitulo: Optional[str] = None
    descricao: Optional[str] = None
    imagem: Optional[Media] = None
    imagem_sensivel: Optional[bool] = False
    creditos: Optional[str] = None
    legenda: Optional[str] = None
    texto_alternativo: Optional[str] = None


class Imagem(CustomBaseModel):
    component: ClassVar[str] = "aux-imagem.imagem"
    imagem_sensivel: bool
    creditos: Optional[str] = None
    legenda: Optional[str] = None
    largura_maxima: Optional[int] = None
    altura_maxima: Optional[int] = None
    largura_maxima_mobile: Optional[int] = None
    altura_maxima_mobile: Optional[int] = None
    texto_alternativo: Optional[str] = None
    imagem: Media

class Zoom(CustomBaseModel):
    component: ClassVar[str] = "aux-zoom.zoom"  
    creditos: Optional[str] = None
    legenda: Optional[str] = None
    texto_alternativo: Optional[str] = None
    imagem: Media
    imagem_zoom: Media
    imagem_sensivel: bool

class AntesDepois(CustomBaseModel):
    component: ClassVar[str] = "principais.antes-depois" 
    imagem_esquerda: Optional[Media] = None
    imagem_direita: Optional[Media] = None
    imagem_sensivel_esquerda: bool
    imagem_sensivel_direita: bool
    texto_alternativo_esquerda: Optional[str] = None
    texto_alternativo_direita: Optional[str] = None
    creditos_direita: Optional[str] = None
    creditos_esquerda: Optional[str] = None
    descricao: Optional[str] = None
    formato: str = "paisagem"
    variante_cor: str = "dark"

class AtividadePratica(CustomBaseModel):
    component: ClassVar[str] = "principais.atividade-pratica"
    enunciado_atividade_pratica: str
    titulo_atividade_pratica: Optional[str] = None
    feedback_resposta: Optional[Card] = None
    conteudo_feedback: Optional[List[Dict]] = None
    ponto_retorno_id: Optional[str] = None

class CaixaFormula(CustomBaseModel):
    component: ClassVar[str] = "principais.caixa-formula"
    titulo: Optional[str] = ""
    legenda: Optional[str] = ""
    transcricao: Optional[str] = ""
    formula: str
    variante_cor: str = "default"


class CardComparativo(CustomBaseModel):
    component: ClassVar[str] = "principais.card-comparativo"
    card1: Card
    card2: Card
    icone: Optional[str] = None
    variante_cor: str = "default"

class CardFeedback(CustomBaseModel):
    component: ClassVar[str] = "principais.card-feedback"
    tipo: str
    card: Card

class CardPlayer(CustomBaseModel):
    component: ClassVar[str] = "principais.card-player"
    url_audio: str
    tipo: str = "podcast"
    titulo_card: Optional[str] = None
    descricao_card: Optional[str] = None
    icone_card: Optional[str] = "Mic"
    imagem: Optional[Media] = None
    imagem_sensivel: Optional[bool] = False
    creditos: Optional[str] = None
    texto_alternativo: Optional[str] = None


class CardTematico(CustomBaseModel):
    component: ClassVar[str] = "principais.card-tematico"
    titulo_card_tematico: str
    conteudo_card_tematico: str
    tipo: str
    imagem: Optional[Media] = None
    creditos: Optional[str] = None
    texto_alternativo: Optional[str] = None


class Carrossel(CustomBaseModel):
    component: ClassVar[str] = "principais.carrossel"
    itens_carrossel: List[ItemCarrossel]


class ChaveResposta(CustomBaseModel):
    component: ClassVar[str] = "principais.chave-resposta"
    conteudo_feedback: Optional[List[Dict]] = None

class CodeSnippet(CustomBaseModel):
    component: ClassVar[str] = "principais.code-snippet"
    snippet_codigo: str
    linguagem: str

class CodeCompiler(CustomBaseModel):
    component: ClassVar[str] = "principais.code-compiler"
    codigo_padrao: str
    linguagem: str


class DestaqueTexto(CustomBaseModel):
    component: ClassVar[str] = "principais.destaque-texto"
    conteudo: str
    variante_cor: str = "light"


class GrupoAccordion(CustomBaseModel):
    component: ClassVar[str] = "principais.grupo-accordion"
    accordions: List[Dict]
    variante_cor: str = "default"
    posicao: str = "abaixo"


class GrupoCardPlayer(CustomBaseModel):
    component: ClassVar[str] = "principais.grupo-card-player"
    cards: List[CardPlayer]
    tipo: str = "podcast"


class GrupoCard(CustomBaseModel):
    component: ClassVar[str] = "principais.grupo-card"
    tipo: str
    cards: List[Card]
    variante_cor: str = "default"

class GrupoImagem(CustomBaseModel):
    component: ClassVar[str] = "principais.grupo-imagem"
    formato: str = "full"
    imagens: List[Imagem]

class GrupoZoom(CustomBaseModel):
    component: ClassVar[str] = "principais.grupo-zoom"
    formato: str = "full"
    imagens: List[Zoom]
    
class PatternsImagem(CustomBaseModel):
    component: ClassVar[str] = "principais.patterns-imagem"
    texto: Optional[str] = None
    posicao_texto: str
    legenda: Optional[str] = None
    creditos: Optional[str] = None
    imagem_sensivel: bool
    largura_maxima: Optional[int] = None
    altura_maxima: Optional[int] = None
    largura_maxima_mobile: Optional[int] = None
    altura_maxima_mobile: Optional[int] = None
    imagem: Media
    texto_alternativo: Optional[str] = None


class Questao(CustomBaseModel):
    component: ClassVar[str] = "principais.questao"
    enunciado_questao: str
    alternativas: List[Alternativa]
    correta: str
    display: str = "texto"
    titulo_questao: Optional[str] = "Questão"
    imagem_sensivel: Optional[bool] = False
    creditos: Optional[str] = None
    legenda: Optional[str] = None
    texto_alternativo: Optional[str] = None
    imagem: Optional[Media] = None
    feedback_positivo: Optional[str] = None
    feedback_negativo: Optional[str] = None
    conteudo_feedback_positivo: Optional[List[Dict]] = None
    conteudo_feedback_negativo: Optional[List[Dict]] = None
    ponto_retorno_id: Optional[str] = None


class Quote(CustomBaseModel):
    component: ClassVar[str] = "principais.quote"
    texto: str
    autor: str
    imagem_quote: Optional[Media] = None
    imagem_sensivel: Optional[bool] = False
    texto_alternativo: Optional[str] = None
    variante_cor: str = "default"


class TabDestaque(CustomBaseModel):
  component: ClassVar[str] = "principais.tab-destaque"
  tabs: List[Dict]
  posicao: str = "abaixo"
  tipo: str = "padrao"


class Texto(CustomBaseModel):
    component: ClassVar[str] = "principais.texto"
    titulo: Optional[str] = None
    conteudo_texto: str

class TextoComBackground(CustomBaseModel):
    component: ClassVar[str] = "principais.texto-com-background"
    texto: str
    variante_cor: str = "light"

class Timeline(CustomBaseModel):
    component: ClassVar[str] = "principais.timeline"
    tipo: str
    cards_timeline: List[CardTimeline]

class TimelineHorizontal(CustomBaseModel):
    component: ClassVar[str] = "principais.timeline-horizontal"
    tipo: str
    cards_timeline: List[CardTimeline]

class Tipografia(CustomBaseModel):
     component: ClassVar[str] = "principais.tipografia"  
     id: int
     variante: str
     cor: str
     opacidade: str
     tamanho: str
     texto: str


class TipografiaModal(CustomBaseModel):
    component: ClassVar[str] = "principais.tipografia-modal"
    id: int
    variante: str
    cor: str
    opacidade: str
    tamanho: str
    texto: str
    modais: list


class Video(CustomBaseModel):
    component: ClassVar[str] = "principais.video"
    urlVideo: str


class Audio(CustomBaseModel):
    component: ClassVar[str] = "principais.audio"
    url_audio: str
    variante_cor: str = "light"

# Union Type for all Components
component: ClassVar[str] = Union[ # type: ignore
    AntesDepois,
    AtividadePratica,
    CaixaFormula,
    CardComparativo,
    CardFeedback,
    CardPlayer,
    CardTematico,
    Carrossel,
    ChaveResposta,
    CodeSnippet,
    CodeCompiler,
    DestaqueTexto,
    GrupoAccordion,
    GrupoCardPlayer,
    GrupoCard,
    GrupoImagem,
    GrupoZoom,
    PatternsImagem,
    Questao,
    Quote,
    TabDestaque,
    Texto,
    TextoComBackground,
    Timeline,
    TimelineHorizontal,
    TipografiaModal,
    Tipografia,
    Video,
    Audio,
    Card,
    ItemCarrossel,
    Alternativa,
    CardTimeline,
    Imagem,
    Zoom
]
