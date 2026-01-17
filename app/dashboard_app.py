from pathlib import Path
import json
import socket
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

import streamlit as st
import yaml

from app.viewer import generate_viewer


st.set_page_config(page_title="RIS_SIONNA Dashboard", layout="wide")
st.title("RIS_SIONNA Dashboard")

output_root = Path("outputs")
if not output_root.exists():
    st.info("No outputs directory found yet. Run a simulation first.")
    st.stop()

runs = sorted(
    [p for p in output_root.iterdir() if p.is_dir() and not p.name.startswith("_")],
    reverse=True,
)
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

config_data = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
scene_cfg = config_data.get("scene", {})

mesh_dir = Path("scenes")
mesh_files = []
if mesh_dir.exists():
    mesh_files = sorted([p for p in mesh_dir.iterdir() if p.suffix.lower() in [".glb", ".gltf", ".obj"]])

with st.sidebar:
    st.header("3D Viewer")
    mesh_choices = ["Use run config"] + [p.name for p in mesh_files]
    mesh_choice = st.selectbox("Mesh override", mesh_choices, index=0)
    proxy_default = st.checkbox("Show proxy geometry by default", value=bool(scene_cfg.get("proxy_enabled", True)))
    regen_clicked = st.button("Regenerate viewer now")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_viewer_server(root_dir: Path) -> int:
    handler = partial(SimpleHTTPRequestHandler, directory=str(root_dir))
    port = _find_free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return port


if regen_clicked:
    updated_scene = dict(scene_cfg)
    if mesh_choice != "Use run config":
        updated_scene["mesh"] = str(mesh_dir / mesh_choice)
    updated_scene["proxy_enabled"] = proxy_default
    updated_config = dict(config_data)
    updated_config["scene"] = updated_scene
    try:
        generate_viewer(run_dir, updated_config)
    except Exception as exc:
        st.sidebar.warning(f"Viewer update failed: {exc}")

viewer_html = run_dir / "viewer" / "index.html"
viewer_root = viewer_html.parent if viewer_html.exists() else None
viewer_url = None
if viewer_root is not None:
    existing_root = st.session_state.get("viewer_root")
    if existing_root != str(viewer_root):
        try:
            port = _start_viewer_server(viewer_root)
            st.session_state["viewer_root"] = str(viewer_root)
            st.session_state["viewer_port"] = port
        except Exception:
            st.session_state["viewer_port"] = None
    if st.session_state.get("viewer_port"):
        viewer_url = f"http://127.0.0.1:{st.session_state['viewer_port']}/index.html"


def _load_json_with_retry(path: Path, attempts: int = 3, delay_s: float = 0.2):
    for _ in range(attempts):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            time.sleep(delay_s)
    return None


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

tabs = st.tabs(["Summary", "Config", "Metrics", "Maps", "3D View", "Scene", "Downloads"])

with tabs[0]:
    if summary_path.exists():
        summary = _load_json_with_retry(summary_path)
        if summary is None:
            st.warning("summary.json not readable yet. Try refreshing.")
        else:
            st.json(summary, expanded=False)
    else:
        st.warning("summary.json not found")

with tabs[1]:
    if config_path.exists():
        st.code(config_path.read_text(), language="yaml")
    else:
        st.warning("config.yaml not found")

with tabs[2]:
    st.subheader("Path Metrics")
    delay_png = plots_dir / "path_delay_hist.png"
    aoa_az_png = plots_dir / "aoa_azimuth_hist.png"
    aoa_el_png = plots_dir / "aoa_elevation_hist.png"
    if delay_png.exists():
        st.image(str(delay_png), caption="Path delay distribution", width="stretch")
    if aoa_az_png.exists():
        st.image(str(aoa_az_png), caption="AoA azimuth distribution", width="stretch")
    if aoa_el_png.exists():
        st.image(str(aoa_el_png), caption="AoA elevation distribution", width="stretch")
    if not any(p.exists() for p in [delay_png, aoa_az_png, aoa_el_png]):
        st.info("No path metric plots found yet.")

with tabs[3]:
    st.subheader("Coverage Maps")
    if plot_png.exists():
        st.image(str(plot_png), caption=f"Radio map ({metric_label})", width="stretch")
    elif legacy_png.exists():
        st.image(str(legacy_png), caption="Radio map (legacy)", width="stretch")
    else:
        st.info("No plot found yet.")

with tabs[4]:
    st.subheader("3D View (Rays + Devices)")
    if viewer_url:
        st.components.v1.iframe(viewer_url, height=600, scrolling=False)
        st.caption(f"Viewer URL: {viewer_url}")
    elif viewer_html.exists():
        st.components.v1.html(viewer_html.read_text(), height=600, scrolling=False)
        st.caption(f"Local viewer file: {viewer_html}")
        st.caption("If the embedded view is blank, open the HTML file directly in your browser.")
    else:
        ray_png = plots_dir / "ray_paths_3d.png"
        if ray_png.exists():
            st.image(str(ray_png), caption="Ray paths (static 3D view)", width="stretch")
        else:
            st.info("No 3D ray plot found yet.")

with tabs[5]:
    scene_png = plots_dir / "scene.png"
    if scene_png.exists():
        st.image(str(scene_png), caption="Scene render", width="stretch")
        st.caption("Legend: red marker = transmitter (Tx), green marker = receiver (Rx).")
    else:
        st.info("No scene render found yet.")

with tabs[6]:
    download_files = [
        plot_png,
        plots_dir / metric_options[metric_label].replace(".png", ".svg"),
        plots_dir / "scene.png",
        plots_dir / "path_delay_hist.png",
        plots_dir / "aoa_azimuth_hist.png",
        plots_dir / "aoa_elevation_hist.png",
        data_dir / "radio_map.csv",
        data_dir / "radio_map.npz",
        data_dir / "ray_paths.csv",
        data_dir / "ray_paths.npz",
    ]
    for file_path in download_files:
        if file_path.exists():
            st.download_button(
                label=f"Download {file_path.name}",
                data=file_path.read_bytes(),
                file_name=file_path.name,
                mime="application/octet-stream",
            )
