"""
Tests for clone + detection flow.
"""

import os
import re
import shutil
import subprocess
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pineapple.detect import detect_framework
from pineapple.dockerfile import generate_dockerfile

TEST_REPO = "https://github.com/octopacket/octoflow-build-test.git"


def test_git_available():
    result = subprocess.run(["git", "--version"], capture_output=True, text=True)
    assert result.returncode == 0, "git is not installed"
    print(f"  OK git: {result.stdout.strip()}")


def test_clone_and_parse_progress():
    dest = "/tmp/pineapple-test-clone"
    if os.path.exists(dest):
        shutil.rmtree(dest)

    proc = subprocess.Popen(
        ["git", "clone", "--progress", "--depth", "1", TEST_REPO, dest],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    log = ""
    max_progress = 0
    for line in iter(proc.stdout.readline, ""):
        log += line
        m = re.search(r"(\d+)%", line)
        if m:
            max_progress = max(max_progress, float(m.group(1)))
    proc.wait()
    assert proc.returncode == 0, f"Clone failed: {log[-300:]}"
    assert os.path.exists(os.path.join(dest, ".git"))
    print(f"  OK Clone successful (progress reached {max_progress:.0f}%)")
    return dest


def test_detection(project_dir):
    result = detect_framework(project_dir)
    assert result["framework"] != "unknown"
    print(f"  OK Detected: {result['framework']} ({result['type']})")
    return result


def test_dockerfile_generation(detection, project_dir):
    df = generate_dockerfile(detection, build_context=project_dir)
    assert "FROM" in df
    lines = df.count("\n") + 1
    print(f"  OK Dockerfile generated ({lines} lines)")
    return df


def test_package_manager_detection(project_dir):
    from pineapple.detect import detect_package_manager
    pm = detect_package_manager(project_dir)
    assert pm in ["pnpm", "yarn", "npm"]
    print(f"  OK Package manager: {pm}")


def test_api_endpoints():
    import threading, time, urllib.request, socket
    from pineapple.server import run_dashboard

    # Find free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    t = threading.Thread(target=lambda: run_dashboard(port=port, open_browser=False))
    t.daemon = True
    t.start()
    time.sleep(0.5)

    base = f"http://localhost:{port}"

    def api(method, path, body=None):
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(
            base + path, data=data, method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        return json.loads(urllib.request.urlopen(req).read())

    # Health
    data = api("GET", "/api/health")
    assert data["status"] == "ok"
    print(f"  OK API server running (v{data['version']})")

    # Frameworks
    data = api("GET", "/api/frameworks")
    assert len(data["frameworks"]) > 0
    print(f"  OK {len(data['frameworks'])} frameworks")

    # Create repo
    repo = api("POST", "/api/repos", {"url": TEST_REPO})
    assert repo["clone_status"] in ("cloning", "done")
    print(f"  OK Repo created: {repo['name']} (status: {repo['clone_status']})")

    # Wait for clone
    for _ in range(30):
        data = api("GET", f"/api/repos/{repo['id']}")
        r = data.get("repo", {})
        if r.get("clone_status") == "done":
            print(f"  OK Clone completed")
            if data.get("detection"):
                print(f"  OK Detection: {data['detection']['framework']}")
            break
        elif r.get("clone_status") == "failed":
            print(f"  FAIL Clone error: {r.get('clone_error')}")
            break
        time.sleep(1)

    # Cleanup
    api("DELETE", f"/api/repos/{repo['id']}")
    print(f"  OK Cleanup done")
    print(f"  OK All API tests passed")


if __name__ == "__main__":
    print("Pineapple Clone + Detection Tests")
    print("=" * 40)
    test_git_available()
    proj = test_clone_and_parse_progress()
    det = test_detection(proj)
    test_dockerfile_generation(det, proj)
    test_package_manager_detection(proj)
    test_api_endpoints()
    print()
    print("All tests passed!")
