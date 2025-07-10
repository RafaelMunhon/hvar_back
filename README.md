# Projeto - YDUQS.

## Ambiente Virtual

Para trabalhar no projeto, é necessário ativar o ambiente virtual. Siga os passos abaixo:

### Ativar o Ambiente Virtual

No Linux ou MacOS:
source .venv/bin/activate

No Windows:
.venv\Scripts\activate

### Desativar o Ambiente Virtual
Após concluir o trabalho, desative o ambiente virtual com o comando:

deactivate

### Instalação de Dependências
Certifique-se de que todas as dependências necessárias estão instaladas. Para isso, execute:

pip install --upgrade pip setuptools wheel

pip install -r requirements.txt --use-pep517

### Iniciar a Aplicação
Para iniciar a aplicação, utilize o comando:

python -m app.main
