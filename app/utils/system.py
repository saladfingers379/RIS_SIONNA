import ctypes
import importlib.metadata
import logging
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple


_DRJIT_CACHE_DIR = os.environ.get("DRJIT_CACHE_DIR", "/tmp/drjit-cache")
os.environ.setdefault("DRJIT_CACHE_DIR", _DRJIT_CACHE_DIR)
try:
    os.makedirs(_DRJIT_CACHE_DIR, exist_ok=True)
except Exception:
    pass

def _safe_version(pkg: str) -> Optional[str]:
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None


def _preferred_cuda_variant(variants: list[str]) -> Optional[str]:
    for candidate in [
        "cuda_ad_mono_polarized",
        "cuda_ad_spectral_polarized",
        "cuda_ad_mono",
        "cuda_ad_spectral",
        "cuda_ad_rgb",
    ]:
        if candidate in variants:
            return candidate
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


def select_mitsuba_variant(
    prefer_gpu: bool,
    forced_variant: str = "auto",
    require_cuda: bool = False,
) -> str:
    cache_dir = os.environ.get("DRJIT_CACHE_DIR", "/tmp/drjit-cache")
    os.environ.setdefault("DRJIT_CACHE_DIR", cache_dir)
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        pass
    import mitsuba as mi

    variants = list(mi.variants())
    logger = logging.getLogger(__name__)
    if forced_variant and forced_variant != "auto":
        if forced_variant not in variants:
            raise ValueError(f"Requested Mitsuba variant '{forced_variant}' not in {variants}")
        mi.set_variant(forced_variant)
        return mi.variant()

    if prefer_gpu:
        candidate = _preferred_cuda_variant(variants)
        if candidate:
            try:
                mi.set_variant(candidate)
                return mi.variant()
            except Exception as exc:  # pragma: no cover - runtime GPU variance
                logger.warning("CUDA variant selection failed (%s): %s", candidate, exc)
                if require_cuda:
                    raise RuntimeError(
                        "CUDA variant requested but could not be initialized. "
                        "Ensure NVIDIA driver + CUDA runtime are compatible."
                    ) from exc

    # Prefer spectral variants on CPU to avoid RGB spectrum shape mismatches.
    for candidate in [
        "llvm_ad_mono_polarized",
        "llvm_ad_spectral_polarized",
        "llvm_ad_spectral",
        "llvm_ad_rgb",
        "scalar_spectral_polarized",
        "scalar_spectral",
        "scalar_rgb",
    ]:
        if candidate in variants:
            mi.set_variant(candidate)
            return mi.variant()

    mi.set_variant(variants[0])
    return mi.variant()


def apply_mitsuba_variant(variant: str | None) -> None:
    if not variant:
        return
    try:
        import mitsuba as mi
        mi.set_variant(variant)
    except Exception:
        return
    try:
        from sionna.rt import Camera

        Camera.mi_2_sionna = (
            mi.ScalarTransform4f.rotate([0, 0, 1], 90.0)
            @ mi.ScalarTransform4f.rotate([1, 0, 0], 90.0)
        )
    except Exception:
        return


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

    raw_smi = _nvidia_smi_output()
    info["nvidia_smi"] = raw_smi
    info["nvidia"] = _parse_nvidia_smi_versions(raw_smi)
    info["optix"] = check_optix_runtime()

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

    info["gpu_memory_mb"] = get_gpu_memory_mb()

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


