import sys
from pathlib import Path

# web/py/web_api.py runs inside Pyodide in the browser; tests import it directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web" / "py"))
