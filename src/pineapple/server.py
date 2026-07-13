"""Pineapple Dashboard Server."""
import http.server, json, os, re, shutil, subprocess, sys, threading
import time, uuid, urllib.request, webbrowser, secrets
from pathlib import Path
from typing import Any

from pineapple import __version__
from pineapple._dashboard_html import DASHBOARD_HTML_CONTENT
from pineapple.detect import detect_framework, FRAMEWORK_PATTERNS
from pineapple.dockerfile import generate_dockerfile
from pineapple.builder import build_image, check_docker

try:
    from pineapple.db import (
        create_repo, get_repo, get_all_repos, update_repo_clone, set_repo_path,
        delete_repo, save_detection, get_detection, get_full_repo,
        save_dockerfile, get_dockerfile, create_build, get_build, update_build,
        save_github_token, get_github_token, delete_github_token,
        create_project, get_project, get_all_projects, delete_project, update_project,
    )
except ImportError:
    # Fallback if db module not available
    pass

STATIC_DIR = Path(__file__).parent / "static"
SERVER_PORT = 8765
_build_processes = {}
_oauth_states = {}


def _mime(path):
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
            "js": "application/javascript; charset=utf-8", "json": "application/json",
            "png": "image/png", "svg": "image/svg+xml", "ico": "image/x-icon"
            }.get(ext, "application/octet-stream")

def _json(data, status=200):
    body = json.dumps(data, default=str).encode("utf-8")
    st = "OK" if status == 200 else "Error"
    return (f"HTTP/1.1 {status} {st}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n\r\n").encode() + body

def _html(data, status=200):
    body = data.encode("utf-8") if isinstance(data, str) else data
    st = "OK" if status == 200 else "Error"
    return (f"HTTP/1.1 {status} {st}\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n").encode() + (body if isinstance(data, str) else data)

