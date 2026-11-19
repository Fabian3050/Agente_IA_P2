import os
import httpx
from pydantic import BaseModel
from typing import Optional, Dict, Any

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaRequest(BaseModel):
    model: str = "llama3.2"
    prompt: str
    stream: bool = False
    format: Optional[Any] = None
    options: Optional[Dict[str, Any]] = None


class OllamaResponse(BaseModel):
    response: str
    done: bool = True
    total_duration: Optional[int] = None


async def generate_text(req: OllamaRequest) -> OllamaResponse:
    default_options = {
        "temperature": 0.0,
        "num_ctx": 4096,
        "seed": 42
    }
    if req.options:
        default_options.update(req.options)

    # Preparar URLs candidatas con fallback inteligente
    base_url = OLLAMA_BASE_URL.rstrip('/')
    candidate_urls = [
        f"{base_url}/api/generate",
        "http://host.docker.internal:11434/api/generate",
        "http://ollama:11434/api/generate",
        "http://127.0.0.1:11434/api/generate",
        "http://localhost:11434/api/generate",
    ]

    # Eliminar duplicados preservando orden
    seen_urls = set()
    urls_to_try = []
    for u in candidate_urls:
        if u not in seen_urls:
            seen_urls.add(u)
            urls_to_try.append(u)

    # Modelos a intentar (fallback si el tag específico no existe en Ollama)
    models_to_try = [req.model]
    for alt in ["llama3.2", "llama3.2:latest", "llama3.2:3b-instruct-q4_K_M"]:
        if alt not in models_to_try:
            models_to_try.append(alt)

    last_error = None
    for attempt_url in urls_to_try:
        url_is_live = False
        for model_name in models_to_try:
            payload = {
                "model": model_name,
                "prompt": req.prompt,
                "stream": False,
                "options": default_options
            }
            if req.format is not None:
                payload["format"] = req.format

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(attempt_url, json=payload)
                    url_is_live = True
                    # Si el modelo no existe (404), probar siguiente modelo en el mismo servidor
                    if resp.status_code == 404:
                        last_error = f"Modelo '{model_name}' no encontrado en {attempt_url}"
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    return OllamaResponse(
                        response=data.get("response", ""),
                        done=data.get("done", True),
                        total_duration=data.get("total_duration")
                    )
            except httpx.ConnectError as ce:
                last_error = ce
                # Si falló la conexión al endpoint, no tiene sentido probar más modelos en esta URL
                break
            except Exception as e:
                last_error = e
                if not url_is_live:
                    break
                continue

    print(f"[MS2 Ollama] Error conectando con Ollama en {urls_to_try} (modelos {models_to_try}): {last_error}")
    raise Exception(f"Falla en inferencia Ollama: {last_error}")
