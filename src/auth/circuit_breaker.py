import time
from typing import Optional


class CircuitBreakerError(Exception):
    """後台登入連續失敗達門檻，熔斷保護已啟動"""
    pass


class CircuitBreaker:
    """
    熔斷保護器 (Circuit Breaker)
    - 監控後台登入連續失敗次數，達 failure_threshold (預設 3 次) 時啟動熔斷保護
    - 熔斷期間直接中斷請求 (Fast-Fail)，不進行網路連線，避免帳號鎖定與雪崩
    - 冷卻時間 cooldown_seconds (預設 60 秒) 過後進入半開狀態 (Half-Open)，允許單次試探 (Probe)
    - 試探成功則重置並恢復正常 (Closed)；失敗則重新進入熔斷冷卻 (Open)
    """

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_failures = 0
        self.last_failure_time: Optional[float] = None

    @property
    def is_open(self) -> bool:
        """判定熔斷保護是否處於開啟狀態"""
        if self.consecutive_failures < self.failure_threshold:
            return False

        if self.last_failure_time is not None:
            # 若冷卻時間已過，允許單次試探 (Half-Open)
            if time.time() - self.last_failure_time >= self.cooldown_seconds:
                return False

        return True

    def record_failure(self) -> None:
        """記錄一次失敗並更新失敗時間戳記"""
        self.consecutive_failures += 1
        self.last_failure_time = time.time()

    def record_success(self) -> None:
        """記錄成功並重置失敗狀態"""
        self.consecutive_failures = 0
        self.last_failure_time = None

    def reset(self) -> None:
        """手動重置熔斷器為正常關閉狀態"""
        self.record_success()
