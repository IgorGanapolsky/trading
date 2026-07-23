import json
from types import SimpleNamespace

import scripts.system_health_check as sh
from src.observability.llm_observability import LLMObservabilityReport


class _FakeTable:
    def __init__(self, row_count):
        self._row_count = row_count

    def count_rows(self):
        return self._row_count


class _FakeDb:
    def __init__(self, tables, row_count=1):
        self._tables = tables
        self._row_count = row_count

    def table_names(self):
        return self._tables

    def open_table(self, name):
        assert name == "document_aware_rag"
        return _FakeTable(self._row_count)


def test_probe_vector_index_reports_ready_without_loading_embeddings(monkeypatch, tmp_path):
    monkeypatch.setattr(sh, "LANCEDB_PATH", tmp_path)
    tmp_path.mkdir(exist_ok=True)

    fake_module = SimpleNamespace(connect=lambda _: _FakeDb(["document_aware_rag"], row_count=42))
    monkeypatch.setitem(__import__("sys").modules, "lancedb", fake_module)

    ok, detail = sh._probe_vector_index()

    assert ok is True
    assert "42 rows" in detail


def test_probe_vector_index_flags_missing_table(monkeypatch, tmp_path):
    monkeypatch.setattr(sh, "LANCEDB_PATH", tmp_path)
    tmp_path.mkdir(exist_ok=True)

    fake_module = SimpleNamespace(connect=lambda _: _FakeDb(["other_table"], row_count=0))
    monkeypatch.setitem(__import__("sys").modules, "lancedb", fake_module)

    ok, detail = sh._probe_vector_index()

    assert ok is False
    assert "document_aware_rag table missing" in detail


def test_probe_vector_index_flags_missing_path(monkeypatch, tmp_path):
    missing_path = tmp_path / "missing"
    monkeypatch.setattr(sh, "LANCEDB_PATH", missing_path)

    ok, detail = sh._probe_vector_index()

    assert ok is False
    assert str(missing_path) in detail


def test_check_vector_db_reports_broken_on_empty_index(monkeypatch):
    monkeypatch.setattr(
        sh, "_probe_vector_index", lambda: (False, "document_aware_rag table empty")
    )

    result = sh.check_vector_db()

    assert result["status"] == "BROKEN"
    assert any("table empty" in detail for detail in result["details"])


def test_check_vector_db_is_non_blocking_in_bounded_mode_for_missing_path(monkeypatch):
    monkeypatch.setattr(sh, "_probe_vector_index", lambda: (False, "LanceDB path missing: /tmp/foo"))
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_vector_db()

    assert result["status"] == "STUB"
    assert any("non-blocking in bounded CI mode" in detail for detail in result["details"])


def test_check_llm_observability_surfaces_warning_without_failing(monkeypatch):
    monkeypatch.setattr(
        sh,
        "build_llm_observability_report",
        lambda: LLMObservabilityReport(
            status="warning",
            summary="Gateway routing active; OpenRouter logs are subset-only.",
            primary_route="gateway",
            primary_base_url="https://gateway.example/v1",
            primary_base_host="gateway.example",
            fallback_base_host="openrouter.ai",
            openrouter_api_key_present=True,
            gateway_base_url_present=True,
            gateway_base_host="gateway.example",
            gateway_api_key_present=True,
            input_output_logging_declared=True,
            openrouter_private_logs_cover_primary=False,
            openrouter_private_logs_cover_fallback=True,
            critical_execution_provider="anthropic",
            critical_execution_covered_by_openrouter=False,
            warnings=("subset-only coverage",),
            notes=("critical execution outside OpenRouter logs",),
        ),
    )

    result = sh.check_llm_observability()

    assert result["status"] == "WARNING"
    assert any("subset-only" in detail for detail in result["details"])