def get_gpu_memory_mb() -> Optional[int]:
    """Return total GPU memory in MB for the first GPU, if available."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    first = output.splitlines()[0].strip()
    try:
        return int(float(first))
    except ValueError:
        return None


def _run_nvidia_smi_query(fields: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["nvidia-smi", f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    output = result.stdout.strip()
    return output or None


def get_gpu_utilization_sample() -> Optional[Dict[str, float]]:
    output = _run_nvidia_smi_query("utilization.gpu,memory.used,memory.total")
    if not output:
        return None
    first = output.splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 3:
        return None
    try:
        return {
            "utilization_pct": float(parts[0]),
            "memory_used_mb": float(parts[1]),
            "memory_total_mb": float(parts[2]),
        }
    except ValueError:
        return None


def _nvidia_smi_output() -> Optional[str]:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    return result.stdout.strip() or result.stderr.strip() or None


def _parse_nvidia_smi_versions(raw: Optional[str]) -> Dict[str, Optional[str]]:
    versions = {"driver_version": None, "cuda_version": None}
    if not raw:
        return versions
    driver_match = re.search(r"Driver Version:\s*([0-9.]+)", raw)
    cuda_match = re.search(r"CUDA Version:\s*([0-9.]+)", raw)
    if driver_match:
        versions["driver_version"] = driver_match.group(1)
    if cuda_match:
        versions["cuda_version"] = cuda_match.group(1)
    return versions


def check_optix_runtime() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "library": "libnvoptix.so.1",
        "available": False,
        "has_optixQueryFunctionTable": None,
        "error": None,
    }
    try:
        lib = ctypes.CDLL("libnvoptix.so.1")
        info["available"] = True
    except OSError as exc:
        info["error"] = str(exc)
        return info
    try:
        getattr(lib, "optixQueryFunctionTable")
        info["has_optixQueryFunctionTable"] = True
    except AttributeError:
        info["has_optixQueryFunctionTable"] = False
    return info


class GpuMonitor:
    def __init__(self, interval_s: float = 0.5) -> None:
        self.interval_s = interval_s
        self.samples: list[Tuple[float, Dict[str, float]]] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            sample = get_gpu_utilization_sample()
            if sample:
                self.samples.append((time.time(), sample))
            time.sleep(self.interval_s)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def summary(self) -> Dict[str, Any]:
        if not self.samples:
            return {"samples": 0}
        utilizations = [s[1]["utilization_pct"] for s in self.samples if "utilization_pct" in s[1]]
        mem_used = [s[1]["memory_used_mb"] for s in self.samples if "memory_used_mb" in s[1]]
        mem_total = [s[1]["memory_total_mb"] for s in self.samples if "memory_total_mb" in s[1]]
        return {
            "samples": len(self.samples),
            "max_utilization_pct": max(utilizations) if utilizations else None,
            "max_memory_used_mb": max(mem_used) if mem_used else None,
            "memory_total_mb": max(mem_total) if mem_total else None,
            "start_time": self.samples[0][0],
            "end_time": self.samples[-1][0],
        }


def _backend_verdict(variant: Optional[str]) -> str:
    if not variant:
        return "unknown"
    if "cuda" in variant:
        return "cuda/optix"
    if "llvm" in variant or "scalar" in variant:
        return "cpu/llvm"
    return "unknown"


def gpu_smoke_test(prefer_gpu: bool = True, forced_variant: str = "auto") -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "prefer_gpu": prefer_gpu,
        "forced_variant": forced_variant,
    }
    cache_dir = os.environ.get("DRJIT_CACHE_DIR", "/tmp/drjit-cache")
    os.environ.setdefault("DRJIT_CACHE_DIR", cache_dir)
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        pass
    try:
        import mitsuba as mi
    except Exception as exc:
        result["error"] = f"mitsuba import failed: {exc}"
        return result

    variants = list(mi.variants())
    result["available_variants"] = variants
    selected = None
    if prefer_gpu and forced_variant == "auto":
        candidate = _preferred_cuda_variant(variants)
        if candidate:
            try:
                mi.set_variant(candidate)
                selected = mi.variant()
            except Exception as exc:
                result["variant_error"] = str(exc)
    if selected is None:
        try:
            selected = select_mitsuba_variant(prefer_gpu=False, forced_variant=forced_variant)
        except Exception as exc:
            result["error"] = f"mitsuba variant selection failed: {exc}"
            return result
    result["selected_variant"] = selected
    result["backend"] = _backend_verdict(selected)

    try:
        import numpy as np
        import sionna.rt as rt  # pylint: disable=import-error
        apply_mitsuba_variant(result.get("selected_variant"))
    except Exception as exc:
        result["error"] = f"sionna-rt import failed: {exc}"
        return result

    try:
        scene = rt.load_scene()
        scene.tx_array = rt.PlanarArray(
            num_rows=1,
            num_cols=1,
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
            pattern="iso",
            polarization="V",
        )
        scene.rx_array = rt.PlanarArray(
            num_rows=1,
            num_cols=1,
            vertical_spacing=0.5,
            horizontal_spacing=0.5,
            pattern="iso",
            polarization="V",
        )
        scene.add(rt.Transmitter(name="tx", position=np.array([0.0, 0.0, 3.0])))
        scene.add(rt.Receiver(name="rx", position=np.array([10.0, 0.0, 1.5])))
        t0 = time.time()
        paths = scene.compute_paths(
            max_depth=1,
            method="fibonacci",
            num_samples=512,
            los=True,
            reflection=False,
            diffraction=False,
            scattering=False,
            ris=True,
        )
        result["duration_s"] = time.time() - t0
        try:
            mask = paths.mask
            result["valid_paths"] = int(mask.numpy().sum())
        except Exception:
            result["valid_paths"] = None
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"smoke test failed: {exc}"
    return result


def diagnose_environment(
    prefer_gpu: bool = True,
    forced_variant: str = "auto",
    tensorflow_mode: str = "auto",
    run_smoke: bool = True,
) -> Dict[str, Any]:
    info = collect_environment_info()
    info["diagnose"] = {}

    rt_diag: Dict[str, Any] = {}
    raw_smi = _nvidia_smi_output()
    versions = _parse_nvidia_smi_versions(raw_smi)
    rt_diag["nvidia_smi_raw"] = raw_smi
    rt_diag["nvidia_smi_available"] = raw_smi is not None
    rt_diag["nvidia_driver_version"] = versions["driver_version"]
    rt_diag["driver_version"] = versions["driver_version"]
    rt_diag["cuda_version"] = versions["cuda_version"]
    optix_info = check_optix_runtime()
    rt_diag["optix"] = optix_info
    rt_diag["optix_symbol_ok"] = optix_info.get("has_optixQueryFunctionTable")
    rt_diag["gpu_utilization_sample"] = get_gpu_utilization_sample()
    try:
        import mitsuba as mi
        variants = list(mi.variants())
        rt_diag["mitsuba_variants"] = variants
        rt_diag["mitsuba_cuda_variants"] = [v for v in variants if "cuda" in v]
        rt_diag["mitsuba_has_cuda_variant"] = _preferred_cuda_variant(variants) is not None
        selected = None
        if prefer_gpu and forced_variant == "auto":
            candidate = _preferred_cuda_variant(variants)
            if candidate:
                try:
                    mi.set_variant(candidate)
                    selected = mi.variant()
                except Exception as exc:
                    rt_diag["variant_error"] = str(exc)
        if selected is None:
            try:
                selected = select_mitsuba_variant(prefer_gpu=False, forced_variant=forced_variant)
            except Exception as exc:
                rt_diag["variant_error"] = str(exc)
                selected = None
        rt_diag["selected_variant"] = selected
        rt_diag["backend"] = _backend_verdict(selected)
    except Exception as exc:
        rt_diag["mitsuba_error"] = str(exc)

    if tensorflow_mode != "skip":
        tf_info = configure_tensorflow_memory_growth(mode=tensorflow_mode)
        rt_diag["tensorflow"] = tf_info

    if run_smoke:
        rt_diag["gpu_smoke_test"] = gpu_smoke_test(prefer_gpu=prefer_gpu, forced_variant=forced_variant)

    actions = []
    if rt_diag.get("backend") == "cuda/optix":
        verdict = "✅ RT backend is CUDA/OptiX"
    else:
        verdict = "⚠️ RT backend is CPU/LLVM"
        actions = [
            "Verify NVIDIA driver + CUDA runtime (nvidia-smi must work).",
            "Ensure Mitsuba CUDA variants are available and selectable.",
            "Re-run `python -m app diagnose` after fixing CUDA availability.",
        ]
    smoke_err = (rt_diag.get("gpu_smoke_test") or {}).get("error", "")
    if smoke_err and "OptiX" in smoke_err:
        actions.insert(0, "OptiX init failed; update NVIDIA driver to a supported range (Dr.Jit/Mitsuba may reject CUDA 12.7 drivers).")

    info["diagnose"].update(
        {
            "runtime": rt_diag,
            "verdict": verdict,
            "actions": actions,
        }
    )
    return info


def print_diagnose_info(
    prefer_gpu: bool = True,
    forced_variant: str = "auto",
    tensorflow_mode: str = "auto",
    run_smoke: bool = True,
    json_only: bool = False,
) -> None:
    start_time = time.time()
    info = diagnose_environment(
        prefer_gpu=prefer_gpu,
        forced_variant=forced_variant,
        tensorflow_mode=tensorflow_mode,
        run_smoke=run_smoke,
    )
    wall_time_s = time.time() - start_time
    info.setdefault("diagnose", {})
    info["diagnose"]["wall_time_s"] = wall_time_s
    info["diagnose"].setdefault("runtime", {})
    info["diagnose"]["runtime"]["wall_time_s"] = wall_time_s
    from ..io import create_output_dir, save_json

    output_dir = create_output_dir("outputs")
    info["diagnose"]["output_dir"] = str(output_dir)
    save_json(output_dir / "summary.json", info)
    print(json.dumps(info, indent=2))
    if not json_only:
        verdict = info.get("diagnose", {}).get("verdict", "unknown")
        print(verdict)
