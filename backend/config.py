import os
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    _backend_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(_backend_dir, ".env"))
    load_dotenv(os.path.join(os.path.dirname(_backend_dir), ".env"))
except Exception:
    pass


class Settings(BaseModel):
    APP_NAME: str = "VoxGuard AI"
    APP_VERSION: str = "1.0.0-SIH"
    TAGLINE: str = "Trust Every Voice"
    ENV: str = os.getenv("ENV", "development")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///backend/data/voxguard.db")

    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    FIREBASE_CLIENT_EMAIL: str = os.getenv("FIREBASE_CLIENT_EMAIL", "")
    FIREBASE_PRIVATE_KEY: str = os.getenv("FIREBASE_PRIVATE_KEY", "")

    BLOCKCHAIN_RPC_URL: str = os.getenv("BLOCKCHAIN_RPC_URL", "https://polygon-mumbai.g.alchemy.com/v2/demo")
    BLOCKCHAIN_CONTRACT_ADDRESS: str = os.getenv("BLOCKCHAIN_CONTRACT_ADDRESS", "0x8C3F001a91d26859841B98d97034b22Ae301b442")

    WEIGHT_VOICE_SYNTHETIC: float = 0.30
    WEIGHT_SPEAKER_ANOMALY: float = 0.18
    WEIGHT_PROSODY_ANOMALY: float = 0.10
    WEIGHT_CONVERSATION_RISK: float = 0.20
    WEIGHT_CALLER_RISK: float = 0.07
    WEIGHT_TRANSACTION_RISK: float = 0.15

    THRESHOLD_SAFE: int = 90
    THRESHOLD_CAUTION: int = 60
    THRESHOLD_HIGH_RISK: int = 30
    THRESHOLD_CRITICAL: int = 0


settings = Settings()
