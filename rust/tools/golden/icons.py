"""
Reference renderings of the app icon from `installer/create_icons.py` (Pillow).

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/icons.py
Writes rust/testdata/golden/icons/app_<size>.png.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

RUST = Path(__file__).resolve().parents[2]
OUT = RUST / "testdata" / "golden" / "icons"

spec = importlib.util.spec_from_file_location(
    "create_icons", RUST.parent / "installer" / "create_icons.py"
)
create_icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(create_icons)

OUT.mkdir(parents=True, exist_ok=True)
for size in (16, 32, 64, 256):
    create_icons.create_weather_icon(size).save(OUT / f"app_{size}.png", format="PNG")
    print("wrote", OUT / f"app_{size}.png")
