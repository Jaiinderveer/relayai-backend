from fastapi import APIRouter, HTTPException
from firebase.db_helper import get_dashboard_metrics
from models.schemas import ChatRequest
from core.config import openai_client
import json

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/")
def get_analytics():
    try:
        metrics = get_dashboard_metrics()
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
def ask_analyst(request: ChatRequest):
    try:
        # 1. Deterministic Python execution: Fetch metrics safely without LLM tokens
        metrics = get_dashboard_metrics()
        metrics_json = json.dumps(metrics, indent=2)

        # 2. Strict Analytics System Prompt
        system_prompt = (
            "You are RelayAI's dedicated Analytics Agent.\n"
            "Your SOLE purpose is to answer questions about dashboard metrics, success rates, "
            "call history trends, and system performance.\n\n"
            "CRITICAL RULES:\n"
            "1. YOU MUST NEVER CREATE, UPDATE, OR DELETE TASKS.\n"
            "2. You cannot make calls or modify the database.\n"
            "3. Base your answers entirely on the provided real-time system metrics context.\n"
            "4. If the user asks you to perform an action outside of analytics, politely decline and remind them of your specific role.\n\n"
            f"CURRENT REAL-TIME METRICS CONTEXT:\n{metrics_json}"
        )

        # 3. Assemble message payload
        messages = [{"role": "system", "content": system_prompt}]
        for msg in request.input_list:
            messages.append({"role": msg.role, "content": msg.content})

        # 4. Single OpenAI Call (Minimizes API usage, prevents tool hallucination)
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0
        )

        return {"response": response.choices[0].message.content}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))