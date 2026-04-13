from argparse import Namespace

from app import cli
import app.sim_server as sim_server


def test_sim_command_warns_when_auth_password_is_missing(monkeypatch, capsys) -> None:
    calls = {}

    def _fake_parse_args() -> Namespace:
        return Namespace(
            command="sim",
            host="127.0.0.1",
            port=8765,
            no_browser=True,
            auth_password_env="SIM_PASSWORD",
            auth_password_file=None,
        )

    def _fake_serve_simulator(host: str, port: int, auth_password=None) -> None:
        calls["host"] = host
        calls["port"] = port
        calls["auth_password"] = auth_password

    monkeypatch.setattr(cli, "_parse_args", _fake_parse_args)
    monkeypatch.setattr(sim_server, "serve_simulator", _fake_serve_simulator)
    monkeypatch.delenv("SIM_PASSWORD", raising=False)

    cli.main()

    out = capsys.readouterr().out
    assert "Simulator access password is disabled." in out
    assert "SIM_PASSWORD" in out
    assert calls == {"host": "127.0.0.1", "port": 8765, "auth_password": None}


def test_sim_command_reads_auth_password_from_env(monkeypatch, capsys) -> None:
    calls = {}

    def _fake_parse_args() -> Namespace:
        return Namespace(
            command="sim",
            host="127.0.0.1",
            port=8765,
            no_browser=True,
            auth_password_env="SIM_PASSWORD",
            auth_password_file=None,
        )

    def _fake_serve_simulator(host: str, port: int, auth_password=None) -> None:
        calls["host"] = host
        calls["port"] = port
        calls["auth_password"] = auth_password

    monkeypatch.setattr(cli, "_parse_args", _fake_parse_args)
    monkeypatch.setattr(sim_server, "serve_simulator", _fake_serve_simulator)
    monkeypatch.setenv("SIM_PASSWORD", "demo-pass")

    cli.main()

    out = capsys.readouterr().out
    assert "Simulator access password is disabled." not in out
    assert calls == {"host": "127.0.0.1", "port": 8765, "auth_password": "demo-pass"}
