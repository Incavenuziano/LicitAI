import random
import string
from fastapi.testclient import TestClient
from backend.main import app
 
client = TestClient(app)
 
def generate_random_email():
    """Gera um email aleatório para evitar conflitos no teste."""
    random_part = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"testuser_{random_part}@example.com"

def test_create_user_successfully():
    """Testa se um usuário pode ser criado com sucesso com um email único."""
    email = generate_random_email()
    response = client.post(
        "/users/",
        json={"email": email, "password": "a_valid_password"},
    )
    # Verifica se a requisição foi bem-sucedida
    assert response.status_code == 200
    data = response.json()
    # Verifica se o email retornado é o mesmo que foi enviado
    assert data["email"] == email
    # Verifica se um ID foi atribuído
    assert "id" in data
    # Verifica se a senha não foi retornada
    assert "hashed_password" not in data
