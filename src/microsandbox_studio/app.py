import os
from pathlib import Path

import webview
from microsandbox._runtime import msb_path as bundled_msb_path

from .api import Api


def main() -> None:
    frontend = Path(__file__).with_name("frontend") / "index.html"
    if not frontend.exists():
        raise SystemExit("Frontend missing. Please run `npm install && npm run build` in frontend/ first.")
    os.environ.setdefault("MSB_PATH", str(bundled_msb_path()))
    api = Api()
    api._window = webview.create_window(
        "Microsandbox Studio",
        str(frontend),
        js_api=api,
        text_select=True,
        width=1440,
        height=900,
        min_size=(420, 560),
        background_color="#08080B",
    )
    webview.start(http_server=True)
