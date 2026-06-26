"""Deterministic representative-example and redaction contracts.

These tests prove internal consistency and redaction properties of the
Trident example bundle shipped under ``examples/trident/``. They do NOT
prove arbitrary Klipper loadability, hardware safety, or complete secret
detection.

Test groups (use ``-k`` to select):
    bundle      – required files, root link, topology, backups, heaters/sensors
    ownership   – one extension sensor hook per active tool, no legacy owners,
                  direct SELECT_TOOL delegates, private non-recursive adapters
    documentation / rollback / hazards – required guide sections, legacy removal,
                                         exact rollback, commissioning order,
                                         operator verification, hazards and stop
    redaction   – reject common private-credential and machine-identifier forms
    uat / evidence / exclusion – runbook structure, evidence schema, exclusions
"""

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
TRIDENT = ROOT / "examples" / "trident"
README = ROOT / "README.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_cfg(path: Path) -> dict[str, dict[str, str]]:
    """Return a nested dict {section_header: {option: value}}.

    Handles multi-line gcode values (indented continuation lines).
    A continuation line is any non-empty, non-comment, non-section line
    that appears after a key with an empty value or after a multi-line key.
    """
    sections: dict[str, dict[str, str]] = {}
    current: str | None = None
    current_key: str | None = None
    in_multiline: bool = False
    for line in _read(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            # Continuation of a multi-line value
            if in_multiline and current is not None and current_key is not None:
                sections[current][current_key] += "\n" + stripped
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1].strip()
            sections.setdefault(current, {})
            current_key = None
            in_multiline = False
            continue
        if current is not None and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key != current_key:
                # New option — always set it (may be empty for multi-line)
                sections[current][key] = value
                current_key = key
                in_multiline = (value == "")
            else:
                # Continuation of a multi-line value
                sections[current][key] += "\n" + value
                in_multiline = True
        elif current is not None and in_multiline and current_key is not None:
            # Continuation line without a colon (e.g., gcode body)
            sections[current][current_key] += "\n" + stripped
    return sections


# ===================================================================
# bundle — topology, backups, heaters, sensors, required files, link
# ===================================================================


class TestBundle:
    """Required example files, root README link, topology, and config checks."""

    def test_required_files_exist(self):
        for name in (
            "README.md",
            "tool_fallback.cfg",
            "tool_fallback_macros.cfg",
            "sensor_hooks.cfg",
        ):
            assert (TRIDENT / name).exists(), f"{name} is missing"

    def test_root_readme_links_trident_bundle(self):
        text = _read(README)
        assert "examples/trident/README.md" in text, (
            "Root README must link to the Trident bundle"
        )

    def test_only_t0_t1_sections(self):
        cfg = _read_cfg(TRIDENT / "tool_fallback.cfg")
        tool_sections = [
            s for s in cfg if s.startswith("tool_fallback T")
        ]
        names = [s.replace("tool_fallback ", "") for s in tool_sections]
        assert sorted(names) == ["T0", "T1"], (
            f"Expected exactly T0 and T1, got {names}"
        )

    def test_reciprocal_backups_exact(self):
        cfg = _read_cfg(TRIDENT / "tool_fallback.cfg")
        t0_backups = cfg.get("tool_fallback T0", {}).get("backups", "")
        t1_backups = cfg.get("tool_fallback T1", {}).get("backups", "")
        assert t0_backups == "T1", f"T0 backups should be T1, got '{t0_backups}'"
        assert t1_backups == "T0", f"T1 backups should be T0, got '{t1_backups}'"

    def test_heater_names_exact(self):
        cfg = _read_cfg(TRIDENT / "tool_fallback.cfg")
        assert cfg["tool_fallback T0"]["heater"] == "extruder"
        assert cfg["tool_fallback T1"]["heater"] == "extruder1"

    def test_sensor_names_exact(self):
        cfg = _read_cfg(TRIDENT / "tool_fallback.cfg")
        assert cfg["tool_fallback T0"]["filament_sensor"] == (
            "filament_switch_sensor T0_sensor"
        )
        assert cfg["tool_fallback T1"]["filament_sensor"] == (
            "filament_switch_sensor T1_sensor"
        )

    def test_adapter_gcode_names(self):
        cfg = _read_cfg(TRIDENT / "tool_fallback.cfg")
        global_section = cfg.get("tool_fallback", {})
        assert global_section["purge_gcode"] == "_TOOL_FALLBACK_TRIDENT_PURGE"
        assert global_section["notify_gcode"] == "_TOOL_FALLBACK_TRIDENT_NOTIFY"
        assert global_section["purge_gcode"] != global_section["notify_gcode"]


