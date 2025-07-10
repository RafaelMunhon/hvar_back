import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'YDUQS Video Service'
copyright = '2024, YDUQS'
author = 'YDUQS Team'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
]

html_theme = 'sphinx_rtd_theme' 