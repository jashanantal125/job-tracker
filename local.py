"""Run the whole tracker on your own computer with one command.

    python3 local.py            # then open http://localhost:8000

- fetches internships right away, then again every 30 minutes
- serves the website from public/ on http://localhost:8000
- the site shows a "Refresh now" button that triggers a fetch on demand

Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import threading
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scraper"))

from tracker import run as tracker_run  # noqa: E402

_lock = threading.Lock()
_state = {"running": False, "last_run": None}


def fetch_now(deadline: float) -> bool:
    """Run the tracker once. Returns False if a run is already in progress."""
    if not _lock.acquire(blocking=False):
        return False
    _state["running"] = True
    try:
        print("Fetching internships…", flush=True)
        tracker_run.main(["--deadline", str(deadline)])
    except Exception as e:  # noqa: BLE001 - keep the server alive
        print(f"Fetch failed: {e}", flush=True)
    finally:
        _state.update(running=False, last_run=time.time())
        _lock.release()
    return True


def scheduler(interval_min: float, deadline: float) -> None:
    while True:
        fetch_now(deadline)
        time.sleep(interval_min * 60)


class Handler(SimpleHTTPRequestHandler):
    deadline = 120.0

    def _json(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            return self._json(200, _state)
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/refresh"):
            if _state["running"]:
                return self._json(202, {"started": False, "running": True})
            threading.Thread(target=fetch_now, args=(self.deadline,), daemon=True).start()
            return self._json(202, {"started": True, "running": True})
        self.send_error(404)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):  # keep the console readable
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--every", type=float, default=30, help="minutes between automatic fetches")
    ap.add_argument("--deadline", type=float, default=120, help="max seconds per fetch")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    Handler.deadline = args.deadline
    threading.Thread(target=scheduler, args=(args.every, args.deadline), daemon=True).start()

    handler = functools.partial(Handler, directory=str(ROOT / "public"))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://localhost:{args.port}"
    print(f"Site running at {url}  (fetching every {args.every:g} min, Ctrl+C to stop)", flush=True)
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