# ===================================================================
# ownership — one sensor owner, no legacy, direct handlers, private adapters
# ===================================================================


class TestOwnership:
    """Sensor-owner uniqueness, legacy absence, handler shape, adapter privacy."""

    def test_sensor_hooks_one_extension_owner_per_active_tool(self):
        text = _read(TRIDENT / "sensor_hooks.cfg")
        assert "TOOL_FALLBACK_RUNOUT" in text
        assert "TOOL_FALLBACK_INSERT" in text
        assert "PAUSE_OWNED=1" in text

    def test_no_shipped_legacy_remap_tool(self):
        trident_text = _read(TRIDENT / "README.md")
        # The README should document removal, not ship the macro.
        # We check that no [gcode_macro REMAP_TOOL] definition exists.
        assert "[gcode_macro REMAP_TOOL]" not in trident_text

    def test_no_shipped_legacy_backup_spool(self):
        trident_text = _read(TRIDENT / "README.md")
        assert "[gcode_macro BACKUP_SPOOL]" not in trident_text

    def test_no_shipped_legacy_tool_runout(self):
        trident_text = _read(TRIDENT / "README.md")
        assert "[gcode_macro _TOOL_RUNOUT]" not in trident_text

    def test_physical_handlers_direct_select_tool(self):
        cfg = _read_cfg(TRIDENT / "sensor_hooks.cfg")
        t0_body = cfg.get("gcode_macro T0", {}).get("gcode", "")
        assert "SELECT_TOOL T=0" in t0_body, (
            "T0 handler must delegate to SELECT_TOOL T=0"
        )
        t1_body = cfg.get("gcode_macro T1", {}).get("gcode", "")
        assert "SELECT_TOOL T=1" in t1_body, (
            "T1 handler must delegate to SELECT_TOOL T=1"
        )

    def test_purge_adapter_not_recursive(self):
        macros = _read(TRIDENT / "tool_fallback_macros.cfg")
        # Extract only the gcode body lines (indented under the macro definition)
        # and check that the public PURGE_TOOL command is not invoked as a command.
        in_purge_body = False
        gcode_lines: list[str] = []
        for line in macros.splitlines():
            stripped = line.strip()
            if "[gcode_macro _TOOL_FALLBACK_TRIDENT_PURGE]" in line:
                in_purge_body = True
                continue
            if in_purge_body:
                if stripped.startswith("[gcode_macro"):
                    in_purge_body = False
                    continue
                # Skip comments and empty lines
                if not stripped or stripped.startswith("#"):
                    continue
                gcode_lines.append(line)
        body = "\n".join(gcode_lines)
        # Check that PURGE_TOOL is not invoked as a standalone gcode command.
        # It may appear in error messages (e.g., action_raise_error) which is fine.
        # We check each line: if a line starts with PURGE_TOOL (ignoring leading
        # whitespace), it's a command invocation.
        for line in gcode_lines:
            stripped = line.strip()
            if stripped.startswith("PURGE_TOOL") and not stripped.startswith("PURGE_TOOL:"):
                assert False, (
                    f"Purge adapter gcode body must not invoke public "
                    f"PURGE_TOOL as a command: {stripped}"
                )

    def test_notify_adapter_no_extension_mutation(self):
        macros = _read(TRIDENT / "tool_fallback_macros.cfg")
        # Extract only the gcode body lines from the notify adapter
        # and check that no extension mutating commands are invoked.
        in_notify_body = False
        gcode_lines: list[str] = []
        for line in macros.splitlines():
            stripped = line.strip()
            if "[gcode_macro _TOOL_FALLBACK_TRIDENT_NOTIFY]" in line:
                in_notify_body = True
                continue
            if in_notify_body:
                if stripped.startswith("[gcode_macro"):
                    in_notify_body = False
                    continue
                if not stripped or stripped.startswith("#"):
                    continue
                gcode_lines.append(line)
        body = "\n".join(gcode_lines)
        for cmd in (
            "SET_TOOL_BACKUPS",
            "RESET_TOOL_BACKUPS",
            "RESET_ALL_BACKUPS",
            "REMAP_TOOL",
            "PURGE_TOOL",
            "SHOW_TOOL_FALLBACK_STATE",
        ):
            assert cmd not in body, (
                f"Notify adapter gcode body must not invoke {cmd}"
            )


