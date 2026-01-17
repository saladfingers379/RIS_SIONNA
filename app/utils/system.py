import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from typing import Any, Dict, Optional


def _safe_version(pkg: str) -> Optional[str]:
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None


def disable_pythreejs_import(reason: str = "cli") -> None:
    """Stub out pythreejs to avoid slow imports when previews are unused."""
    import sys
    import types

    if "pythreejs" in sys.modules:
        return
    stub = types.ModuleType("pythreejs")
    stub.__dict__["__ris_sionna_stub__"] = reason

    class _Dummy:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return None

    for name in [
        "PerspectiveCamera",
        "OrthographicCamera",
        "Mesh",
        "BufferGeometry",
        "MeshLambertMaterial",
        "MeshBasicMaterial",
        "LineBasicMaterial",
        "LineSegments",
        "Scene",
        "DirectionalLight",
        "AmbientLight",
        "Vector3",
        "SpriteMaterial",
        "Sprite",
        "Group",
        "AxesHelper",
        "GridHelper",
    ]:
        stub.__dict__[name] = _Dummy

    def __getattr__(name: str):
        return _Dummy

    stub.__getattr__ = __getattr__  # type: ignore[attr-defined]
    sys.modules["pythreejs"] = stub


def select_mitsuba_variant(prefer_gpu: bool, forced_variant: str = "auto") -> str:
    import mitsuba as mi

    variants = list(mi.variants())
    if forced_variant and forced_variant != "auto":
        if forced_variant not in variants:
            raise ValueError(f"Requested Mitsuba variant '{forced_variant}' not in {variants}")
        mi.set_variant(forced_variant)
        return mi.variant()

    if prefer_gpu and "cuda_ad_rgb" in variants:
        mi.set_variant("cuda_ad_rgb")
        return mi.variant()

    # Prefer spectral variants on CPU to avoid RGB spectrum shape mismatches.
    for candidate in [
        "llvm_ad_mono_polarized",
        "llvm_ad_spectral_polarized",
        "scalar_spectral_polarized",
        "llvm_ad_spectral",
        "scalar_spectral",
        "llvm_ad_rgb",
        "scalar_rgb",
    ]:
        if candidate in variants:
            mi.set_variant(candidate)
            return mi.variant()

    mi.set_variant(variants[0])
    return mi.variant()


def configure_tensorflow_memory_growth(
    timeout_s: float = 5.0,
    mode: str = "auto",
) -> Dict[str, Any]:
    """Attempt to configure TF GPU memory growth with a timeout to avoid hangs."""
    import concurrent.futures

    info: Dict[str, Any] = {}
    if mode not in {"auto", "force", "skip"}:
        info["tensorflow_import_error"] = f"Unknown tensorflow_import mode: {mode}"
        return info
    if mode == "skip":
        info["tensorflow_import_skipped"] = True
        return info
    if mode == "auto" and platform.system() == "Darwin":
        info["tensorflow_import_skipped"] = True
        info["tensorflow_import_reason"] = "darwin"
        return info

    def _load_tf():
        import tensorflow as tf  # pylint: disable=import-error
        return tf

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_load_tf)
        try:
            tf = future.result(timeout=timeout_s)
        except Exception as exc:  # pragma: no cover - optional runtime behavior
            info["tensorflow_import_error"] = str(exc)
            info["tensorflow_import_timeout_s"] = timeout_s
            return info

    gpus = tf.config.list_physical_devices("GPU")
    info["tf_gpus"] = [g.name for g in gpus]
    if gpus:
        try:
            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)
            info["tf_memory_growth"] = True
        except RuntimeError as exc:
            info["tf_memory_growth_error"] = str(exc)
    return info


def collect_environment_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    info["platform"] = platform.platform()
    info["python_version"] = platform.python_version()
    info["in_docker"] = os.path.exists("/.dockerenv")

    info["versions"] = {
        "sionna": _safe_version("sionna"),
        "sionna-rt": _safe_version("sionna-rt"),
        "tensorflow": _safe_version("tensorflow"),
        "drjit": _safe_version("drjit"),
        "mitsuba": _safe_version("mitsuba"),
        "numpy": _safe_version("numpy"),
    }

    try:
        import mitsuba as mi
        info["mitsuba_variants"] = list(mi.variants())
        try:
            info["mitsuba_variant"] = mi.variant()
        except Exception as exc:  # pragma: no cover
            info["mitsuba_variant_error"] = str(exc)
    except Exception as exc:  # pragma: no cover
        info["mitsuba_error"] = str(exc)

    if platform.system() == "Darwin":
        info["tensorflow_error"] = "Skipped TensorFlow import on macOS to avoid startup hangs."
    else:
        try:
            import tensorflow as tf
            info["tensorflow_gpus"] = [g.name for g in tf.config.list_physical_devices("GPU")]
            info["tensorflow_build"] = tf.sysconfig.get_build_info()
        except Exception as exc:  # pragma: no cover
            info["tensorflow_error"] = str(exc)

    info["docker_gpu_env"] = {
        "NVIDIA_VISIBLE_DEVICES": os.getenv("NVIDIA_VISIBLE_DEVICES"),
        "NVIDIA_DRIVER_CAPABILITIES": os.getenv("NVIDIA_DRIVER_CAPABILITIES"),
    }

    try:
        result = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, check=False)
        info["nvidia_smi"] = result.stdout.strip() or result.stderr.strip()
    except FileNotFoundError:
        info["nvidia_smi"] = "nvidia-smi not found"

    warnings = []
    if sys.version_info >= (3, 13):
        warnings.append(
            "Python 3.13 detected. Sionna 1.2.1 requires numpy<2.0; use Python 3.10–3.12."
        )
    if info["versions"].get("numpy") and info["versions"]["numpy"].startswith("2."):
        warnings.append(
            "NumPy 2.x detected. Sionna 1.2.1 requires numpy<2.0."
        )
    if warnings:
        info["warnings"] = warnings

    return info


def print_environment_info() -> None:
    info = collect_environment_info()
    print(json.dumps(info, indent=2))
