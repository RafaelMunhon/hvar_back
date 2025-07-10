import os
import pdoc

# Configurações
modules = ['app']  # Lista de módulos para documentar
output_dir = 'docs'  # Diretório de saída

# Cria o diretório de saída se não existir
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# Configura o pdoc
pdoc.render.configure(
    docformat='google',  # Formato do docstring (google, numpy, ou restructuredtext)
    template_directory=None,  # Usa o template padrão
    show_source=True  # Mostra o código fonte
)

# Gera a documentação
pdoc.pdoc(*modules, output_directory=output_dir) 