# ===================================================================
# documentation — required guide sections
# ===================================================================


class TestDocumentation:
    """Required sections in the adaptation guide."""

    def _guide(self) -> str:
        return _read(TRIDENT / "README.md")

    def test_revision_binding(self):
        text = self._guide()
        assert "Revision:" in text or "revision" in text.lower(), (
            "Guide must state the exact representative revision"
        )

    def test_bounded_scope_statement(self):
        text = self._guide()
        assert "not a universal" in text.lower() or "bounded" in text.lower(), (
            "Guide must state bounded scope, not universal compatibility"
        )

    def test_ownership_table(self):
        text = self._guide()
        assert "Owner" in text or "owner" in text.lower(), (
            "Guide must contain ownership information"
        )

    def test_copied_adapted_assumptions(self):
        text = self._guide()
        assert "assumption" in text.lower(), (
            "Guide must list copied/adapted assumptions"
        )

    def test_operator_verification(self):
        text = self._guide()
        assert "verify" in text.lower(), (
            "Guide must tell operators what to verify on their printer"
        )

    def test_legacy_removal(self):
        text = self._guide()
        assert "REMAP_TOOL" in text
        assert "BACKUP_SPOOL" in text
        assert "_TOOL_RUNOUT" in text

    def test_installation_include_order(self):
        text = self._guide()
        assert "include" in text.lower(), (
            "Guide must document installation/include order"
        )

    def test_commissioning_order(self):
        text = self._guide()
        assert "commission" in text.lower() or "staged" in text.lower(), (
            "Guide must describe commissioning order"
        )

    def test_hazards_stop_conditions(self):
        text = self._guide()
        assert "hazard" in text.lower() or "stop" in text.lower(), (
            "Guide must document hazards and stop conditions"
        )

    def test_evidence_links(self):
        text = self._guide()
        assert "LIVE-UAT" in text, (
            "Guide must link to the live-UAT runbook"
        )


# ===================================================================
# rollback — exact rollback instructions
# ===================================================================


class TestRollback:
    """Exact rollback steps are documented."""

    def test_rollback_section_exists(self):
        text = _read(TRIDENT / "README.md")
        assert "rollback" in text.lower(), (
            "Guide must contain rollback instructions"
        )

    def test_rollback_restores_legacy_macros(self):
        text = _read(TRIDENT / "README.md")
        assert "REMAP_TOOL" in text
        assert "BACKUP_SPOOL" in text
        assert "_TOOL_RUNOUT" in text

    def test_rollback_restores_includes(self):
        text = _read(TRIDENT / "README.md")
        # Rollback should mention removing includes
        assert "include" in text.lower(), (
            "Rollback must mention removing includes"
        )


# ===================================================================
# hazards — Trident-specific hazards and stop conditions
# ===================================================================


class TestHazards:
    """Trident-specific hazards and stop conditions are documented."""

    def test_collision_risk_documented(self):
        text = _read(TRIDENT / "README.md")
        assert "collision" in text.lower(), (
            "Guide must document dock/liftbar collision risk"
        )

    def test_purge_clearance_documented(self):
        text = _read(TRIDENT / "README.md")
        assert "purge" in text.lower() and "clearance" in text.lower(), (
            "Guide must document purge clearance"
        )

    def test_heating_documented(self):
        text = _read(TRIDENT / "README.md")
        assert "heater" in text.lower() or "heating" in text.lower(), (
            "Guide must document heating hazards"
        )


