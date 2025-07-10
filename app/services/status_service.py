import requests

# Substitua pelo ID do vídeo retornado na resposta anterior
video_id = "eadf5d2259364d6c8888c7272fe51c24"

# URL para verificar o status
status_url = f"https://api.heygen.com/v2/video/status/{video_id}"

# Cabeçalhos da solicitação
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "x-api-key": "ZjQ3NDhlOGQ0MDcyNDU5MGI0NGY4N2UwNWJiYTllZGUtMTczMzE1OTM2NA=="  # Substitua pela sua chave válida
}

# Fazer a solicitação para verificar o status
response = requests.get(status_url, headers=headers)

# Exibir o resultado
if response.status_code == 200:
    print("Status do vídeo:")
    print(response.json())
else:
    print(f"Erro ao verificar o status! Código: {response.status_code}")
    print("Detalhes do erro:", response.text)
