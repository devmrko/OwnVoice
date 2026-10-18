"""Verify packaged UI assets and imports without the source checkout on sys.path."""

import subprocess
import tempfile
import zipfile
from pathlib import Path

wheels = sorted(Path("dist").glob("ownvoice-*.whl"))
if not wheels:
    raise SystemExit("Run uv build first")
with tempfile.TemporaryDirectory() as folder:
    with zipfile.ZipFile(wheels[-1]) as wheel:
        for asset in ("index.html", "app.js", "style.css"):
            assert f"ownvoice/static/{asset}" in wheel.namelist()
        wheel.extractall(folder)
    code = 'from pathlib import Path; import ownvoice; from ownvoice.app import create_app; assert (Path(ownvoice.__file__).parent / "static/index.html").is_file()'
    import os
    import sys

    subprocess.run(
        [sys.executable, "-c", code], cwd=folder, env={**os.environ, "PYTHONPATH": folder}, check=True
    )
print("Wheel assets and imports: OK")
