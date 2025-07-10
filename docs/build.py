import os
import sys
from sphinx.cmd.build import main as sphinx_build

def build_docs():
    """Build the documentation using Sphinx"""
    try:
        # Certifica que estamos na pasta raiz do projeto
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(project_root)
        
        # Define os caminhos absolutos
        source_dir = os.path.join(project_root, 'docs', 'source')
        build_dir = os.path.join(project_root, 'docs', 'build')
        
        # Cria diretórios necessários
        os.makedirs(os.path.join(source_dir, '_templates'), exist_ok=True)
        os.makedirs(os.path.join(source_dir, '_static'), exist_ok=True)
        os.makedirs(os.path.join(source_dir, 'modules'), exist_ok=True)
        
        # Mapeamento de módulos para seus caminhos corretos
        modules = {
            'text_overlay_service': 'app.services.text_overlay_service',
            'speech_service': 'app.services.speech_service',
            'video_service': 'app.services.video_service',
            'audiobook_service': 'app.services.audiobook_service',
            'video': 'app.api.video',
            'cria_roteiro_prompt': 'app.common.criaRoteiroPrompt',
            'tratamento_json_matriz': 'app.common.tratamentoJsonMatriz',
            'ffmpeg_config': 'app.config.ffmpeg',
            'vertex_ai_config': 'app.config.vertexAi',
            'edicao_video': 'app.editandoVideo.edicao_video',
            'vertexai_service': 'app.services.vertexai_service'
        }
        
        # Gera a documentação dos módulos
        for module_name, module_path in modules.items():
            module_file = os.path.join(source_dir, 'modules', f'{module_name}.rst')
            with open(module_file, 'w', encoding='utf-8') as f:
                f.write(f'''
{module_name}
{'=' * len(module_name)}

.. automodule:: {module_path}
   :members:
   :undoc-members:
   :show-inheritance:
''')
        
        # Executa sphinx-build usando a API do Python
        sys.argv = [
            'sphinx-build',
            '-M',  # Usar o modo Makefile
            'html',  # builder
            source_dir,  # sourcedir
            build_dir,  # outputdir
            # '-W'  # Comentado: não tratar warnings como erros por enquanto
        ]
        
        result = sphinx_build(sys.argv[1:])
        
        if result == 0:
            print(f"Documentação gerada com sucesso em {build_dir}/html/")
        else:
            print(f"Erro ao gerar documentação. Código de retorno: {result}")
            
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    build_docs() 