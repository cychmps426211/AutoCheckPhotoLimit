import json
import logging
from pathlib import Path
from typing import Optional
import requests
import ddddocr

from src.config import SEIWA_BASE_URL, SEIWA_ACCOUNT, SEIWA_PASSWORD

logger = logging.getLogger(__name__)

SESSION_CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "session_cookie.json"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class SessionManager:
    """
    管理 Seiwa 後台會話與認證狀態。
    - 採用本地開源 ddddocr 離線辨識驗證碼（完全在記憶體 byte stream 執行，不存圖檔）
    - 支援 Session 保持與快取，逾期自動重試登入（最多 3 次）
    """

    def __init__(
        self,
        base_url: str = SEIWA_BASE_URL,
        account: str = SEIWA_ACCOUNT,
        password: str = SEIWA_PASSWORD,
        cache_file: Optional[Path] = SESSION_CACHE_FILE,
    ):
        self.base_url = base_url.rstrip("/")
        self.account = account
        self.password = password
        self.cache_file = cache_file
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._ocr: Optional[ddddocr.DdddOcr] = None

        self._load_cached_session()

    def _get_ocr(self) -> ddddocr.DdddOcr:
        """惰性加載 ddddocr 模型以節省初期開銷"""
        if self._ocr is None:
            self._ocr = ddddocr.DdddOcr(show_ad=False)
        return self._ocr

    def _load_cached_session(self) -> None:
        """載入上次保存的 PHPSESSID 快取"""
        if self.cache_file and self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text(encoding="utf-8"))
                phpsessid = data.get("PHPSESSID")
                if phpsessid:
                    self.session.cookies.set("PHPSESSID", phpsessid)
                    logger.info("已從快取檔案載入 PHPSESSID")
            except Exception as e:
                logger.warning(f"載入 Session 快取失敗: {e}")

    def _save_cached_session(self) -> None:
        """保存目前 Session 的 PHPSESSID"""
        if not self.cache_file:
            return
        phpsessid = self.session.cookies.get("PHPSESSID")
        if phpsessid:
            try:
                self.cache_file.write_text(
                    json.dumps({"PHPSESSID": phpsessid}, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception as e:
                logger.warning(f"寫入 Session 快取失敗: {e}")

    def is_session_valid(self) -> bool:
        """
        透過請求檢測目前 Session 是否有效。
        若後台回應 302 重定向到 500.html 或 login 頁面，表示會話已失效。
        """
        phpsessid = self.session.cookies.get("PHPSESSID")
        if not phpsessid:
            return False

        test_url = f"{self.base_url}/pc/Paper/PaperMachine.php?area=0&uno=91&s=2"
        try:
            resp = self.session.get(test_url, allow_redirects=False, timeout=8)
            # 後台未登入時會回傳 302 Found, location: ../Common/500.html
            if resp.status_code == 200:
                return True
            return False
        except Exception as e:
            logger.warning(f"驗證 Session 有效性時發生異常: {e}")
            return False

    def login(self, max_retries: int = 3) -> bool:
        """
        執行自動登入流程：
        1. 獲取驗證碼 byte stream
        2. 調用 ddddocr 本地辨識 4 位碼
        3. 發送登入請求至 LoginCheck.php
        4. 失敗則重試（最多 max_retries 次）
        """
        if not self.account or not self.password:
            raise ValueError("未配置 SEIWA_ACCOUNT 或 SEIWA_PASSWORD")

        ocr = self._get_ocr()
        vcode_url = f"{self.base_url}/utils/GetVCode.php"
        login_url = f"{self.base_url}/BLL/LoginCheck.php"

        for attempt in range(1, max_retries + 1):
            logger.info(f"正在嘗試登入 Seiwa 後台 (第 {attempt}/{max_retries} 次)...")
            try:
                # 1. 取得驗證碼（保持在記憶體 byte stream 中）
                vcode_resp = self.session.get(vcode_url, timeout=10)
                if vcode_resp.status_code != 200 or not vcode_resp.content:
                    logger.warning(f"獲取驗證碼失敗 (HTTP {vcode_resp.status_code})")
                    continue

                # 2. 本地離線 OCR 辨識
                captcha_code = ocr.classification(vcode_resp.content)
                captcha_code = str(captcha_code).strip()
                logger.info(f"驗證碼辨識結果: {captcha_code}")

                # 3. 發送登入驗證
                payload = {
                    "ACC": self.account,
                    "PWD": self.password,
                    "Auth": captcha_code,
                }
                headers = {
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": f"{self.base_url}/login/",
                }

                login_resp = self.session.post(
                    login_url,
                    data=payload,
                    headers=headers,
                    timeout=10,
                )

                if login_resp.status_code != 200:
                    logger.warning(f"登入請求返回異常代碼: {login_resp.status_code}")
                    continue

                try:
                    result = login_resp.json()
                except Exception:
                    logger.warning(f"登入回應非 JSON 格式: {login_resp.text}")
                    continue

                if result.get("err") == 0:
                    logger.info("Seiwa 後台登入成功！")
                    self._save_cached_session()
                    return True
                else:
                    err_msg = result.get("msg", "未知錯誤")
                    logger.warning(f"登入失敗 ({err_msg})，準備重試...")

            except Exception as e:
                logger.warning(f"登入過程中發生異常: {e}")

        raise RuntimeError(f"登入失敗：已達最大重試次數 ({max_retries})")

    def get_authenticated_session(self) -> requests.Session:
        """取得已驗證的 requests.Session 物件（過期則自動登入）"""
        if not self.is_session_valid():
            logger.info("目前 Session 無效或已過期，觸發自動登入...")
            self.login()
        return self.session
