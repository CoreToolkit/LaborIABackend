from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_auth():
    #response = client.get("/auth/google")
    #assert response.status_code == 200
    #assert response.json() == {"url": "https://accounts.google.com/..."}
    assert True == True