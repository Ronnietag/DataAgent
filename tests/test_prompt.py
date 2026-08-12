"""prompt 组装 / thinking 清理 / 历史压缩 / 规则冲突检测回归测试"""
import json

import server


def test_clean_think_removes_think_block():
    assert server._clean_think("abc<think>内部思考</think>def") == "abcdef"


def test_compact_history_keeps_user_questions():
    history = [
        {"role": "user", "content": "问 top10"},
        {"role": "assistant", "content": "```python\n很长的代码\n```",
         "result_summary": {"row_count": 10, "columns": ["a", "b"], "preview": [["1", "2"]]}},
        {"role": "user", "content": "再加个条件"},
    ]
    out = server._compact_history_for_llm(history)
    assert out[0]["content"] == "问 top10"
    assert out[2]["content"] == "再加个条件"


def test_compact_history_replaces_code_with_summary():
    history = [{
        "role": "assistant",
        "content": "```python\n这里是非常长的代码\n```",
        "result_summary": {"row_count": 10, "columns": ["a", "b"], "preview": [["1", "2"], ["3", "4"]]},
    }]
    out = server._compact_history_for_llm(history)
    assert "[上一轮已完成分析,代码略]" in out[0]["content"]
    assert "非常长的代码" not in out[0]["content"]
    assert "结果:10 行" in out[0]["content"]
    assert "a, b" in out[0]["content"]


def test_compact_history_trims_plain_assistant():
    history = [{"role": "assistant", "content": "x" * 1000}]
    out = server._compact_history_for_llm(history)
    assert len(out[0]["content"]) <= 500


def test_compact_history_skips_other_roles():
    history = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]
    out = server._compact_history_for_llm(history)
    assert len(out) == 1
    assert out[0]["role"] == "user"


def test_rules_prompt_includes_filters(tmp_path, monkeypatch):
    rules = {"filters": [{"name": "度量值过滤", "description": "必须先过滤学术接受度", "priority": "high"}]}
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "RULES_PATH", p)
    monkeypatch.setattr(server, "_business_rules", {})
    server.load_business_rules()
    prompt = server.build_rules_prompt()
    assert "度量值过滤" in prompt
    assert "必须先过滤学术接受度" in prompt
    monkeypatch.setattr(server, "_business_rules", {})


def test_detect_rule_conflicts(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_business_rules", {"field_preferences": {"preferred_grouping": {}}})
    habits = [
        {"key": "preferred_grouping", "value": "按代表"},
        {"key": "independent_habit", "value": "看柱状图"},
    ]
    conflicts = server._detect_rule_conflicts(habits)
    assert conflicts == {"preferred_grouping"}
    monkeypatch.setattr(server, "_business_rules", {})


def test_build_memory_prompt_shields_conflicted(tmp_path, monkeypatch):
    rules = {"field_preferences": {"preferred_grouping": {}}}
    rp = tmp_path / "rules.json"
    rp.write_text(json.dumps(rules, ensure_ascii=False), encoding="utf-8")
    mp = tmp_path / "memory.json"
    mp.write_text(json.dumps({"habits": [
        {"key": "preferred_grouping", "value": "按代表", "confidence": 0.9},
        {"key": "normal_habit", "value": "看柱状图", "confidence": 0.8},
    ]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(server, "RULES_PATH", rp)
    monkeypatch.setattr(server, "MEMORY_PATH", mp)
    monkeypatch.setattr(server, "_business_rules", {})
    server.load_business_rules()
    prompt = server.build_memory_prompt()
    assert "normal_habit" in prompt
    assert "preferred_grouping" not in prompt
    monkeypatch.setattr(server, "_business_rules", {})
