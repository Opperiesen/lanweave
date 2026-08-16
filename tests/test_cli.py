import json
from pathlib import Path

import pytest

from lanweave.cli import _confirm_apply, _render_plan, build_parser, main
from lanweave.plan import Plan, ResourceDiff


def test_init_and_validate_commands(tmp_path: Path, capsys) -> None:
    path = tmp_path / "config" / "network.yaml"

    assert main(["init", "--path", str(path)]) == 0
    assert main(["validate", "--config", str(path)]) == 0

    assert "created" in capsys.readouterr().out


def test_doctor_is_offline_by_default(monkeypatch, capsys) -> None:
    monkeypatch.setenv("UNIFI_HOST", "https://controller.example")
    monkeypatch.setenv("UNIFI_API_KEY", "test-key")

    assert main(["doctor"]) == 0

    output = capsys.readouterr().out
    assert "configuration looks usable" in output
    assert "reachable" not in output


def test_cli_contract_exposes_stable_options() -> None:
    args = build_parser().parse_args(
        ["plan", "--config", "network.yaml", "--prune", "--output", "json"]
    )

    assert args.command == "plan"
    assert args.config.name == "network.yaml"
    assert args.prune is True
    assert args.output == "json"

    profiles = build_parser().parse_args(["profiles", "list", "--config", "profiles.yaml"])
    assert profiles.command == "profiles"
    assert profiles.profiles_command == "list"
    assert profiles.config.name == "profiles.yaml"

    doctor = build_parser().parse_args(
        ["doctor", "--config", "profiles.yaml", "--profile", "office"]
    )
    assert doctor.config.name == "profiles.yaml"
    assert doctor.profile == "office"

    plan = build_parser().parse_args(["plan", "--config", "profiles.yaml", "--profile", "guest"])
    assert plan.profile == "guest"

    capabilities = build_parser().parse_args(
        ["capabilities", "--config", "profiles.yaml", "--profile", "cloud", "--output", "json"]
    )
    assert capabilities.command == "capabilities"
    assert capabilities.output == "json"

    vpn = build_parser().parse_args(["vpn", "--config", "profiles.yaml", "--output", "json"])
    assert vpn.command == "vpn"
    assert vpn.config.name == "profiles.yaml"
    assert vpn.output == "json"

    apply = build_parser().parse_args(
        [
            "apply",
            "--config",
            "network.yaml",
            "--yes",
            "--acknowledge-risk",
        ]
    )
    assert apply.acknowledge_risk is True

    legacy_apply = build_parser().parse_args(
        ["apply", "--config", "network.yaml", "--acknowledge-firewall-risk"]
    )
    assert legacy_apply.acknowledge_risk is True


def test_cli_renders_firewall_reordering_and_warnings(capsys) -> None:
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="firewall_rule",
                action="reorder",
                name="Trusted -> WAN",
                payload={
                    "source_zone": "Trusted",
                    "destination_zone": "WAN",
                    "before_system_defined": [],
                    "after_system_defined": ["allow-web"],
                },
                warnings=("rule order changes first-match behavior",),
            )
        ]
    )

    _render_plan(plan, "table")

    output = capsys.readouterr().out
    assert "!1 reorder" in output
    assert "reorder  firewall_rule" in output
    assert "WARNING  firewall_rule/Trusted -> WAN" in output


def test_cli_requires_risk_acknowledgement_even_with_yes(capsys) -> None:
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="firewall_rule",
                action="create",
                name="allow-web",
                payload={"name": "allow-web"},
                warnings=("broad match",),
            )
        ]
    )

    assert _confirm_apply(plan, prune=False, yes=True, acknowledge_risk=False) is False
    assert _confirm_apply(plan, prune=False, yes=True, acknowledge_risk=True) is True
    assert "refusing risky apply" in capsys.readouterr().err


def test_cli_interactive_firewall_acknowledgement_is_consumed(monkeypatch) -> None:
    plan = Plan(
        diffs=[
            ResourceDiff(
                kind="firewall_rule",
                action="create",
                name="allow-web",
                payload={"name": "allow-web"},
                warnings=("broad match",),
            )
        ]
    )

    class TTY:
        def isatty(self) -> bool:
            return True

    answers = iter(("ACKNOWLEDGE_FIREWALL_RISK", "APPLY"))
    monkeypatch.setattr("lanweave.cli.sys.stdin", TTY())
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    assert _confirm_apply(plan, prune=False, yes=False, acknowledge_risk=False) is True


def test_validate_reports_nat_mapping_count(tmp_path: Path, capsys) -> None:
    path = tmp_path / "network.yaml"
    path.write_text(
        """\
version: 1
controller:
  site: default
networks: []
wlans: []
nat:
  - name: web
    protocol: TCP
    public:
      interface: WAN
      port: 443
    private:
      address: 192.0.2.10
      port: 8443
""",
        encoding="utf-8",
    )

    assert main(["validate", "--config", str(path)]) == 0

    assert "1 NAT mapping(s)" in capsys.readouterr().out


