import os
import sys

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.insert(0, os.path.abspath('../..'))

project = 'YDUQS Video Service'
copyright = '2024, YDUQS'
author = 'YDUQS Team'

# Extensões do Sphinx
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
]

# Tema
html_theme = 'sphinx_rtd_theme'

# Configurações adicionais
templates_path = ['_templates']
exclude_patterns = []
html_static_path = ['_static']

# Configurações do autodoc
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__'
} 