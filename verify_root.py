import asyncio
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from main import app

def test_root_metadata():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    
    print("Root Metadata:")
    print(data)
    
    assert data["status"] == "UP"
    assert "version" in data
    assert "services" in data
    assert data["services"]["risk_engine"] == "ACTIVE"
    
    print("\nSuccess: Root metadata verified.")

if __name__ == "__main__":
    test_root_metadata()