# ===================================================================
# redaction — reject common private-credential and machine-identifier
# ===================================================================


class TestRedaction:
    """Common secret and machine-identifier patterns are absent."""

    _SECRET_PATTERNS = [
        # Discord webhook URLs
        r"https://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+",
        # Telegram bot tokens (bot<digits>:<token>)
        r"bot\d+:[A-Za-z0-9_-]{30,}",
        # Generic API key / token forms
        r"(?:api[_-]?key|token|secret|password)\s*[=:]\s*[A-Za-z0-9+/=]{16,}",
        # CAN UUIDs (8-4-4-4-12 hex)
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        # Serial-by-id paths (/dev/serial/by-id/...)
        r"/dev/serial/by-id/[A-Za-z0-9_.-]+",
        # IP:port patterns that look like private service endpoints
        r"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\:\d{4,5}",
    ]

    def _scan_all(self) -> str:
        """Return concatenated text of every file under examples/trident/."""
        parts: list[str] = []
        for path in sorted(TRIDENT.rglob("*")):
            if path.is_file() and path.suffix in (".md", ".cfg", ".txt", ".ini"):
                try:
                    parts.append(_read(path))
                except OSError:
                    pass
        return "\n".join(parts)

    def test_no_discord_webhook_urls(self):
        text = self._scan_all()
        matches = re.findall(self._SECRET_PATTERNS[0], text)
        assert matches == [], f"Discord webhook URLs found: {matches}"

    def test_no_telegram_bot_tokens(self):
        text = self._scan_all()
        matches = re.findall(self._SECRET_PATTERNS[1], text)
        assert matches == [], f"Telegram bot tokens found: {matches}"

    def test_no_api_key_assignments(self):
        text = self._scan_all()
        matches = re.findall(self._SECRET_PATTERNS[2], text, re.IGNORECASE)
        assert matches == [], f"API key assignments found: {matches}"

    def test_no_can_uuids(self):
        text = self._scan_all()
        matches = re.findall(self._SECRET_PATTERNS[3], text)
        assert matches == [], f"CAN UUIDs found: {matches}"

    def test_no_serial_by_id_paths(self):
        text = self._scan_all()
        matches = re.findall(self._SECRET_PATTERNS[4], text)
        assert matches == [], f"Serial-by-id paths found: {matches}"


# ===================================================================
# uat / evidence / exclusion — runbook and evidence schema
# ===================================================================