def test_profiles_commands_are_offline_and_secret_free(tmp_path: Path, capsys) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["profiles", "validate", "--config", str(path)]) == 0
    assert "valid configuration: version=2 profiles=3 networks=0 wlans=0" in capsys.readouterr().out

    assert main(["profiles", "list", "--config", str(path)]) == 0
    output = capsys.readouterr().out
    assert "profile=backup-default controller=backup site=default adapter=local-classic" in output
    assert "LANWEAVE_" not in output


def test_controller_command_announces_the_selected_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("LANWEAVE_LOCAL_HOST", "https://local.example")
    monkeypatch.setenv("LANWEAVE_LOCAL_API_KEY", "local-key")

    class FakeClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def health(self):
            return []

        def clients(self):
            return []

        def devices(self):
            return []

    monkeypatch.setattr("lanweave.cli.UniFiClient", FakeClient)

    assert main(["status", "--config", str(path)]) == 0

    assert (
        "target: profile=office controller=local site=default adapter=local-classic"
        in capsys.readouterr().err
    )


def test_plan_outputs_the_selected_target_in_table_and_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("LANWEAVE_LOCAL_HOST", "https://local.example")
    monkeypatch.setenv("LANWEAVE_LOCAL_API_KEY", "local-key")

    class FakeClient:
        def __init__(self, settings) -> None:
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def networks(self):
            return []

        def wlans(self):
            return []

    monkeypatch.setattr("lanweave.cli.UniFiClient", FakeClient)

    assert main(["plan", "--config", str(path), "--output", "json"]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["target"] == {
        "profile": "office",
        "controller": "local",
        "site": "default",
        "adapter": "local-classic",
    }

    assert main(["plan", "--config", str(path)]) == 0
    assert (
        "Target: profile=office controller=local site=default adapter=local-classic"
        in capsys.readouterr().out
    )


def test_plan_rejects_a_conflicting_explicit_profile_before_controller_access(
    tmp_path: Path,
    capsys,
) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    assert main(["plan", "--config", str(path), "--profile", "guest"]) == 2

    assert "conflicting profile selectors" in capsys.readouterr().err


def test_capabilities_rejects_an_unknown_profile_with_exit_code_two(tmp_path: Path, capsys) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-adapters.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(
        fixture.read_text(encoding="utf-8").replace("profile: local-office\n", ""),
        encoding="utf-8",
    )

    assert main(["capabilities", "--config", str(path), "--profile", "missing"]) == 2
    assert "unknown profile: missing" in capsys.readouterr().err


def test_capabilities_are_offline_and_show_explicit_cloud_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-adapters.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(
        fixture.read_text(encoding="utf-8").replace("profile: local-office\n", ""),
        encoding="utf-8",
    )
    monkeypatch.delenv("LANWEAVE_CLOUD_HOST", raising=False)
    monkeypatch.delenv("LANWEAVE_CLOUD_API_KEY", raising=False)

    assert (
        main(
            [
                "capabilities",
                "--config",
                str(path),
                "--profile",
                "cloud-overview",
                "--output",
                "json",
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    assert rendered["target"] == {
        "profile": "cloud-overview",
        "controller": "cloud",
        "site": "organization",
        "adapter": "cloud-site-manager",
    }
    assert rendered["capabilities"] == {
        "format_version": 1,
        "adapter": "cloud-site-manager",
        "auth_modes": ["api-key"],
        "resources": [
            {"resource": "devices", "operations": ["read"]},
            {"resource": "health", "operations": ["read"]},
            {"resource": "hosts", "operations": ["read"]},
            {"resource": "sites", "operations": ["read"]},
        ],
    }


def test_session_capabilities_expose_the_complete_nat_lifecycle_offline(
    tmp_path: Path,
    capsys,
) -> None:
    fixture = Path(__file__).parents[1] / "tests/fixtures/profiles/config-v2-multi-target.yaml"
    path = tmp_path / "profiles.yaml"
    path.write_text(
        fixture.read_text(encoding="utf-8").replace(
            "profile: office\n", "profile: backup-default\n"
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "capabilities",
                "--config",
                str(path),
                "--profile",
                "backup-default",
                "--output",
                "json",
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    resources = {
        item["resource"]: item["operations"] for item in rendered["capabilities"]["resources"]
    }
    assert resources["nat"] == ["read", "export", "plan", "apply", "prune"]


def test_cli_rejected_overwrite_and_missing_config_use_exit_code_two(
    tmp_path: Path, capsys
) -> None:
    path = tmp_path / "network.yaml"
    path.write_text("existing", encoding="utf-8")

    assert main(["init", "--path", str(path)]) == 2
    assert main(["validate", "--config", str(tmp_path / "missing.yaml")]) == 2

    assert "refusing to overwrite" in capsys.readouterr().err


def test_cli_version_uses_zero_exit_code(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert "0.6.0" in capsys.readouterr().out
