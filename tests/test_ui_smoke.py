from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def _wait_for_ready(url: str, timeout_s: float = 15.0) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            with urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Simulator not ready after {timeout_s}s")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright not installed. Install with: pip install playwright && playwright install")
        return 1

    port = 8765
    proc = subprocess.Popen(
        [sys.executable, "-m", "app", "sim", "--port", str(port), "--no-browser"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_ready(f"http://127.0.0.1:{port}/api/ping")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}", wait_until="domcontentloaded")
            page.wait_for_selector("#viewerCanvas", timeout=10000)
            screenshot_path = Path("outputs") / "_ui_smoke.png"
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