def test_check_ml_pipeline_reports_ineligible_policy_as_stub(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    model_dir = tmp_path / "models" / "ml"
    runtime_dir = data_dir / "runtime"
    data_dir.mkdir()
    model_dir.mkdir(parents=True)
    runtime_dir.mkdir()
    (runtime_dir / "strategy_kill_switch.json").write_text(
        json.dumps({"active_family": "spy_put_credit"})
    )
    (data_dir / "trades.json").write_text(json.dumps({"trades": []}))
    (model_dir / "grpo_trade_metadata.json").write_text(
        json.dumps({"trades_trained_on": 159, "strategy_family": "iron_condor"})
    )

    result = sh.check_ml_pipeline()

    assert result["status"] == "STUB"
    assert any("quarantined" in detail for detail in result["details"])
    assert any("0/30" in detail for detail in result["details"])


def test_check_position_completeness_allows_long_only_defined_risk_structure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps(
            {
                "positions": [
                    {"symbol": "SPY260430C00700000", "qty": 2},
                    {"symbol": "SPY260430P00615000", "qty": 2},
                ]
            }
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: SimpleNamespace(clean=True, option_leg_count=2),
    )

    result = sh.check_position_completeness()

    assert result["status"] == "OK"
    assert any("Long-only defined-risk structure" in detail for detail in result["details"])


def test_check_position_completeness_blocks_unhedged_short_exposure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps(
            {
                "positions": [
                    {"symbol": "SPY260430P00620000", "qty": -1},
                    {"symbol": "SPY260430C00700000", "qty": 1},
                ]
            }
        )
    )

    result = sh.check_position_completeness()

    assert result["status"] == "BROKEN"
    assert any("Unhedged short exposure" in detail for detail in result["details"])
    assert any("long put hedge" in detail for detail in result["details"])


def test_check_position_completeness_accepts_protected_four_leg_structure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps(
            {
                "positions": [
                    {"symbol": "SPY260430P00610000", "qty": 1},
                    {"symbol": "SPY260430P00620000", "qty": -1},
                    {"symbol": "SPY260430C00690000", "qty": -1},
                    {"symbol": "SPY260430C00700000", "qty": 1},
                ]
            }
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: SimpleNamespace(clean=True, option_leg_count=4),
    )

    result = sh.check_position_completeness()

    assert result["status"] == "OK"
    assert any("Defined-risk put/call exposure" in detail for detail in result["details"])


def test_position_helpers_ignore_non_options_invalid_legs_and_zero_quantity():
    grouped = sh._positions_by_expiry(
        [
            {"symbol": "SPY", "qty": 10},
            {"symbol": "SPY260821P00700000", "qty": -1},
        ]
    )
    assert set(grouped) == {"260821"}

    counts = sh._expiry_side_counts(
        [
            {"symbol": "not-an-option", "qty": -1},
            {"symbol": "SPY260821P00700000", "qty": 0},
            {"symbol": "SPY260821C00781000", "qty": 1},
        ]
    )
    assert counts == {("C", "long"): 1}


def test_expiry_protection_covers_call_spread_and_missing_call_hedge():
    protected, details = sh._expiry_protection(
        "260821",
        [
            {"symbol": "SPY260821C00776000", "qty": -1},
            {"symbol": "SPY260821C00781000", "qty": 1},
        ],
    )
    assert protected is True
    assert any("Protected call-side spread" in detail for detail in details)

    protected, details = sh._expiry_protection(
        "260821",
        [{"symbol": "SPY260821C00776000", "qty": -1}],
    )
    assert protected is False
    assert any("long call hedge" in detail for detail in details)


def test_position_completeness_handles_missing_empty_and_invalid_state(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    missing = sh.check_position_completeness()
    assert missing["status"] == "BROKEN"
    assert any("not found" in detail for detail in missing["details"])

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    state_path = data_dir / "system_state.json"
    state_path.write_text(json.dumps({"positions": []}))
    empty = sh.check_position_completeness()
    assert empty["status"] == "OK"
    assert any("No open positions" in detail for detail in empty["details"])

    state_path.write_text("{invalid")
    invalid = sh.check_position_completeness()
    assert invalid["status"] == "BROKEN"
    assert any("Error:" in detail for detail in invalid["details"])


def _write_defined_risk_inventory_mismatch(root, *finding_codes):
    data_dir = root / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps(
            {
                "positions": [
                    {"symbol": "SPY260821P00703000", "qty": 1},
                    {"symbol": "SPY260821P00708000", "qty": -1},
                ]
            }
        )
    )
    codes = finding_codes or ("QTY_MISMATCH",)
    findings = []
    for code in codes:
        details = {"offenders": [{"right": "P", "strike": 708.0}]} if code == "LOT_SIZE_EXCEEDED" else {}
        findings.append(
            SimpleNamespace(
                code=code,
                severity="block",
                details=details,
            )
        )
    return SimpleNamespace(
        clean=False,
        option_leg_count=2,
        findings=findings,
        block_reasons=lambda: ["Expiry 260821 has journal quantity mismatch"],
    )


