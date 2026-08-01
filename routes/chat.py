from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest
from services.ai_service import agentic_save
import traceback
router = APIRouter(prefix="/api/chat", tags=["Agentic Chat"])

@router.post("/")
async def chat_with_agent(request: ChatRequest):
    try:
        # Convert Pydantic models to list of dicts for OpenAI
        input_list = [{"role": msg.role, "content": msg.content} for msg in request.input_list]
        
        response_text = agentic_save(input_list,mode = request.mode)
        return {"response": response_text}

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))