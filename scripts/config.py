import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "sqlite:///data/jobmarket.db"
)

ADZUNA_APP_ID:  str = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY: str = os.getenv("ADZUNA_APP_KEY", "")

RAW_DIR:   Path = Path("data/raw")
CLEAN_DIR: Path = Path("data/clean")

RAW_DIR.mkdir(parents=True, exist_ok=True)
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
EMAIL_RECEIVER: str = os.getenv("EMAIL_RECEIVER", "")