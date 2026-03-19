from fastapi import APIRouter, HTTPException
from ai.azure_openai_client import AzureOpenAIClient
from ai.azure_openai_service import AzureOpenAIService

router = APIRouter(
    prefix="/ai/azure-openai",
    tags=["azure-openai"],
)

azure_openai_service = AzureOpenAIService()
azure_openai_client = AzureOpenAIClient(azure_openai_service)


@router.get("/health")
async def health_check():
    is_healthy = await azure_openai_service.health_check()

    if is_healthy:
        return {
            "status": "healthy",
            "deployment": azure_openai_service.deployment_name,
            "api_version": azure_openai_service.api_version,
            "message": "Azure OpenAI esta disponible",
        }

    raise HTTPException(
        status_code=503,
        detail="Azure OpenAI no esta disponible o el deployment no responde",
    )


@router.post("/ask")
async def ask_model(body: dict):
    """
    Envia un prompt generico al deployment de Azure OpenAI.

    Body:
    {
        "prompt": "Pregunta o mensaje del usuario",
        "system_prompt": "Instruccion personalizada (opcional)",
        "temperature": 0.1,
        "max_tokens": 256,
        "top_p": 1.0
    }
    """
    try:
        prompt = body.get("prompt")
        if not prompt:
            raise HTTPException(status_code=400, detail="'prompt' es requerido")

        result = await azure_openai_client.ask(
            question=prompt,
            system_prompt=body.get("system_prompt"),
            temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens", 256),
            top_p=body.get("top_p"),
        )
        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
