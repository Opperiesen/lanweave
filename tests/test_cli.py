from pathlib import Path

from lanweave.cli import main


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