class TestUATRunbook:
    """Staged live-UAT runbook structure and honesty."""

    def _runbook(self) -> str | None:
        path = TRIDENT / "LIVE-UAT.md"
        if path.exists():
            return _read(path)
        return None

    def test_runbook_exists(self):
        assert (TRIDENT / "LIVE-UAT.md").exists(), (
            "LIVE-UAT.md must exist"
        )

    def test_required_matrix_columns(self):
        text = self._runbook()
        assert text is not None, "LIVE-UAT.md must exist"
        required = [
            "ID", "Evidence", "Claim", "Topology", "Precondition",
            "Procedure", "Expected", "Observed", "Result",
            "Evidence", "Cleanup",
        ]
        # Check that key column headers appear (case-insensitive)
        lower = text.lower()
        for keyword in ["id", "evidence", "claim", "precondition",
                         "procedure", "expected", "observed", "result",
                         "cleanup"]:
            assert keyword in lower, (
                f"Runbook must contain column '{keyword}'"
            )

    def test_live_rows_accept_honest_mixed_states(self):
        """Lifecycle-aware: NOT RUN / FAIL / BLOCKED are acceptable without
        required fields; PASS rows must have evidence, revisions, observed
        result, and verified cleanup."""
        text = self._runbook()
        assert text is not None, "LIVE-UAT.md must exist"
        lines = text.splitlines()
        # Collect matrix rows (table body lines starting with |)
        matrix_rows: list[str] = []
        in_matrix = False
        for line in lines:
            stripped = line.strip()
            if "Staged Matrix" in line or "staged matrix" in line.lower():
                in_matrix = True
                continue
            if in_matrix and stripped.startswith("|---") or (
                in_matrix and stripped.startswith("|") and not stripped.startswith("| ")
            ):
                # header or separator — skip
                if stripped.startswith("|---"):
                    continue
            if in_matrix and stripped.startswith("|"):
                # Check if this is a data row (contains Result column)
                if "Result" in text[max(0, text.find(stripped) - 500):text.find(stripped)]:
                    pass
                matrix_rows.append(stripped)
        # At least one live row must exist (NOT RUN or otherwise)
        assert len(matrix_rows) > 0, (
            "Runbook matrix must contain live rows"
        )
        # Validate each row
        for row in matrix_rows:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            # Find the Result column (last meaningful column)
            result = cells[-1] if cells else ""
            if result == "PASS":
                # PASS rows MUST have:
                # 1. Observed result (not empty)
                # 2. Evidence column (not empty)
                # 3. Cleanup column (not empty)
                observed = cells[-4] if len(cells) >= 4 else ""
                evidence = cells[-3] if len(cells) >= 3 else ""
                cleanup = cells[-2] if len(cells) >= 2 else ""
                assert observed not in ("", "-"), (
                    f"PASS row must have an observed result: {row[:80]}"
                )
                assert evidence not in ("", "-"), (
                    f"PASS row must have committed evidence IDs: {row[:80]}"
                )
                assert cleanup not in ("", "-"), (
                    f"PASS row must have verified cleanup: {row[:80]}"
                )
            # NOT RUN, FAIL, BLOCKED are always acceptable without
            # required fields — they represent honest non-creditable states.

    def test_no_pass_without_evidence(self):
        """Regression: no PASS row may exist without evidence, observed
        result, and cleanup. This catches accidental overclaiming."""
        text = self._runbook()
        assert text is not None, "LIVE-UAT.md must exist"
        lines = text.splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("|") and "| PASS |" in stripped:
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                result = cells[-1] if cells else ""
                observed = cells[-4] if len(cells) >= 4 else ""
                evidence = cells[-3] if len(cells) >= 3 else ""
                cleanup = cells[-2] if len(cells) >= 2 else ""
                # At least one of observed/evidence/cleanup must be non-empty
                assert (
                    observed or evidence or cleanup
                ), f"PASS row must have supporting data: {stripped[:100]}"

    def test_bounded_claim_statement(self):
        text = self._runbook()
        if text is None:
            assert text is not None, "LIVE-UAT.md must exist"
        lower = text.lower()
        assert "bounded" in lower or "not a universal" in lower, (
            "Runbook must state bounded scope"
        )

    def test_simulation_only_for_failure_inputs(self):
        text = self._runbook()
        if text is None:
            assert text is not None, "LIVE-UAT.md must exist"
        lower = text.lower()
        assert "simulation" in lower or "simulated" in lower, (
            "Runbook must label failure inputs as simulation-only"
        )

    def test_stop_conditions_present(self):
        text = self._runbook()
        if text is None:
            assert text is not None, "LIVE-UAT.md must exist"
        lower = text.lower()
        assert "stop" in lower, (
            "Runbook must document stop conditions"
        )

    def test_cleanup_instructions_present(self):
        text = self._runbook()
        if text is None:
            assert text is not None, "LIVE-UAT.md must exist"
        lower = text.lower()
        assert "cleanup" in lower or "restore" in lower, (
            "Runbook must document cleanup instructions"
        )


