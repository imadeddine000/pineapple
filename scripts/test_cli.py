#!/usr/bin/env python3
"""
Quick CLI smoke test — run without building a .deb.

Usage:
    PYTHONPATH=src python3 scripts/test_cli.py
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.environ.copy()
ENV["PYTHONPATH"] = os.path.join(ROOT, "src")

PINEAPPLE = [sys.executable, "-m", "pineapple"]

passed = 0
failed = 0

def run(name, args, expect_code=0, expect_in=None):
    global passed, failed
    result = subprocess.run(
        PINEAPPLE + args,
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=10,
    )
    ok = result.returncode == expect_code
    if expect_in and expect_in not in result.stdout + result.stderr:
        ok = False
    status = "✓" if ok else "✗"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  {status} {name}")
    if not ok:
        print(f"      exit={result.returncode} (expected {expect_code})")
        if result.stderr:
            print(f"      stderr: {result.stderr[:200]}")
        if result.stdout:
            print(f"      stdout: {result.stdout[:200]}")
    return ok


if __name__ == "__main__":
    print("Pineapple CLI Smoke Tests")
    print("=" * 40)

    run("--version", ["--version"])
    run("-v", ["-v"])
    run("version", ["version"])
    run("--help", ["--help"], expect_in="generate")

    run("generate with --framework flask", ["generate", ".", "--framework", "flask", "--quiet"], expect_in="python:3.11-slim")
    run("generate with --framework nextjs", ["generate", ".", "--framework", "nextjs", "--quiet"], expect_in="node:20-alpine")
    run("generate with --framework vite", ["generate", ".", "--framework", "vite", "--quiet"], expect_in="caddy:alpine")
    run("generate with --framework go", ["generate", ".", "--framework", "go", "--quiet"], expect_in="golang:1.22-alpine")
    run("generate with --framework rust", ["generate", ".", "--framework", "rust", "--quiet"], expect_in="rust:1.77-slim")

    run("generate nonexistent dir", ["generate", "/nonexistent"], expect_code=1, expect_in="not a directory")

    run("verify --help", ["verify", "--help"], expect_in="docker")
    run("github --help", ["github", "--help"], expect_in="setup")
    run("github setup --help", ["github", "setup", "--help"], expect_in="private-key")
    run("dashboard --help", ["dashboard", "--help"], expect_in="port")

    run("top-level path forward", ["/tmp", "--quiet"], expect_in="nginx:alpine")

    print("=" * 40)
    print(f"  {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
