import argparse
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path

from .io import find_latest_output_dir
from .plots import plot_radio_map_from_npz
from .simulate import run_simulation
from .utils.logging import setup_logging
from .utils.system import print_diagnose_info

logger = logging.getLogger(__name__)

def _pick_dashboard_port(preferred: int = 8501) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app", description="RIS_SIONNA CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_p = subparsers.add_parser("run", help="Run a Sionna RT simulation")
    run_p.add_argument("--config", required=True, help="Path to YAML config")

    plot_p = subparsers.add_parser("plot", help="Plot from saved outputs")
    plot_group = plot_p.add_mutually_exclusive_group(required=True)
    plot_group.add_argument("--latest", action="store_true", help="Use latest output dir")
    plot_group.add_argument("--output-dir", help="Path to an outputs/<timestamp> directory")
    plot_p.add_argument(
        "--metric",
        default="path_gain_db",
        choices=["path_gain_db", "rx_power_dbm", "path_loss_db"],
        help="Which metric to plot",
    )

    subparsers.add_parser("diagnose", help="Print environment diagnostics")
    subparsers.add_parser("dashboard", help="Launch the visualization dashboard")
    sim_p = subparsers.add_parser("sim", help="Launch the Omniverse-lite simulator")
    sim_p.add_argument("--host", default="127.0.0.1", help="Host to bind the simulator")
    sim_p.add_argument("--port", type=int, default=8765, help="Port for the simulator UI")
    sim_p.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")

    ris_p = subparsers.add_parser("ris", help="RIS Lab tools")
    ris_subparsers = ris_p.add_subparsers(dest="ris_command", required=True)
    ris_run = ris_subparsers.add_parser("run", help="Run RIS Lab")
    ris_run.add_argument("--config", required=True, help="Path to RIS Lab YAML config")
    ris_run.add_argument(
        "--mode",
        required=True,
        choices=["pattern", "link"],
        help="Run mode: pattern or link",
    )
    ris_validate = ris_subparsers.add_parser("validate", help="Validate RIS Lab")
    ris_validate.add_argument("--config", required=True, help="Path to RIS Lab YAML config")
    ris_validate.add_argument(
        "--ref", required=True, help="Path to reference CSV or NPZ file"
    )

    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = _parse_args()

    if args.command == "run":
        output_dir = run_simulation(args.config)
        logger.info("Outputs saved to %s", output_dir)
        return

    if args.command == "plot":
        if args.latest:
            output_dir = find_latest_output_dir("outputs")
            if output_dir is None:
                raise SystemExit("No outputs found under ./outputs")
        else:
            output_dir = Path(args.output_dir)

        npz_path = output_dir / "data" / "radio_map.npz"
        if not npz_path.exists():
            raise SystemExit(f"radio_map.npz not found in {output_dir}")

        plots_dir = output_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)
        metric_map = {
            "path_gain_db": ("path_gain_db", "Path gain [dB]", "radio_map_path_gain_db"),
            "rx_power_dbm": ("rx_power_dbm", "Rx power [dBm]", "radio_map_rx_power_dbm"),
            "path_loss_db": ("path_loss_db", "Path loss [dB]", "radio_map_path_loss_db"),
        }[args.metric]
        plot_radio_map_from_npz(npz_path, plots_dir, *metric_map)
        logger.info("Plots saved to %s", output_dir / "plots")
        return

    if args.command == "diagnose":
        print_diagnose_info()
        return

    if args.command == "dashboard":
        try:
            import streamlit  # noqa: F401
        except Exception:
            raise SystemExit("Streamlit not installed. Install with: pip install .[dashboard]")

        port = _pick_dashboard_port(8501)
        logger.info("Starting dashboard at http://127.0.0.1:%s (press Ctrl+C to stop)", port)
        env = dict(**dict(os.environ))
        env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app/dashboard_app.py",
                "--server.headless",
                "true",
                "--server.fileWatcherType",
                "none",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(port),
                "--browser.gatherUsageStats",
                "false",
            ],
            check=True,
            env=env,
        )
        return

    if args.command == "sim":
        from .sim_server import serve_simulator
        if not args.no_browser:
            import webbrowser
            webbrowser.open(f"http://{args.host}:{args.port}")
        serve_simulator(host=args.host, port=int(args.port))
        return

    if args.command == "ris":
        from .ris.ris_lab import run_ris_lab, validate_ris_lab

        if args.ris_command == "run":
            run_ris_lab(args.config, args.mode)
            return
        if args.ris_command == "validate":
            validate_ris_lab(args.config, args.ref)
            return


if __name__ == "__main__":
    main()
