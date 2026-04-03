from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List


def _float_attr(node: ET.Element, name: str, default: float = 0.0) -> float:
    try:
        return float(node.attrib.get(name, default))
    except Exception:
        return float(default)


def _parse_transform_ops(transform: ET.Element | None) -> List[Dict[str, Any]]:
    if transform is None:
        return []

    ops: List[Dict[str, Any]] = []
    for child in list(transform):
        tag = (child.tag or "").lower()
        if tag == "translate":
            ops.append(
                {
                    "type": "translate",
                    "value": [
                        _float_attr(child, "x"),
                        _float_attr(child, "y"),
                        _float_attr(child, "z"),
                    ],
                }
            )
        elif tag == "scale":
            uniform = child.attrib.get("value")
            if uniform is not None:
                try:
                    s = float(uniform)
                except Exception:
                    s = 1.0
                value = [s, s, s]
            else:
                value = [
                    _float_attr(child, "x", 1.0),
                    _float_attr(child, "y", 1.0),
                    _float_attr(child, "z", 1.0),
                ]
            ops.append({"type": "scale", "value": value})
        elif tag == "rotate":
            axis = [
                _float_attr(child, "x"),
                _float_attr(child, "y"),
                _float_attr(child, "z"),
            ]
            if any(abs(v) > 0.0 for v in axis):
                ops.append(
                    {
                        "type": "rotate",
                        "axis": axis,
                        "angle_deg": _float_attr(child, "angle"),
                    }
                )
        elif tag == "matrix":
            raw = (child.attrib.get("value") or "").replace(",", " ").split()
            try:
                values = [float(v) for v in raw]
            except Exception:
                values = []
            if len(values) == 16:
                ops.append({"type": "matrix", "value": values})
    return ops


def load_scene_shape_entries(scene_xml: Path) -> List[Dict[str, Any]]:
    try:
        root = ET.parse(scene_xml).getroot()
    except Exception:
        return []

    entries: List[Dict[str, Any]] = []
    for shape in root.findall("shape"):
        string_node = shape.find("string[@name='filename']")
        if string_node is None:
            continue
        rel_path = (string_node.attrib.get("value") or "").strip()
        if not rel_path:
            continue
        entries.append(
            {
                "shape_id": shape.attrib.get("id"),
                "source_file": rel_path,
                "transform_ops": _parse_transform_ops(shape.find("transform[@name='to_world']")),
            }
        )
    return entries
