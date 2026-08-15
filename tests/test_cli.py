from pathlib import Path

import pytest

from lanweave.cli import build_parser, main


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
    assert "0.1.0" in capsys.readouterr().out
