import os, json

code = '''"""
Pineapple Dashboard Server - REST API + static file server.
"""

import http.server, json, os, re, shutil, subprocess, sys, threading
import time, uuid, urllib.request, webbrowser
from pathlib import Path
from typing import Any

from pineapple import __version__
from pineapple._dashboard_html import DASHBOARD_HTML_CONTENT
from pineapple.detect import detect_framework, FRAMEWORK_PATTERNS
from pineapple.dockerfile import generate_dockerfile
from pineapple.builder import build_image, check_docker
from pineapple.db import (
    create_repo, get_repo, get_all_repos, update_repo_clone, set_repo_path,
    delete_repo, save_detection, get_detection, get_full_repo,
    save_dockerfile, get_dockerfile, create_build, get_build, update_build,
    save_github_token, get_github_token, delete_github_token,
    create_project, get_project, get_all_projects, delete_project, update_project,
)

STATIC_DIR = Path(__file__).parent / "static"
_build_processes: dict[str, subprocess.Popen] = {}


def _mime(path):
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {"html": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
            "js": "application/javascript; charset=utf-8", "json": "application/json",
            "png": "image/png", "svg": "image/svg+xml", "ico": "image/x-icon",
            "woff2": "font/woff2"}.get(ext, "application/octet-stream")


def _json(data, status=200):
    body = json.dumps(data, default=str).encode("utf-8")
    st = "OK" if status == 200 else "Error"
    return (f"HTTP/1.1 {status} {st}\\r\\n"
            f"Content-Type: application/json\\r\\n"
            f"Content-Length: {len(body)}\\r\\n"
            f"Access-Control-Allow-Origin: *\\r\\n"
            f"Connection: close\\r\\n\\r\\n").encode() + body


def _html(html, status=200):
    body = html.encode("utf-8")
    st = "OK" if status == 200 else "Error"
    return (f"HTTP/1.1 {status} {st}\\r\\n"
            f"Content-Type: text/html; charset=utf-8\\r\\n"
            f"Content-Length: {len(body)}\\r\\n"
            f"Connection: close\\r\\n\\r\\n").encode() + body


def _static(filepath):
    if not filepath.exists() or not filepath.is_file():
        return None
    mime = _mime(str(filepath))
    body = filepath.read_bytes()
    return (f"HTTP/1.1 200 OK\\r\\nContent-Type: {mime}\\r\\n"
            f"Content-Length: {len(body)}\\r\\nConnection: close\\r\\n\\r\\n").encode() + body


def _read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _repo_name_from_url(url):
    m = re.search(r"([^/]+?)(?:\\.git)?$", url.rstrip("/"))
    return m.group(1) if m else "unknown"


def _parse_git_progress(line):
    m = re.search(r"(\\d+)%", line)
    return float(m.group(1)) if m else 0


def _get_token_from_db():
    tok = get_github_token()
    return tok["token"] if tok else None


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _route(self, method):
        path = self.path.split("?")[0].rstrip("/")
        if not path:
            path = "/"

        try:
            # Health
            if path == "/api/health" and method == "GET":
                return self._json({"status": "ok", "version": __version__})

            # Frameworks
            if path == "/api/frameworks" and method == "GET":
                return self._json({"frameworks": sorted(FRAMEWORK_PATTERNS.keys())})

            # GitHub token
            if path == "/api/github/token" and method == "GET":
                tok = get_github_token()
                return self._json({"token": tok["token"] if tok else None,
                                   "login": tok["github_login"] if tok else None})

            if path == "/api/github/token" and method == "POST":
                body = _read_body(self)
                token = body.get("token", "").strip()
                if not token:
                    return self._json({"error": "Missing token"}, 400)
                try:
                    req = urllib.request.Request(
                        "https://api.github.com/user",
                        headers={"Authorization": "Bearer " + token,
                                 "User-Agent": "pineapple"},
                    )
                    resp = urllib.request.urlopen(req, timeout=10)
                    user = json.loads(resp.read())
                    login = user.get("login", "")
                    save_github_token(token, login)
                    return self._json({"status": "ok", "login": login})
                except urllib.error.HTTPError as e:
                    return self._json({"error": "GitHub API: " + str(e.code)}, 400)
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            if path == "/api/github/token" and method == "DELETE":
                delete_github_token()
                return self._json({"status": "deleted"})

            # GitHub repos
            if path == "/api/github/repos" and method == "GET":
                token = _get_token_from_db()
                if not token:
                    return self._json({"error": "No token"}, 401)
                try:
                    req = urllib.request.Request(
                        "https://api.github.com/user/repos?per_page=100&sort=updated",
                        headers={"Authorization": "Bearer " + token,
                                 "User-Agent": "pineapple"},
                    )
                    resp = urllib.request.urlopen(req, timeout=15)
                    data = json.loads(resp.read())
                    repos = [{
                        "id": r["id"], "name": r["name"],
                        "full_name": r["full_name"],
                        "description": r.get("description", ""),
                        "html_url": r["html_url"],
                        "clone_url": r["clone_url"],
                        "language": r.get("language"),
                        "default_branch": r.get("default_branch", "main"),
                        "private": r.get("private", False),
                        "fork": r.get("fork", False),
                    } for r in data]
                    tok = get_github_token()
                    return self._json({"repos": repos, "login": tok["github_login"] if tok else None})
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        delete_github_token()
                    return self._json({"error": "GitHub API: " + str(e.code)}, e.code)
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            # Gitignore templates
            if path == "/api/gitignore/templates" and method == "GET":
                templates = [
                    {"name": "Node", "content": "node_modules/\\ndist/\\nbuild/\\n.env\\n*.log\\n.DS_Store"},
                    {"name": "Python", "content": "__pycache__/\\n*.pyc\\n.env\\nvenv/\\n*.egg-info/\\ndist/\\nbuild/"},
                    {"name": "React", "content": "node_modules/\\ndist/\\nbuild/\\n.env\\n*.log\\n.DS_Store\\n.eslintcache"},
                    {"name": "Next.js", "content": "node_modules/\\n.next/\\nout/\\ndist/\\n.env\\n*.log\\n.DS_Store\\n*.tsbuildinfo"},
                    {"name": "Java", "content": "*.class\\n*.jar\\nbuild/\\ntarget/\\n.idea/\\n*.iml"},
                    {"name": "Go", "content": "*.exe\\n*.test\\n*.out\\nvendor/\\n.env"},
                    {"name": "Rust", "content": "target/\\n*.rs.bk\\nCargo.lock"},
                    {"name": "Docker", "content": "*.env\\n*.log\\n.DS_Store\\n.secret"},
                ]
                return self._json({"templates": templates})

            # Repos
            if path == "/api/repos" and method == "GET":
                return self._json({"repos": get_all_repos()})

            if path == "/api/repos" and method == "POST":
                body = _read_body(self)
                url = body.get("url", "").strip()
                if not url:
                    return self._json({"error": "Missing url"}, 400)
                name = _repo_name_from_url(url)
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
                            pct = _parse_git_progress(line)
                            update_repo_clone(repo["id"], "cloning", pct, log)
                        proc.wait()
                        if proc.returncode == 0:
                            update_repo_clone(repo["id"], "done", 100, log + "\\nCloned")
                        else:
                            update_repo_clone(repo["id"], "failed", 0, log, "git clone failed")
                    except FileNotFoundError:
                        update_repo_clone(repo["id"], "failed", 0, "", "git not installed")
                    except Exception as e:
                        update_repo_clone(repo["id"], "failed", 0, "", str(e))

                threading.Thread(target=_clone, daemon=True).start()
                return self._json(repo, 201)

            # Single repo
            if re.match(r"^/api/repos/[^/]+$", path) and method == "GET":
                rid = path.split("/")[3]
                result = get_full_repo(rid)
                if "error" in result:
                    return self._json(result, 404)
                return self._json(result)

            if re.match(r"^/api/repos/[^/]+$", path) and method == "DELETE":
                rid = path.split("/")[3]
                repo = get_repo(rid)
                if repo and repo.get("local_path"):
                    p = Path(repo["local_path"])
                    if p.exists():
                        shutil.rmtree(p, ignore_errors=True)
                delete_repo(rid)
                return self._json({"status": "deleted"})

            # Detect
            if re.match(r"^/api/repos/[^/]+/detect$", path) and method == "POST":
                rid = path.split("/")[3]
                repo = get_repo(rid)
                if not repo:
                    return self._json({"error": "Repo not found"}, 404)
                lp = repo.get("local_path", ".")
                if not os.path.isdir(lp):
                    return self._json({"error": "Dir not found: " + lp}, 404)
                try:
                    result = detect_framework(lp)
                    saved = save_detection(rid, result)
                    return self._json({"detection": saved})
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            # Generate
            if re.match(r"^/api/repos/[^/]+/generate$", path) and method == "POST":
                rid = path.split("/")[3]
                repo = get_repo(rid)
                if not repo:
                    return self._json({"error": "Repo not found"}, 404)
                lp = repo.get("local_path", ".")
                det = get_detection(rid)
                if not det:
                    return self._json({"error": "No detection. Scan first."}, 400)
                try:
                    df = generate_dockerfile(det, build_context=lp)
                    saved = save_dockerfile(rid, df)
                    return self._json({"dockerfile": df})
                except Exception as e:
                    return self._json({"error": str(e)}, 500)

            # Build
            if re.match(r"^/api/repos/[^/]+/build$", path) and method == "POST":
                rid = path.split("/")[3]
                body = _read_body(self)
                repo = get_repo(rid)
                if not repo:
                    return self._json({"error": "Repo not found"}, 404)
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

            # Build status
            if path.startswith("/api/builds/") and method == "GET":
                bid = path.split("/")[3]
                b = get_build(bid)
                if not b:
                    return self._json({"error": "Build not found"}, 404)
                return self._json(b)

            # Projects
            if path == "/api/projects" and method == "GET":
                return self._json({"projects": get_all_projects()})

            if path == "/api/projects" and method == "POST":
                body = _read_body(self)
                name = body.get("name", "").strip()
                if not name:
                    return self._json({"error": "Missing name"}, 400)
                desc = body.get("description", "")
                gitignore = body.get("gitignore", "")
                repo_id = body.get("repo_id")
                projects_dir = Path.home() / ".pineapple" / "projects"
                projects_dir.mkdir(parents=True, exist_ok=True)
                safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
                lp = str(projects_dir / safe)
                if gitignore:
                    os.makedirs(lp, exist_ok=True)
                    with open(os.path.join(lp, ".gitignore"), "w") as f:
                        f.write(gitignore + "\\n")
                    with open(os.path.join(lp, "README.md"), "w") as f:
                        f.write("# " + name + "\\n\\n" + desc + "\\n")
                proj = create_project(name, desc, repo_id, gitignore)
                if repo_id:
                    update_project(proj["id"], repo_id=repo_id)
                return self._json(proj, 201)

            if re.match(r"^/api/projects/[^/]+$", path) and method == "GET":
                pid = path.split("/")[3]
                proj = get_project(pid)
                if not proj:
                    return self._json({"error": "Not found"}, 404)
                result = {"project": proj}
                if proj.get("repo_id"):
                    result["repo"] = get_full_repo(proj["repo_id"])
                return self._json(result)

            if re.match(r"^/api/projects/[^/]+$", path) and method == "DELETE":
                pid = path.split("/")[3]
                delete_project(pid)
                return self._json({"status": "deleted"})

            # Static files (React SPA)
            if path == "/" or path == "/dashboard":
                idx = STATIC_DIR / "index.html"
                if idx.exists():
                    return self._raw(_html(idx.read_text("utf-8")))
                return self._raw(_html(DASHBOARD_HTML_CONTENT))

            if STATIC_DIR.exists():
                fp = STATIC_DIR / path.lstrip("/")
                resp = _static(fp)
                if resp:
                    return self._raw(resp)
                idx = STATIC_DIR / "index.html"
                if idx.exists() and not path.startswith("/api/"):
                    return self._raw(_html(idx.read_text("utf-8")))

            return self._json({"error": "Not found"}, 404)

        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def do_DELETE(self):
        self._route("DELETE")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _raw(self, data):
        self.wfile.write(data)

    def _json(self, data, status=200):
        self._raw(_json(data, status))

    def _html(self, html, status=200):
        self._raw(_html(html, status))


def _find_free_port(start=8765, max_attempts=100):
    import socket
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def run_dashboard(port=0, open_browser=True):
    actual_port = _find_free_port(port or 8765)
    if actual_port == 0:
        print("No free port", file=sys.stderr)
        return 1
    server = http.server.HTTPServer(("127.0.0.1", actual_port), Handler)
    url = f"http://localhost:{actual_port}"
    Path("/tmp/pineapple-clones").mkdir(parents=True, exist_ok=True)
    print(f"  Pineapple dashboard at {url}", file=sys.stderr)
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
'''

path = '/home/madeb/pineapple/src/pineapple/server.py'
with open(path, 'w') as f:
    f.write(code)
print('Wrote server.py,', len(code), 'chars')

# Verify syntax
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('Syntax: OK')
except py_compile.PyCompileError as e:
    print('Syntax ERROR:', e)
