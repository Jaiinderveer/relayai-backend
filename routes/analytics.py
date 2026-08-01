from fastapi import APIRouter, HTTPException
from firebase.db_helper import get_dashboard_metrics
from models.schemas import ChatRequest
from core.config import gemini_client
import json
from google.genai import types
import traceback
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/")
def get_analytics():
    try:
        metrics = get_dashboard_metrics()
        return metrics
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))