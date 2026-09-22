import json
import pytest
from pathlib import Path
from src.crawler.collaborative_manager import (
    load_collaborative_config,
    CollaborativeTechnician,
)


def test_load_default_collaborative_config():
    """驗證預設設定檔 config/collaborative_machines.json 能正確解析出 uno=19 的 24 台機台"""
    technicians = load_collaborative_config()
    assert len(technicians) == 1

    tech19 = technicians[0]
    assert tech19.uno == 19
    assert tech19.description == "高雄協同支援機台"
    assert len(tech19.machine_ids) == 24

    # 驗證指定機台代號存在於集合中
    expected_sample_ids = [
        "ABC074-ND",
        "ABC079-ST",
        "ABC097-ND",
        "ABC152-ND",
        "ABC161-ND",
        "ABC173-ND",
        "ABC175-ND",
        "ABC185-ND",
        "ABC187-ST",
        "ABC188-ST",
        "ABC203-ND",
        "ABC215-ST",
        "ABC247-ST",
        "ABC322-ND",
        "ABC327-ST",
        "ABC336-ND",
        "ABC376-ST",
        "ABC383-ST",
        "ABC395-ST",
        "ABC401-ND",
        "ABC404-ST",
        "ABC409-ND",
        "ABC422-ND",
        "ABC686-AX",
    ]
    for m_id in expected_sample_ids:
        assert m_id in tech19.machine_ids
        assert m_id in tech19.fallback_names
        assert len(tech19.fallback_names[m_id]) > 0


def test_load_collaborative_config_missing_file(tmp_path):
    """驗證當設定檔路徑不存在時，安全回傳空清單而不中斷"""
    non_existent_file = tmp_path / "does_not_exist.json"
    result = load_collaborative_config(str(non_existent_file))
    assert result == []


def test_load_collaborative_config_invalid_json(tmp_path):
    """驗證當設定檔損毀非合法 JSON 時，安全回傳空清單"""
    bad_json_file = tmp_path / "bad.json"
    bad_json_file.write_text("{ broken json ...", encoding="utf-8")
    result = load_collaborative_config(str(bad_json_file))
    assert result == []


def test_load_collaborative_config_custom_file(tmp_path):
    """驗證自訂設定檔格式解析"""
    custom_file = tmp_path / "custom.json"
    content = {
        "collaborative_technicians": [
          {
            "uno": 88,
            "description": "測試協同",
            "machines": [
              {"id": "TEST01-AA", "name": "測試店 A"},
              {"id": "TEST02-BB", "name": "測試店 B"}
            ]
          }
        ]
    }
    custom_file.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")

    result = load_collaborative_config(str(custom_file))
    assert len(result) == 1
    assert result[0].uno == 88
    assert result[0].machine_ids == {"TEST01-AA", "TEST02-BB"}
    assert result[0].fallback_names["TEST01-AA"] == "測試店 A"
