"""CAN-156 worker-policy 对齐的判定测试（照 Iris#208 参考测试移植）。

分组读取（claude_cli.dev / claude_cli.ci，顺序 == 回退顺序）、冷却时长
（5h，从 worker-policy.json 读，非写死）、模型冷却推进（pick_live_model）、
升级记录（字段/原因/24h 计数）。纯函数 + 注入依赖（record_dir=tmp_path、
monkeypatch _QUOTA_STATE_FILE），不碰真实 D:/Github/_ops/escalations 与
D:/Github/_ops/model_quota_cooldown.json，不读网络、不起 claude CLI。
"""
import datetime as dt
import json
import os
import pathlib

import dev_local as dl

TZ8 = dt.timezone(dt.timedelta(hours=8))

EXPECTED_DEV = ("kimi-k3", "deepseek-pro", "glm-5.2")
EXPECTED_CI = ("deepseek", "sensenova-lite", "sensenova-lite-global",
               "internlm-s2", "internlm-s1", "auto")

TEST_POLICY = {
    "claude_cli": {
        "cooldown_hours": 7,
        "dev": ["glm-5.2", "kimi-k3"],
        "ci": ["deepseek", "auto"],
    }
}


class TestGroupReading:
    """分组读取 —— 决定回退顺序的函数族，按 --role 分流（#156）。"""

    def test_dev_models_read_from_policy(self):
        assert dl.dev_models(TEST_POLICY) == ("glm-5.2", "kimi-k3")

    def test_ci_models_read_from_policy(self):
        assert dl.ci_models(TEST_POLICY) == ("deepseek", "auto")

    def test_group_order_is_fallback_order(self):
        """组顺序 == 回退顺序 —— 换模型的顺位由策略文件的数组顺序决定。"""
        assert list(dl.dev_models(TEST_POLICY)) == TEST_POLICY["claude_cli"]["dev"]

    def test_models_for_role_dev_returns_dev_group(self):
        assert dl.models_for_role("dev", TEST_POLICY) == ("glm-5.2", "kimi-k3")

    def test_models_for_role_ci_returns_ci_group(self):
        assert dl.models_for_role("ci", TEST_POLICY) == ("deepseek", "auto")

    def test_unknown_role_falls_back_to_dev(self):
        """默认（没传 --role）= dev —— 别让 typo 静默变成 CI 组。"""
        assert dl.models_for_role("whatever", TEST_POLICY) == dl.dev_models(TEST_POLICY)

    def test_missing_file_falls_back_to_builtin(self, tmp_path):
        p = tmp_path / "nope.json"
        assert dl.load_worker_policy(p) == {}
        assert dl.claude_cli_section(dl.load_worker_policy(p)) == dl.claude_cli_section({})

    def test_corrupt_json_treated_as_missing(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert dl.load_worker_policy(p) == {}

    def test_builtin_defaults_match_reference(self):
        """内置回退与 worker-policy.json 的 claude_cli 对齐（缺文件也能跑）。"""
        sec = dl.claude_cli_section({})
        assert tuple(sec["dev"]) == EXPECTED_DEV
        assert tuple(sec["ci"]) == EXPECTED_CI
        assert sec["cooldown_hours"] == 5

    def test_partial_policy_per_field_fallback(self):
        """缺字段回填默认、有字段用给的 —— 两组不会互相污染。"""
        partial = {"claude_cli": {"dev": ["glm-5.2"]}}
        sec = dl.claude_cli_section(partial)
        assert sec["dev"] == ["glm-5.2"]
        assert tuple(sec["ci"]) == EXPECTED_CI

    def test_policy_default_path_constant(self):
        """默认策略路径写死在一处，MNESIS_WORKER_POLICY 可覆盖（#156）。"""
        if os.environ.get("MNESIS_WORKER_POLICY"):
            assert str(dl._POLICY_FILE) == os.environ["MNESIS_WORKER_POLICY"]
        else:
            norm = str(dl._POLICY_FILE).replace("\\", "/")
            assert norm.endswith("Parthenon/cockpit/data/worker-policy.json")


class TestCooldown:
    """冷却时长（#156：5h 窗口是修正后的规格，旧 4.5h 写死已废）。"""

    def test_default_is_5h_from_policy(self):
        """默认 5h —— **不是** 4.5h；4.5h 是已被 Muso 决策取代的旧数。"""
        assert dl.cooldown_seconds({}) == 5 * 3600
        assert dl.cooldown_seconds({}) != 4.5 * 3600

    def test_reads_policy_cooldown_hours(self):
        assert dl.cooldown_seconds(TEST_POLICY) == 7 * 3600

    def test_not_hardcoded_4_5h(self):
        """别把 4.5h 写死回来 —— 这正是 #156 要替换的旧默认。"""
        assert dl.cooldown_seconds({}) != 4.5 * 3600

    def test_hook_overrides_policy_window(self, monkeypatch):
        """_QUOTA_COOLDOWN_S 是唯一允许覆盖冷却窗的钩子（tests 用）。"""
        monkeypatch.setattr(dl, "_QUOTA_COOLDOWN_S", 60.0)
        assert dl._cooldown_s() == 60.0

    def test_hook_default_is_policy_driven_not_hardcoded(self):
        """模块加载后钩子必须是 None —— 冷却时长以策略文件为准。"""
        assert dl._QUOTA_COOLDOWN_S is None

    def test_mark_then_expired_flips_to_not_cooling(self, tmp_path, monkeypatch):
        """已知时刻 + 已知窗口 = 确定性判冷却：过窗即解冻（不赌真实时钟）。"""
        monkeypatch.setattr(dl, "_QUOTA_STATE_FILE", tmp_path / "cd.json")
        monkeypatch.setattr(dl, "_QUOTA_COOLDOWN_S", 60.0)
        dl._mark_quota_exhausted("kimi-k3")
        assert dl.model_in_cooldown("kimi-k3")[0] is True
        st = json.loads((tmp_path / "cd.json").read_text(encoding="utf-8"))
        st["kimi-k3"] -= 61
        (tmp_path / "cd.json").write_text(json.dumps(st), encoding="utf-8")
        assert dl.model_in_cooldown("kimi-k3")[0] is False

    def test_policy_window_used_when_no_hook(self, tmp_path, monkeypatch):
        """没挂钩子时走策略文件的 5h 窗 —— 新鲜标记必在窗内。"""
        monkeypatch.setattr(dl, "_QUOTA_STATE_FILE", tmp_path / "cd.json")
        monkeypatch.setattr(dl, "_QUOTA_COOLDOWN_S", None)
        dl._mark_quota_exhausted("kimi-k3")
        assert dl.model_in_cooldown("kimi-k3")[0] is True


class TestQuotaMarkers:
    """额度耗尽的指纹 —— 撞上就换模型记冷却，绝不重试烧 attempt。"""

    def test_quota_markers_detected(self):
        assert dl.is_quota_exhausted("API Error: HTTP 429 rate_limit_error")
        assert dl.is_quota_exhausted('{"error":{"code":"insufficient_quota"}}')
        assert dl.is_quota_exhausted("entitlement exhausted")
        assert not dl.is_quota_exhausted("everything works")

    def test_model_unavailable_marker_still_wired(self):
        assert dl.is_model_unavailable(
            "There's an issue with the selected model (auto). It may not exist")


class TestPickLiveModel:
    """冷却推进 —— 沿组顺位换模型；整组冷却原样返回（上层停，exit 10）。"""

    @staticmethod
    def _iso(tmp_path, monkeypatch):
        monkeypatch.setattr(dl, "_QUOTA_STATE_FILE", tmp_path / "cd.json")
        monkeypatch.setattr(dl, "_QUOTA_COOLDOWN_S", None)

    def test_prefers_first_when_nothing_cooling(self, tmp_path, monkeypatch):
        self._iso(tmp_path, monkeypatch)
        picked, _ = dl.pick_live_model("kimi-k3", EXPECTED_DEV)
        assert picked == "kimi-k3"

    def test_skips_cooling_models_in_order(self, tmp_path, monkeypatch):
        self._iso(tmp_path, monkeypatch)
        dl._mark_quota_exhausted("kimi-k3")
        picked, why = dl.pick_live_model("kimi-k3", EXPECTED_DEV)
        assert picked == "deepseek-pro"
        assert "kimi-k3" in why  # 换模型必须被说出来，不许静默（#234）

    def test_all_cooling_returns_preferred_for_escalation(self, tmp_path, monkeypatch):
        """整组冷却 → 原样返回 preferred（上层据此写升级记录 exit 10）。"""
        self._iso(tmp_path, monkeypatch)
        for m in EXPECTED_DEV:
            dl._mark_quota_exhausted(m)
        picked, why = dl.pick_live_model("kimi-k3", EXPECTED_DEV)
        assert picked == "kimi-k3"
        assert "全部候选不可用" in why

    def test_never_returns_model_from_other_group(self, tmp_path, monkeypatch):
        """绝不用另一组模型硬做 —— #156 第一原则。"""
        self._iso(tmp_path, monkeypatch)
        for m in EXPECTED_DEV:
            dl._mark_quota_exhausted(m)
        picked, _ = dl.pick_live_model("kimi-k3", EXPECTED_DEV)
        assert picked in EXPECTED_DEV
        assert picked not in EXPECTED_CI

    def test_skip_set_works_without_state_file(self, tmp_path, monkeypatch):
        """skip 不依赖 state 文件 —— _save 吞异常时也不能原地打转。"""
        self._iso(tmp_path, monkeypatch)
        picked, _ = dl.pick_live_model("kimi-k3", EXPECTED_DEV, skip=("kimi-k3",))
        assert picked == "deepseek-pro"


class TestEscalate:
    """升级记录：字段齐全、24h 同任务计数、只落注入的临时目录。"""

    def test_writes_record_with_required_fields(self, tmp_path):
        at = dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8)
        rd = pathlib.Path("/run")
        path = dl.escalate("CAN-156", "/work", 5, rd, "acceptance failed",
                           at=at, record_dir=tmp_path)
        assert path.is_file()
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert rec["task"] == "CAN-156"
        assert rec["cli"] == "claude"
        assert rec["role"] == "dev"
        assert rec["cwd"] == "/work"
        assert rec["exit_code"] == 5
        assert rec["reason"] == "验收未过（pytest 红）—— 看 detail 的 acceptance_fail"
        assert rec["detail"] == "acceptance failed"
        assert rec["rundir"] == str(rd)
        assert rec["at"] == at.isoformat()
        assert rec["failures_24h_for_task"] == 1
        assert rec["resolved"] is False

    def test_filename_format(self, tmp_path):
        at = dt.datetime(2026, 1, 15, 12, 3, 4, tzinfo=TZ8)
        path = dl.escalate("CAN-156", "/w", 5, pathlib.Path("/r"), "",
                           at=at, record_dir=tmp_path)
        assert path.name == "CAN-156-0115-120304.json"

    def test_role_field_recorded(self, tmp_path):
        at = dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8)
        path = dl.escalate("CAN-156", "/w", 10, pathlib.Path("/r"), "",
                           role="ci", at=at, record_dir=tmp_path)
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert rec["role"] == "ci"

    def test_quota_reason_for_exit_10(self, tmp_path):
        at = dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8)
        path = dl.escalate("CAN-156", "/w", 10, pathlib.Path("/r"), "quota",
                           at=at, record_dir=tmp_path)
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert rec["reason"] == "网关后端故障或开发组模型全部冷却（交编排侧接管）"

    def test_unknown_code_reason(self, tmp_path):
        at = dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8)
        path = dl.escalate("CAN-156", "/w", 99, pathlib.Path("/r"), "",
                           at=at, record_dir=tmp_path)
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert rec["reason"] == "exit 99"

    def test_detail_truncated_to_500(self, tmp_path):
        at = dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8)
        path = dl.escalate("CAN-156", "/w", 4, pathlib.Path("/r"), "x" * 600,
                           at=at, record_dir=tmp_path)
        rec = json.loads(path.read_text(encoding="utf-8"))
        assert len(rec["detail"]) == 500

    def test_counts_failures_within_24h(self, tmp_path):
        """第 2、3 条必须读到前面几条 —— 派单 root 靠它做 24h 聚合升级。"""
        p1 = dl.escalate("CAN-156", "/w", 6, pathlib.Path("/r"), "",
                         at=dt.datetime(2026, 1, 15, 11, 0, tzinfo=TZ8),
                         record_dir=tmp_path)
        p2 = dl.escalate("CAN-156", "/w", 6, pathlib.Path("/r"), "",
                         at=dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8),
                         record_dir=tmp_path)
        p3 = dl.escalate("CAN-156", "/w", 6, pathlib.Path("/r"), "",
                         at=dt.datetime(2026, 1, 15, 13, 0, tzinfo=TZ8),
                         record_dir=tmp_path)
        r1 = json.loads(p1.read_text(encoding="utf-8"))
        r2 = json.loads(p2.read_text(encoding="utf-8"))
        r3 = json.loads(p3.read_text(encoding="utf-8"))
        assert (r1["failures_24h_for_task"],
                r2["failures_24h_for_task"],
                r3["failures_24h_for_task"]) == (1, 2, 3)

    def test_old_records_not_counted(self, tmp_path):
        dl.escalate("CAN-156", "/w", 6, pathlib.Path("/r"), "",
                    at=dt.datetime(2026, 1, 13, 12, 0, tzinfo=TZ8),
                    record_dir=tmp_path)
        p = dl.escalate("CAN-156", "/w", 6, pathlib.Path("/r"), "",
                        at=dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8),
                        record_dir=tmp_path)
        rec = json.loads(p.read_text(encoding="utf-8"))
        assert rec["failures_24h_for_task"] == 1  # 48h 前的不计

    def test_counts_only_same_task(self, tmp_path):
        dl.escalate("CAN-156", "/w", 6, pathlib.Path("/r"), "",
                    at=dt.datetime(2026, 1, 15, 11, 0, tzinfo=TZ8),
                    record_dir=tmp_path)
        p = dl.escalate("CAN-777", "/w", 6, pathlib.Path("/r"), "",
                        at=dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8),
                        record_dir=tmp_path)
        rec = json.loads(p.read_text(encoding="utf-8"))
        assert rec["failures_24h_for_task"] == 1  # 别的卡不掺和

    def test_never_writes_real_escalation_dir(self, tmp_path):
        """注入 record_dir 后，真实 escalations 目录一个文件都不许多出来。"""
        real = pathlib.Path("D:/Github/_ops/escalations")

        def snap():
            if real.is_dir():
                return {p.name for p in real.glob("*.json")}
            return set()

        before = snap()
        at = dt.datetime(2026, 1, 15, 12, 0, tzinfo=TZ8)
        dl.escalate("CAN-156", "/w", 1, pathlib.Path("/r"), "",
                    at=at, record_dir=tmp_path)
        assert snap() == before
        assert list(tmp_path.glob("CAN-156-*.json"))  # 产物确实进了 tmp

    def test_escalation_dir_default_or_env_override(self):
        """默认 D:/Github/_ops/escalations，MNESIS_ESCALATION_DIR 可覆盖。"""
        if os.environ.get("MNESIS_ESCALATION_DIR"):
            assert str(dl.ESCALATION_DIR) == os.environ["MNESIS_ESCALATION_DIR"]
        else:
            assert dl.ESCALATION_DIR.name == "escalations"
