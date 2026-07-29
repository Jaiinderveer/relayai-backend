import threading
import time
from backend.services.caller_service import fetch_conversation_status, execute_pending_calls

AUTOMATION_THREAD = None

def _automation_loop(interval_seconds: int = 15):
    print(" [Automation Engine] Running...")
    while True:
        try:
            fetch_conversation_status()
            execute_pending_calls()
        except Exception as e:
            print(f" [Automation Engine] Error in background loop: {e}")
        time.sleep(interval_seconds)

def start_automation_engine():
    global AUTOMATION_THREAD
    if AUTOMATION_THREAD is None or not AUTOMATION_THREAD.is_alive():
        AUTOMATION_THREAD = threading.Thread(target=_automation_loop, daemon=True)
        AUTOMATION_THREAD.start()
        print(" [Automation Engine] Daemon thread started successfully.")