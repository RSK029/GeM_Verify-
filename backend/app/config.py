"""Application configuration. Everything tunable lives here."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = BASE_DIR / "data"
SPECIMEN_DIR = DATA_DIR / "specimen"
UPLOAD_DIR = BASE_DIR / "uploads"                          # never served statically
DB_PATH = BASE_DIR / "gemverify.db"


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class Settings:
    # --- paths (mirrored onto the settings object for convenience) --------
    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    SPECIMEN_DIR = SPECIMEN_DIR
    UPLOAD_DIR = UPLOAD_DIR
    DB_PATH = DB_PATH

    # --- app -------------------------------------------------------------
    APP_NAME = "GeMVerify"
    API_PREFIX = "/api"
    DEBUG = _env("GV_DEBUG", "1") == "1"

    # --- database --------------------------------------------------------
    DATABASE_URL = _env("GV_DATABASE_URL", f"sqlite:///{DB_PATH}")

    # --- auth ------------------------------------------------------------
    # Dev default only. Set GV_SECRET_KEY in any real deployment.
    SECRET_KEY = _env("GV_SECRET_KEY", "dev-only-insecure-key-change-me")
    JWT_ALGORITHM = "HS256"
    SESSION_COOKIE = "gv_session"
    SESSION_TTL_HOURS = 12

    # --- uploads ---------------------------------------------------------
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    ALLOWED_MIME = {"application/pdf"}
    PDF_MAGIC = b"%PDF-"

    # --- CORS ------------------------------------------------------------
    CORS_ORIGINS = [
        o.strip()
        for o in _env(
            "GV_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if o.strip()
    ]

    # --- verification thresholds ----------------------------------------
    # Similarity bands for cross-document comparison. Tunable; every verdict
    # in the system traces back to these four numbers.
    SIM_CONSISTENT = 0.90
    SIM_POTENTIAL = 0.70
    # Scoring weights for the overall bid score.
    WEIGHT_DOCUMENT = 0.5
    WEIGHT_CONSISTENCY = 0.5

    # Tender-level qualification thresholds (mirrors the specimen tender).
    MIN_TURNOVER_CR = 5.0
    MIN_EXPERIENCE_YEARS = 5
    MIN_LOCAL_CONTENT_PCT = 50

    # --- ollama ----------------------------------------------------------
    OLLAMA_URL = _env("GV_OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = _env("GV_OLLAMA_MODEL", "qwen2.5:7b-instruct")
    OLLAMA_TIMEOUT_S = float(_env("GV_OLLAMA_TIMEOUT", "120"))
    OLLAMA_ENABLED = _env("GV_OLLAMA_ENABLED", "1") == "1"


settings = Settings()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
