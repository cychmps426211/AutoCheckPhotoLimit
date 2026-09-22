import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from src.config import COLLABORATIVE_CONFIG_PATH

logger = logging.getLogger(__name__)


@dataclass
class CollaborativeTechnician:
    uno: int
    description: str = ""
    machine_ids: Set[str] = field(default_factory=set)
    fallback_names: Dict[str, str] = field(default_factory=dict)

    def matches(self, code_no: str) -> bool:
        """判斷機台代號是否屬於此協同維修師關注之機台"""
        return code_no in self.machine_ids

    def resolve_name(self, code_no: str, api_name: str) -> str:
        """優先使用後台回傳之機台名稱，若為空則回退至設定檔中的中文名稱"""
        cleaned_api_name = api_name.strip()
        if cleaned_api_name:
            return cleaned_api_name
        return self.fallback_names.get(code_no, "")


def load_collaborative_config(
    file_path: Optional[str] = None,
) -> List[CollaborativeTechnician]:
    """
    載入協同機台設定檔。
    若設定檔不存在或解析異常，安全回傳空清單並記錄日誌，不影響主查詢流程。
    """
    path_to_load = Path(file_path or COLLABORATIVE_CONFIG_PATH)

    if not path_to_load.is_file():
        logger.warning(f"協同機台設定檔不存在: {path_to_load}，略過協同機台查詢。")
        return []

    try:
        with open(path_to_load, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"讀取或解析協同機台設定檔失敗: {e}")
        return []

    technicians: List[CollaborativeTechnician] = []
    raw_technicians = data.get("collaborative_technicians", [])
    for entry in raw_technicians:
        try:
            uno = int(entry.get("uno"))
            desc = str(entry.get("description", "")).strip()
            machine_ids: Set[str] = set()
            fallback_names: Dict[str, str] = {}

            for m in entry.get("machines", []):
                m_id = str(m.get("id", "")).strip()
                m_name = str(m.get("name", "")).strip()
                if m_id:
                    machine_ids.add(m_id)
                    if m_name:
                        fallback_names[m_id] = m_name

            technicians.append(
                CollaborativeTechnician(
                    uno=uno,
                    description=desc,
                    machine_ids=machine_ids,
                    fallback_names=fallback_names,
                )
            )
        except Exception as e:
            logger.error(f"解析單筆協同維修師設定失敗: {entry}, 錯誤: {e}")
            continue

    return technicians
