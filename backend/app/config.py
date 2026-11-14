
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def parse_origins(value: str) -> list[str]:
    return [
        origin.strip()
        for origin in value.split(",")
        if origin.strip()
    ]


class Settings:
    def __init__(self):
        self.APP_NAME = os.getenv("APP_NAME", "MarkLens AI")
        self.APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
        self.APP_ENV = os.getenv("APP_ENV", "development")
        self.DEBUG = os.getenv("DEBUG", "true").lower() == "true"

        self.API_PREFIX = os.getenv("API_PREFIX", "/api/v1")

        self.DATABASE_URL = os.getenv("DATABASE_URL", "")

        self.QDRANT_URL = os.getenv("QDRANT_URL", "")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
        self.QDRANT_COLLECTION = os.getenv(
            "QDRANT_COLLECTION",
            "real_trademark_embeddings"
        )
        self.VECTOR_DIMENSION = int(
            os.getenv("VECTOR_DIMENSION", "512")
        )

        self.CLIP_MODEL_NAME = os.getenv(
            "CLIP_MODEL_NAME", "ViT-B-32"
        )
        self.CLIP_PRETRAINED = os.getenv(
            "CLIP_PRETRAINED", "laion2b_s34b_b79k"
        )

        self.MAX_UPLOAD_SIZE = int(
            os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024))
        )

        self.ALLOWED_IMAGE_TYPES = (
            "image/jpeg",
            "image/png",
            "image/webp",
        )

        self.CORS_ORIGINS = parse_origins(
            os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173"
            )
        )

        self.API_KEY = os.getenv("API_KEY", "")

    @property
    def cors_origins_list(self):
        return self.CORS_ORIGINS


settings = Settings()
