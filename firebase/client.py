import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using service account credentials
    or default application credentials.
    """
    if not firebase_admin._apps:
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
            print(" [Firebase] Admin SDK initialized with Service Account.")
        else:
            # Fallback to Google Application Default Credentials or env project ID
            project_id = os.getenv("FIREBASE_PROJECT_ID", "delegate-ai-2026")
            firebase_admin.initialize_app(options={"projectId": project_id})
            print(f" [Firebase] Admin SDK initialized with Project ID: {project_id}")

    return firestore.client()

# Singleton Firestore Client
db = initialize_firebase()