def test_bounded_health_accepts_only_canonical_controlled_inventory_halt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(tmp_path)
    (tmp_path / "data" / "TRADING_HALTED").write_text(
        "\n".join(
            [
                "INVENTORY RECONCILIATION REQUIRED",
                "Reason: broker inventory does not match journaled structures for SPY 2026-08-21",
                "Policy: new entries blocked; exits and risk reduction remain allowed",
            ]
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_position_completeness()

    assert result["status"] == "HALTED"
    assert any("canonical inventory halt" in detail for detail in result["details"])


def test_bounded_health_rejects_inventory_mismatch_without_valid_halt(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(tmp_path)
    (tmp_path / "data" / "TRADING_HALTED").write_text("generic halt")
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_position_completeness()

    assert result["status"] == "BROKEN"
    assert any("Controlled safety halt invalid" in detail for detail in result["details"])


def test_controlled_halt_requires_structured_findings_and_halt_file(tmp_path):
    no_findings = SimpleNamespace(findings=[])
    valid, detail = sh._controlled_inventory_halt(no_findings, root=tmp_path)
    assert valid is False
    assert "no structured blocking findings" in detail

    inventory = SimpleNamespace(
        findings=[
            SimpleNamespace(
                code="QTY_MISMATCH",
                severity="block",
                details={},
            )
        ]
    )
    valid, detail = sh._controlled_inventory_halt(inventory, root=tmp_path)
    assert valid is False
    assert "unavailable" in detail


def test_bounded_health_rejects_unrelated_inventory_blocker_with_canonical_halt(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(tmp_path, "TOO_MANY_EXPIRIES")
    (tmp_path / "data" / "TRADING_HALTED").write_text(
        "\n".join(
            [
                "INVENTORY RECONCILIATION REQUIRED",
                "Reason: broker inventory does not match journaled structures",
                "Policy: new entries blocked; exits and risk reduction remain allowed",
            ]
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_position_completeness()

    assert result["status"] == "BROKEN"
    assert any("TOO_MANY_EXPIRIES" in detail for detail in result["details"])


def test_bounded_health_rejects_mixed_reconciliation_and_policy_blockers(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(
        tmp_path,
        "QTY_MISMATCH",
        "JOURNAL_STRIKES_INCOMPLETE",
    )
    (tmp_path / "data" / "TRADING_HALTED").write_text(
        "\n".join(
            [
                "INVENTORY RECONCILIATION REQUIRED",
                "Reason: broker inventory does not match journaled structures",
                "Policy: new entries blocked; exits and risk reduction remain allowed",
            ]
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_position_completeness()

    assert result["status"] == "BROKEN"
    assert any("JOURNAL_STRIKES_INCOMPLETE" in detail for detail in result["details"])


def test_bounded_health_accepts_only_broker_lot_offenders(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(tmp_path, "LOT_SIZE_EXCEEDED")
    (tmp_path / "data" / "TRADING_HALTED").write_text(
        "\n".join(
            [
                "INVENTORY RECONCILIATION REQUIRED",
                "Reason: broker inventory does not match journaled structures",
                "Policy: new entries blocked; exits and risk reduction remain allowed",
            ]
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_position_completeness()

    assert result["status"] == "HALTED"


def test_bounded_health_rejects_journal_lot_policy_violation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(tmp_path)
    inventory.findings = [
        SimpleNamespace(
            code="LOT_SIZE_EXCEEDED",
            severity="block",
            details={"journal_key": "IC_260821", "quantity": 2},
        )
    ]
    (tmp_path / "data" / "TRADING_HALTED").write_text(
        "\n".join(
            [
                "INVENTORY RECONCILIATION REQUIRED",
                "Reason: broker inventory does not match journaled structures",
                "Policy: new entries blocked; exits and risk reduction remain allowed",
            ]
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )
    monkeypatch.setenv("SYSTEM_HEALTH_BOUNDED", "1")

    result = sh.check_position_completeness()

    assert result["status"] == "BROKEN"
    assert any("LOT_SIZE_EXCEEDED" in detail for detail in result["details"])


def test_live_health_keeps_controlled_inventory_halt_nonzero(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    inventory = _write_defined_risk_inventory_mismatch(tmp_path)
    (tmp_path / "data" / "TRADING_HALTED").write_text(
        "\n".join(
            [
                "INVENTORY RECONCILIATION REQUIRED",
                "Reason: broker inventory does not match journaled structures",
                "Policy: new entries blocked; exits and risk reduction remain allowed",
            ]
        )
    )
    monkeypatch.setattr(
        "src.risk.open_inventory_audit.audit_from_files",
        lambda _root: inventory,
    )

    result = sh.check_position_completeness()

    assert result["status"] == "BROKEN"
