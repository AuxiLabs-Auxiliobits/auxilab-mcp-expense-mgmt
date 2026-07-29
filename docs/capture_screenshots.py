#!/usr/bin/env python3
"""Regenerate the README screenshots and the animated demo.

    pip install playwright pillow
    python -m playwright install chromium
    python docs/capture_screenshots.py

Starts the real Gradio app against a throwaway seeded database, drives each tab with a
headless browser, and writes PNGs plus an animated GIF into ``docs/images/``.

These extra packages are deliberately NOT in ``requirements-dev.txt``: they are a
maintainer tool for refreshing documentation, not something a contributor needs to run the
tests. Regenerate after any visible UI change.
"""

from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IMAGES = REPO / "docs" / "images"
#: Tall enough that a tab's inputs and its results both fit above the fold.
VIEWPORT = {"width": 1360, "height": 1000}

#: (tab label, run-button label, output PNG stem). Labels must match app.build_ui().
TABS = [
    ("1 · Policy Checker", "Check policy", "policy-checker"),
    ("2 · Receipt Parser", "Parse receipt", "receipt-parser"),
    ("3 · Category Classifier", "Classify", "category-classifier"),
    ("4 · Duplicate Detector", "Check for duplicates", "duplicate-detector"),
    ("5 · Report Summariser", "Summarise", "report-summariser"),
]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def capture() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed. Run:")
        print("    pip install playwright pillow && python -m playwright install chromium")
        return 1

    # A throwaway database keeps whatever the maintainer has locally out of the shots and
    # guarantees the seeded duplicate pair is present for tab 4. The directory name is
    # fixed rather than random so the path shown in the status bar looks the same in every
    # regenerated screenshot.
    scratch = Path(tempfile.gettempdir()) / "expense-compliance-demo"
    scratch.mkdir(parents=True, exist_ok=True)
    for stale in scratch.glob("sqlite.db*"):
        stale.unlink()
    os.environ["EXPENSE_DB_PATH"] = str(scratch / "sqlite.db")
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
    sys.path.insert(0, str(REPO))

    import app

    IMAGES.mkdir(parents=True, exist_ok=True)
    port = free_port()
    ui = app.build_ui()
    options = app.launch_options() | {"server_port": port, "quiet": True}
    ui.launch(prevent_thread_lock=True, inbrowser=False, **options)

    written: list[Path] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(1500)

            for tab_label, button_label, stem in TABS:
                page.get_by_role("tab", name=tab_label).click()
                page.wait_for_timeout(400)
                page.get_by_role("button", name=button_label, exact=True).click()
                # Results render asynchronously; settle before shooting.
                page.wait_for_timeout(2500)
                # Clicking a button near the foot of a tab scrolls it into view, which
                # would push the page heading and tab bar out of the capture.
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(400)

                target = IMAGES / f"{stem}.png"
                page.screenshot(path=str(target))
                written.append(target)
                size_kb = target.stat().st_size // 1024
                print(f"  wrote docs/images/{target.name} ({size_kb} KB)")

            browser.close()
    finally:
        ui.close()

    build_gif(written)
    return 0


def build_gif(frames: list[Path]) -> None:
    """Assemble the PNGs into a looping slideshow."""
    try:
        from PIL import Image
    except ImportError:
        print("  (pillow not installed — skipping demo.gif)")
        return

    if not frames:
        return

    images = []
    for path in frames:
        img = Image.open(path).convert("RGB")
        # Halve the 2x-scaled captures: readable in a README, a fraction of the bytes.
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        images.append(img)

    out = IMAGES / "demo.gif"
    images[0].save(
        out,
        save_all=True,
        append_images=images[1:],
        duration=2200,
        loop=0,
        optimize=True,
    )
    print(f"  wrote docs/images/{out.name} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    raise SystemExit(capture())
