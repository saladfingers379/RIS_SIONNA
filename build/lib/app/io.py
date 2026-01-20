import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
import numpy as np


def generate_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def create_output_dir(base_dir: str, run_id: Optional[str] = None) -> Path:
    run_id = run_id or generate_run_id()
    root = Path(base_dir) / run_id
    (root / "plots").mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(parents=True, exist_ok=True)
    return root


def find_latest_output_dir(base_dir: str) -> Optional[Path]:
    root = Path(base_dir)
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")]
    if not candidates:
        return None
    return sorted(candidates)[-1]


def save_yaml(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _json_default(obj: Any):
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (np.generic,)):
        return obj.item()
    if hasattr(obj, "tolist"):
        return obj.tolist()
    try:
        return float(obj)
    except Exception:
        return str(obj)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=_json_default)