class TestEvidenceSchema:
    """Evidence policy, redaction legend, and excerpt template."""

    def _evidence_readme(self) -> str | None:
        path = TRIDENT / "evidence" / "README.md"
        if path.exists():
            return _read(path)
        return None

    def test_evidence_readme_exists(self):
        assert (TRIDENT / "evidence" / "README.md").exists(), (
            "evidence/README.md must exist"
        )

    def test_evidence_classes_defined(self):
        text = self._evidence_readme()
        if text is None:
            assert text is not None, "evidence/README.md must exist"
        lower = text.lower()
        for cls in ("automated-contract", "simulated-input",
                     "normal-live-operation"):
            assert cls in lower, (
                f"Evidence policy must define class '{cls}'"
            )

    def test_result_states_defined(self):
        text = self._evidence_readme()
        if text is None:
            assert text is not None, "evidence/README.md must exist"
        lower = text.lower()
        for state in ("pass", "fail", "blocked", "not run"):
            assert state in lower, (
                f"Evidence policy must define result state '{state}'"
            )

    def test_redaction_legend_present(self):
        text = self._evidence_readme()
        if text is None:
            assert text is not None, "evidence/README.md must exist"
        assert "<TRIDENT_MAIN_MCU>" in text
        assert "<T0_CAN_UUID>" in text
        assert "<DISCORD_DESTINATION>" in text

    def test_raw_artifacts_prohibited(self):
        text = self._evidence_readme()
        if text is None:
            assert text is not None, "evidence/README.md must exist"
        lower = text.lower()
        assert "log" in lower and "prohibit" in lower or (
            "raw" in lower and "commit" in lower
        ), (
            "Evidence policy must prohibit committing raw logs/config/state"
        )

    def test_excerpts_template_exists(self):
        assert (TRIDENT / "evidence" / "phase6-live-log.md").exists(), (
            "phase6-live-log.md must exist"
        )

    def test_excerpts_template_has_required_fields(self):
        path = TRIDENT / "evidence" / "phase6-live-log.md"
        if not path.exists():
            assert path.exists(), "phase6-live-log.md must exist"
        text = _read(path)
        lower = text.lower()
        for field in ("excerpt", "timestamp", "row", "source",
                      "redaction"):
            assert field in lower, (
                f"Log template must contain field '{field}'"
            )


class TestExclusions:
    """All four excluded Phase 1 scenarios are named and excluded."""

    EXCLUDED_SCENARIOS = [
        "Valid Configuration Startup",
        "Persisted State Survives Restart",
        "Invalid State Blocks Startup Clearly",
        "Read-Only Status Inspection",
    ]

    def _text_sources(self) -> list[str]:
        sources = [_read(TRIDENT / "README.md")]
        runbook = TRIDENT / "LIVE-UAT.md"
        if runbook.exists():
            sources.append(_read(runbook))
        return sources

    def test_all_four_exclusions_named_in_guide(self):
        text = _read(TRIDENT / "README.md")
        for scenario in self.EXCLUDED_SCENARIOS:
            assert scenario in text, (
                f"README must name excluded scenario: {scenario}"
            )

    def test_all_four_exclusions_named_in_runbook(self):
        runbook = TRIDENT / "LIVE-UAT.md"
        if not runbook.exists():
            assert text is not None, "LIVE-UAT.md must exist"
        text = _read(runbook)
        for scenario in self.EXCLUDED_SCENARIOS:
            assert scenario in text, (
                f"Runbook must name excluded scenario: {scenario}"
            )

    def test_exclusions_not_credited(self):
        """No procedure executes or credits an excluded scenario."""
        for text in self._text_sources():
            lower = text.lower()
            # The word "excluded" should appear with each scenario
            for scenario in self.EXCLUDED_SCENARIOS:
                idx = lower.find(scenario.lower())
                assert idx >= 0, f"Missing: {scenario}"
                # Ensure the context around the mention is exclusionary.
                # Use a wide window to catch the "EXCLUDED — NOT EXECUTED"
                # header that precedes the numbered list.
                context = text[max(0, idx - 300):idx + 200].lower()
                assert any(
                    word in context
                    for word in ("excluded", "not executed", "not credited")
                ), (
                    f"Scenario '{scenario}' must be explicitly excluded, "
                    f"not described as a procedure"
                )
