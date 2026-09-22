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

# 預設查詢設定 (全部狀態 s=0, 剩餘張數門檻 <= 20 張)
DEFAULT_QUERY_STATUS: int = int(os.getenv("DEFAULT_QUERY_STATUS", "0"))
DEFAULT_QUERY_THRESHOLD: int = int(os.getenv("DEFAULT_QUERY_THRESHOLD", "20"))

# 異常/排除過濾機台清單 (代號與名稱關鍵字)
EXCLUDED_MACHINE_IDS: set[str] = set(
    filter(None, [x.strip().upper() for x in os.getenv("EXCLUDED_MACHINE_IDS", "ABC158-ND").split(",")])
)
EXCLUDED_MACHINE_NAMES: set[str] = set(
    filter(None, [x.strip() for x in os.getenv("EXCLUDED_MACHINE_NAMES", "高雄職訓中心").split(",")])
)