def _static(filepath):
    if not filepath.exists() or not filepath.is_file():
        return None
    body = filepath.read_bytes()
    return (f"HTTP/1.1 200 OK\r\nContent-Type: {_mime(str(filepath))}\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body

def _read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0: return {}
    try: return json.loads(handler.rfile.read(length))
    except: return {}

def _repo_name(url):
    m = re.search(r"([^/]+?)(?:\.git)?$", url.rstrip("/"))
    return m.group(1) if m else "unknown"

def _pct(line):
    m = re.search(r"(\d+)%", line)
    return float(m.group(1)) if m else 0

def _add_gitignore(path, framework):
    """Add .gitignore to a project if one doesn't exist."""
    gi = os.path.join(path, ".gitignore")
    if os.path.exists(gi):
        return  # Already has one
    templates = {
        "node": "node_modules/\ndist/\nbuild/\n.env\n*.log\n.DS_Store\n\n# Editor\n.vscode/\n.idea/\n*.swp\n*.swo\n",
        "python": "__pycache__/\n*.pyc\n*.pyo\n.env\nvenv/\n.venv/\n*.egg-info/\ndist/\nbuild/\n.idea/\n.vscode/\n",
        "go": "*.exe\n*.test\n*.out\nvendor/\n.env\n.idea/\n.vscode/\n",
        "rust": "target/\n*.rs.bk\nCargo.lock\n.idea/\n.vscode/\n",
        "ruby": "*.gem\n.bundle/\nvendor/bundle\n.env\n*.log\n.idea/\n.vscode/\n",
        "php": "vendor/\n*.lock\n.env\n.DS_Store\n.idea/\n.vscode/\n",
        "static": ".DS_Store\n.env\n",
    }
    content = templates.get(framework, "node_modules/\n.env\n.DS_Store\n")
    with open(gi, "w") as f:
        f.write(content)


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _route(self, method):
        path = self.path.split("?")[0].rstrip("/")
        if not path: path = "/"

        try:
            # ── Health ──
            if path == "/api/health" and method == "GET":
                return self._json({"status": "ok", "version": __version__})

            # ── Frameworks ──
            if path == "/api/frameworks" and method == "GET":
                return self._json({"frameworks": sorted(FRAMEWORK_PATTERNS.keys())})

            # ── Gitignore ──
            if path == "/api/gitignore/templates" and method == "GET":
                return self._json({"templates": [
                    {"name": "Node", "content": "node_modules/\ndist/\nbuild/\n.env\n*.log\n.DS_Store"},
                    {"name": "Python", "content": "__pycache__/\n*.pyc\n.env\nvenv/\n*.egg-info/\ndist/\nbuild/"},
                    {"name": "React", "content": "node_modules/\ndist/\n.env\n*.log\n.DS_Store"},
                    {"name": "Go", "content": "*.exe\n*.test\n*.out\nvendor/\n.env"},
                    {"name": "Rust", "content": "target/\nCargo.lock"},
                ]})

            # ── GitHub Accounts ──
            if path == "/api/github/accounts" and method == "GET":
                from pineapple.db import get_all_github_accounts
                accounts = get_all_github_accounts()
                return self._json({"accounts": accounts})

            if path.startswith("/api/github/accounts/") and path.endswith("/repos") and method == "GET":
                aid = path.split("/")[4]
                from pineapple.db import get_github_account
                acct = get_github_account(aid)
                if not acct:
                    return self._json({"error": "Account not found"}, 404)
                token = acct.get("access_token")
                if not token:
                    return self._json({"error": "No token"}, 401)
                try:
                    req = urllib.request.Request(
                        "https://api.github.com/installation/repositories",
                        headers={"Authorization": f"Bearer {token}",
                                 "Accept": "application/vnd.github.v3+json",
                                 "User-Agent": "pineapple"},
                    )
                    data = json.loads(urllib.request.urlopen(req, timeout=15).read())
                    repos = [{
                        "id": r["id"], "name": r["name"],
                        "full_name": r["full_name"],
                        "description": r.get("description", "") or "",
                        "html_url": r["html_url"], "clone_url": r["clone_url"],
                        "language": r.get("language") or "",
                        "private": r.get("private", False),
                    } for r in data.get("repositories", [])]
                    return self._json({"repos": repos, "account": acct["account_name"]})
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        return self._json({"error": "Token expired"}, 401)
                    return self._json({"error": f"GitHub API: {e.code}"}, e.code)
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            if path.startswith("/api/github/accounts/") and method == "DELETE":
                aid = path.split("/")[4]
                from pineapple.db import delete_github_account
                delete_github_account(aid)
                return self._json({"status": "deleted"})
            # ── Repos ──
            if path == "/api/repos" and method == "GET":
                return self._json({"repos": get_all_repos()})

            if path == "/api/repos" and method == "POST":
                body = _read_body(self)
                url = body.get("url", "").strip()
                if not url:
                    return self._json({"error": "Missing url"}, 400)
                name = _repo_name(url)
                repo = create_repo(url, name)
                clone_dir = Path("/tmp/pineapple-clones")
                clone_dir.mkdir(parents=True, exist_ok=True)
                dest = clone_dir / f"{name}-{uuid.uuid4().hex[:6]}"
                set_repo_path(repo["id"], str(dest))
                update_repo_clone(repo["id"], "cloning")
                repo = get_repo(repo["id"])

                def _clone():
                    try:
                        proc = subprocess.Popen(
                            ["git", "clone", "--progress", url, str(dest)],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1,
                        )
                        log = ""
                        for line in iter(proc.stdout.readline, ""):
                            log += line
                            update_repo_clone(repo["id"], "cloning", _pct(line), log)
                        proc.wait()
                        if proc.returncode == 0:
                            update_repo_clone(repo["id"], "done", 100, log + "\nCloned")
                            # Auto-detect and add .gitignore if missing
                            try:
                                result = detect_framework(str(dest))
                                save_detection(repo["id"], result)
                                _add_gitignore(str(dest), result.get("language", "node"))
                            except:
                                pass
                        else:
                            update_repo_clone(repo["id"], "failed", 0, log, "Clone failed")
                    except FileNotFoundError:
                        update_repo_clone(repo["id"], "failed", 0, "", "git not found")
                    except Exception as e:
                        update_repo_clone(repo["id"], "failed", 0, "", str(e))

                threading.Thread(target=_clone, daemon=True).start()
                return self._json(repo, 201)

            if re.match(r"^/api/repos/[^/]+$", path) and method == "GET":
                rid = path.split("/")[3]
                result = get_full_repo(rid)
                return self._json(result, 404 if "error" in result else 200)

            if re.match(r"^/api/repos/[^/]+$", path) and method == "DELETE":
                rid = path.split("/")[3]
                repo = get_repo(rid)
                if repo and repo.get("local_path"):
                    p = Path(repo["local_path"])
                    if p.exists(): shutil.rmtree(p, ignore_errors=True)
                delete_repo(rid)
                return self._json({"status": "deleted"})

            # ── Detect ──
            if re.match(r"^/api/repos/[^/]+/detect$", path) and method == "POST":
                rid = path.split("/")[3]
                repo = get_repo(rid)
                if not repo: return self._json({"error": "Not found"}, 404)
                lp = repo.get("local_path", ".")
                if not os.path.isdir(lp): return self._json({"error": "Dir not found"}, 404)
                try:
                    result = detect_framework(lp)
                    saved = save_detection(rid, result)
                    return self._json({"detection": saved})
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            # ── Generate ──
            if re.match(r"^/api/repos/[^/]+/generate$", path) and method == "POST":
                rid = path.split("/")[3]
                repo = get_repo(rid)
                if not repo: return self._json({"error": "Not found"}, 404)
                lp = repo.get("local_path", ".")
                det = get_detection(rid)
                if not det: return self._json({"error": "Scan first"}, 400)
                try:
                    df = generate_dockerfile(det, build_context=lp)
                    save_dockerfile(rid, df)
                    return self._json({"dockerfile": df})
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            # ── Build ──
            if re.match(r"^/api/repos/[^/]+/build$", path) and method == "POST":
                rid = path.split("/")[3]
                body = _read_body(self)
                repo = get_repo(rid)
                if not repo: return self._json({"error": "Not found"}, 404)
                lp = repo.get("local_path", ".")
                tag = body.get("tag", Path(lp).name + ":latest")
                build = create_build(rid, tag)

                def _run_build():
                    try:
                        proc = subprocess.Popen(
                            ["docker", "build", "-t", tag, lp],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1,
                        )
                        _build_processes[build["id"]] = proc
                        log = ""
                        for line in iter(proc.stdout.readline, ""):
                            log += line
                            update_build(build["id"], "running", log)
                        proc.wait()
                        update_build(build["id"], "done", log, proc.returncode == 0)
                    except Exception as e:
                        update_build(build["id"], "failed", str(e), False)

                threading.Thread(target=_run_build, daemon=True).start()
                return self._json(build, 201)

            if path.startswith("/api/builds/") and method == "GET":
                bid = path.split("/")[3]
                b = get_build(bid)
                return self._json(b, 404 if not b else 200)

            # ── Projects ──
            if path == "/api/projects" and method == "GET":
                return self._json({"projects": get_all_projects()})

            if path == "/api/projects" and method == "POST":
                body = _read_body(self)
                name = body.get("name", "").strip()
                if not name: return self._json({"error": "Name required"}, 400)
                repo_id = body.get("repo_id")
                proj = create_project(name, body.get("description", ""), repo_id, body.get("gitignore", ""))
                if repo_id:
                    update_project(proj["id"], repo_id=repo_id)
                return self._json(proj, 201)

            if re.match(r"^/api/projects/[^/]+$", path) and method == "GET":
                pid = path.split("/")[3]
                proj = get_project(pid)
                if not proj: return self._json({"error": "Not found"}, 404)
                result = {"project": proj}
                if proj.get("repo_id"):
                    result["repo"] = get_full_repo(proj["repo_id"])
                return self._json(result)

            if re.match(r"^/api/projects/[^/]+$", path) and method == "DELETE":
                delete_project(path.split("/")[3])
                return self._json({"status": "deleted"})

            # ── Static files (SPA) ──
            if path == "/" or path == "/dashboard":
                idx = STATIC_DIR / "index.html"
                return self._raw(_html(idx.read_text("utf-8") if idx.exists() else DASHBOARD_HTML_CONTENT))

            if STATIC_DIR.exists():
                fp = STATIC_DIR / path.lstrip("/")
                resp = _static(fp)
                if resp: return self._raw(resp)

            return self._json({"error": "Not found"}, 404)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._json({"error": str(e)}, 500)

    def do_GET(self): self._route("GET")
    def do_POST(self): self._route("POST")
    def do_DELETE(self): self._route("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _raw(self, data): self.wfile.write(data)
    def _json(self, data, status=200): self._raw(_json(data, status))


def _find_free_port(start=8765):
    import socket
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0

def run_dashboard(port=0, open_browser=True):
    global SERVER_PORT
    actual_port = _find_free_port(port or 8765)
    if actual_port == 0:
        print("No free port", file=sys.stderr)
        return 1
    SERVER_PORT = actual_port
    server = http.server.HTTPServer(("127.0.0.1", actual_port), Handler)
    url = f"http://localhost:{actual_port}"
    Path("/tmp/pineapple-clones").mkdir(parents=True, exist_ok=True)
    print(f"  Pineapple at {url}", file=sys.stderr)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    print("  Ctrl+C to stop", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    return 0

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", "-p", type=int, default=8765)
    p.add_argument("--no-open", action="store_true")
    args = p.parse_args()
    return run_dashboard(port=args.port, open_browser=not args.no_open)

if __name__ == "__main__":
    sys.exit(main())
