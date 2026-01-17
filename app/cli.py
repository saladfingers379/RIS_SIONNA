import argparse
import logging
import subprocess
import sys
from pathlib import Path

from .io import find_latest_output_dir
from .plots import plot_radio_map_from_npz
from .simulate import run_simulation
from .utils.logging import setup_logging
from .utils.system import print_environment_info

logger = logging.getLogger(__name__)


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
        print_environment_info()
        return

    if args.command == "dashboard":
        try:
            import streamlit  # noqa: F401
        except Exception:
            raise SystemExit("Streamlit not installed. Install with: pip install .[dashboard]")

        subprocess.run([sys.executable, "-m", "streamlit", "run", "app/dashboard_app.py"], check=True)
        return


if __name__ == "__main__":
    main()
