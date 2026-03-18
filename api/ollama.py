from fastapi import APIRouter, HTTPException
from ai.ollama_service import OllamaService
from ai.ollama_client import OllamaClient

router = APIRouter(
    prefix="/ai/ollama", 
    tags=["ollama"]
    )

ollama_service = OllamaService()
ollama_client = OllamaClient(ollama_service)


@router.get("/health")
async def health_check():
    is_healthy = await ollama_service.health_check()

    if is_healthy:
        return {
            "status": "healthy",
            "model": ollama_service.model_name,
            "message": f"Ollama está activo con modelo {ollama_service.model_name}",
        }
    else:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama no está disponible en {ollama_service.base_url}",
        )


@router.post("/ask")
async def ask_model(body: dict):
    """
    Envía un prompt genérico al modelo.
    
    Body:
    {
        "prompt": "Pregunta o mensaje del usuario",
        "system_prompt": "Instrucción personalizada (opcional)",
        "temperature": 0.1 ,
        "num_predict": 256
    }
    """
    try:
        prompt = body.get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="'prompt' es requerido")

        result = await ollama_client.ask(
            question=prompt,
            system_prompt=body.get("system_prompt"),
            temperature=body.get("temperature"),
            num_predict=body.get("num_predict", 256),
        )
        return {"result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

