#!/usr/bin/env python
"""stage_web.py - assemble the RSBV (browser version) site into one folder
and optionally serve it locally.

Standalone by design, like every script in tools/: stdlib only, no imports
from the app. It does the same copy the GitHub Pages workflow will do:

    web/                      -> <out>/            (the pages themselves)
    models/ + parsers/ (*.py) -> <out>/py/shared.zip  (unpacked by Pyodide)
    soundfonts/recall_score_sounds.sf2 and web/sf/*.sf2 -> <out>/sf/
                                 plus <out>/sf/index.json listing them

With --scores (local testing only - never for a public deploy), it also
copies every MusicXML file in files/, examples/ and tests/fixtures/ into
<out>/scores/ with a scores/index.json, so the Phase 0 parse spike can
benchmark them without a file picker.

Usage (from the repo root):

    python tools/stage_web.py                 # stage into build/rsbv_site
    python tools/stage_web.py --scores        # ... plus the score corpus
    python tools/stage_web.py --scores --serve 8000
"""
import argparse
import functools
import http.server
import json
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_PACKAGES = ("models", "parsers")
MUSICXML_SUFFIXES = {".musicxml", ".xml", ".mxl"}
SCORE_DIRS = ("files", "examples", "tests/fixtures")


def stage(out: Path, with_scores: bool) -> None:
    web = REPO_ROOT / "web"
    if not web.is_dir():
        sys.exit(f"[ERROR] {web} not found")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(web, out, ignore=shutil.ignore_patterns("__pycache__", "*.sf2", "CLAUDE.md"))

    py_dir = out / "py"
    py_dir.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(py_dir / "shared.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for package in SHARED_PACKAGES:
            for path in sorted((REPO_ROOT / package).glob("*.py")):
                zf.write(path, f"{package}/{path.name}")
                count += 1
    print(f"[OK] py/shared.zip: {count} files from {', '.join(SHARED_PACKAGES)}")

    sf_dir = out / "sf"
    sf_dir.mkdir(exist_ok=True)
    sf_sources = [REPO_ROOT / "soundfonts" / "recall_score_sounds.sf2"]
    sf_sources += sorted((web / "sf").glob("*.sf2")) if (web / "sf").is_dir() else []
    sf_names = []
    for src in sf_sources:
        if src.is_file():
            shutil.copy2(src, sf_dir / src.name)
            sf_names.append(src.name)
        else:
            print(f"[WARN] SoundFont not found, skipped: {src}")
    (sf_dir / "index.json").write_text(json.dumps(sf_names, indent=1), encoding="utf-8")
    print(f"[OK] sf/: {', '.join(sf_names) or 'none'}")

    if with_scores:
        scores_dir = out / "scores"
        scores_dir.mkdir(exist_ok=True)
        entries = []
        for rel in SCORE_DIRS:
            for path in sorted((REPO_ROOT / rel).glob("*")):
                if path.suffix.lower() not in MUSICXML_SUFFIXES:
                    continue
                name = f"{rel.replace('/', '_')}__{path.name}"
                shutil.copy2(path, scores_dir / name)
                entries.append({"name": name, "label": f"{rel}/{path.name}",
                                "bytes": path.stat().st_size})
        (scores_dir / "index.json").write_text(json.dumps(entries, indent=1), encoding="utf-8")
        print(f"[OK] scores/: {len(entries)} MusicXML files")

    print(f"[OK] staged into {out}")


def serve(out: Path, port: int) -> None:
    class Handler(http.server.SimpleHTTPRequestHandler):
        extensions_map = {
            **http.server.SimpleHTTPRequestHandler.extensions_map,
            ".js": "text/javascript", ".mjs": "text/javascript",
            ".wasm": "application/wasm", ".sf2": "application/octet-stream",
        }

        def end_headers(self):
            # Local testing should always see the freshly staged files.
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

    handler = functools.partial(Handler, directory=str(out))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"[OK] serving {out} at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(REPO_ROOT / "build" / "rsbv_site"))
    parser.add_argument("--scores", action="store_true",
                        help="also copy the local MusicXML corpus (local testing only)")
    parser.add_argument("--serve", type=int, metavar="PORT",
                        help="serve the staged folder on 127.0.0.1:PORT afterwards")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    stage(out, args.scores)
    if args.serve:
        serve(out, args.serve)


if __name__ == "__main__":
    main()
