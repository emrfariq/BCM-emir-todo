"""Konfigurasi lokal dari .env, hosting dari environment Vercel."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Environment yang sudah diset selalu menang atas isi file.
env_file = os.getenv("ENV_FILE", ".env")
env_path = BASE_DIR / env_file
if "ENV_FILE" in os.environ and not env_path.is_file():
    raise RuntimeError("ENV_FILE tidak ditemukan. Periksa nama file konfigurasi.")
load_dotenv(env_path)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("VERCEL") == "1"
    MAX_CONTENT_LENGTH = 64 * 1024
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "bcm_emir_todo")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
    DB_SSL_DISABLED = os.getenv("DB_SSL_DISABLED", "0") == "1"
    DB_SSL_CA = os.getenv("DB_SSL_CA", "")
    DB_SSL_VERIFY = os.getenv("DB_SSL_VERIFY", "0") == "1"


if os.getenv("VERCEL") == "1":
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "SECRET_KEY")
    if any(not os.getenv(name) for name in required):
        raise RuntimeError("Lengkapi konfigurasi database dan SECRET_KEY di Vercel.")
    if Config.DB_HOST in ("localhost", "127.0.0.1"):
        raise RuntimeError("Vercel memerlukan DB_HOST database online, bukan localhost.")
    if len(Config.SECRET_KEY) < 32 or Config.SECRET_KEY.startswith("local-demo"):
        raise RuntimeError("Gunakan SECRET_KEY acak baru untuk demo online.")
