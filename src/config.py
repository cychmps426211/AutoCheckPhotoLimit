import os
from pathlib import Path
from dotenv import load_dotenv

# 優先載入專案根目錄的 .env 檔案
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

SEIWA_BASE_URL: str = os.getenv("SEIWA_BASE_URL", "https://dl02.seiwainc.com.tw").rstrip("/")
SEIWA_ACCOUNT: str = os.getenv("SEIWA_ACCOUNT", "")
SEIWA_PASSWORD: str = os.getenv("SEIWA_PASSWORD", "")
DEFAULT_TECHNICIAN_UNO: int = int(os.getenv("DEFAULT_TECHNICIAN_UNO", "91"))

LINE_CHANNEL_SECRET: str = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")

PORT: int = int(os.getenv("PORT", "8000"))

COLLABORATIVE_CONFIG_PATH: str = os.getenv(
    "COLLABORATIVE_CONFIG_PATH",
    str(Path(__file__).resolve().parent.parent / "config" / "collaborative_machines.json"),
)
