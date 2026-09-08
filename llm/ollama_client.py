"""Local Ollama client wrapper."""
import requests

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="qwen2.5-coder:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def generate(self, prompt):
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "")
