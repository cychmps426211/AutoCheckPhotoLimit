from typing import List, Optional
from dataclasses import dataclass


@dataclass
class MachineStock:
    machine_id: str
    machine_name: str
    remaining_sheets: int
    status_text: str = ""


class MessageBuilder:
    """
    負責產出 Line 格式文字訊息
    遵循 CONTEXT.md 領域術語與緊急排序規則
    """

    @classmethod
    def build_stock_report(
        cls,
        uno: int,
        machines: List[MachineStock],
        threshold: Optional[int] = None,
    ) -> str:
        if not machines:
            if threshold is not None:
                return f"🎉 維修師 {uno} 目前負責之機台底片皆充足（無任何機台底片剩餘張數小於等於 {threshold} 張）！"
            return f"🎉 維修師 {uno} 目前所有機台底片存量充足（無接近底限機台）！"

        header_suffix = f"（剩餘張數 <= {threshold} 張）" if threshold is not None else "（接近底限）"
        lines = [
            f"⚠️ 【維修師 {uno} 機台底片存量警報】{header_suffix}",
            f"共找到 {len(machines)} 台機台需要注意（已依緊急程度由少至多排序）：",
            "",
        ]

        for idx, m in enumerate(machines, start=1):
            if m.remaining_sheets <= 10:
                icon = "🔴"
            elif m.remaining_sheets <= 30:
                icon = "🟠"
            else:
                icon = "🟡"

            # 顯示機台名稱與代號
            name_display = m.machine_name if m.machine_name else m.machine_id
            if m.machine_name and m.machine_id and m.machine_name != m.machine_id:
                name_display = f"{m.machine_name} ({m.machine_id})"

            lines.append(f"{idx}. {icon} {name_display}")
            lines.append(f"   剩餘張數：{m.remaining_sheets} 張")
            lines.append("")

        lines.append("💡 請現場維修師優先巡檢置頂機台補充底片。")
        return "\n".join(lines).strip()

    @classmethod
    def build_help_message(cls) -> str:
        return (
            "📖 【機台底片存量查詢指令說明】\n\n"
            "1. 預設查詢：\n"
            "   - 輸入「底片」或「檢查底片」\n"
            "   - 查詢預設維修師 (91) 接近底限之機台\n\n"
            "2. 門檻查詢：\n"
            "   - 輸入「底片 < 20」、「底片門檻 20」或「底片 20張」\n"
            "   - 查詢剩餘張數在門檻值以下的機台\n\n"
            "3. 指定維修師查詢：\n"
            "   - 輸入「底片 師 88」或「檢查底片維修師 88」\n"
            "   - 查詢指定維修師接近底限之機台\n\n"
            "4. 複合查詢：\n"
            "   - 輸入「底片 88 < 20」、「底片 88門檻 20」或「底片 88 20張」\n"
            "   - 查詢指定維修師且剩餘張數低於門檻之機台\n\n"
            "5. 教學說明：\n"
            "   - 輸入「說明」或「底片 說明」"
        )

    @classmethod
    def build_technician_not_found_message(cls, uno: int) -> str:
        return (
            f"ℹ️ 查無維修師 {uno} 負責之機台資料\n\n"
            "請確認維修師編號是否正確，或輸入「說明」查看查詢指令格式。"
        )

    @classmethod
    def build_unknown_message(cls, raw_text: str) -> str:
        return (
            f"❓ 無法辨識指令：「{raw_text}」\n\n"
            "您可以直接輸入「底片」查詢預設維修師 (91) 機台，或輸入「說明」查看所有指令格式。"
        )

    @classmethod
    def build_circuit_breaker_message(cls) -> str:
        return (
            "🚨 【後台連線異常（熔斷保護已啟動）】\n\n"
            "後台登入已連續失敗達 3 次，系統已自動啟動熔斷保護以維護帳號安全，暫停重複登入重試。\n\n"
            "💡 請稍候（約 1 分鐘後）再試，或聯絡系統管理員確認後台狀態與帳號密碼。"
        )

    @classmethod
    def build_error_message(cls, reason: str) -> str:
        return (
            "❌ 查詢失敗\n\n"
            f"原因：{reason}\n"
            "系統已記錄此異常，請稍候重試或聯絡管理員。"
        )
