from pathlib import Path
import json
import time

import streamlit as st


st.set_page_config(page_title="RIS_SIONNA Dashboard", layout="wide")
st.title("RIS_SIONNA Dashboard")

output_root = Path("outputs")
if not output_root.exists():
    st.info("No outputs directory found yet. Run a simulation first.")
    st.stop()

runs = sorted([p for p in output_root.iterdir() if p.is_dir()], reverse=True)
if not runs:
    st.info("No runs found. Run a simulation first.")
    st.stop()

run_labels = [p.name for p in runs]
with st.sidebar:
    st.header("Runs")
    selected = st.selectbox("Most recent first", run_labels, index=0)
run_dir = output_root / selected

summary_path = run_dir / "summary.json"
config_path = run_dir / "config.yaml"
plots_dir = run_dir / "plots"
data_dir = run_dir / "data"

def _load_json_with_retry(path: Path, attempts: int = 3, delay_s: float = 0.2):
    for _ in range(attempts):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            time.sleep(delay_s)
    return None

tabs = st.tabs(["Summary", "Config", "Maps", "Scene", "Downloads"])
metric_options = {
    "Path gain [dB]": "radio_map_path_gain_db.png",
    "Rx power [dBm]": "radio_map_rx_power_dbm.png",
    "Path loss [dB]": "radio_map_path_loss_db.png",
}
with st.sidebar:
    st.header("Metrics")
    metric_label = st.selectbox("Coverage metric", list(metric_options.keys()), index=0)
plot_png = plots_dir / metric_options[metric_label]
legacy_png = plots_dir / "radio_map.png"

with tabs[0]:
    if summary_path.exists():
        summary = _load_json_with_retry(summary_path)
        if summary is None:
            st.warning("summary.json not readable yet. Try refreshing.")
        else:
            st.json(summary)
    else:
        st.warning("summary.json not found")

with tabs[1]:
    if config_path.exists():
        st.code(config_path.read_text(), language="yaml")
    else:
        st.warning("config.yaml not found")

with tabs[2]:
    st.subheader("Coverage Maps")
    if plot_png.exists():
        st.image(str(plot_png), caption=f"Radio map ({metric_label})", width="stretch")
    elif legacy_png.exists():
        st.image(str(legacy_png), caption="Radio map (legacy)", width="stretch")
    else:
        st.info("No plot found yet.")

with tabs[3]:
    scene_png = plots_dir / "scene.png"
    if scene_png.exists():
        st.image(str(scene_png), caption="Scene render", width="stretch")
        st.caption("Legend: red marker = transmitter (Tx), green marker = receiver (Rx).")
    else:
        st.info("No scene render found yet.")

with tabs[4]:
    download_files = [
        plot_png,
        plots_dir / metric_options[metric_label].replace(".png", ".svg"),
        plots_dir / "scene.png",
        data_dir / "radio_map.csv",
        data_dir / "radio_map.npz",
    ]
    for file_path in download_files:
        if file_path.exists():
            st.download_button(
                label=f"Download {file_path.name}",
                data=file_path.read_bytes(),
                file_name=file_path.name,
                mime="application/octet-stream",
            )
