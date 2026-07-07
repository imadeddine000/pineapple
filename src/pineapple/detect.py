"""
Framework detection engine.

Detects programming language, framework, build system, and package manager
from a project directory — no dependencies beyond Python stdlib.
"""

import json
import os
from typing import Optional

# Framework definitions

FRAMEWORK_PATTERNS = {
    # Node.js static sites
    "vite":          {"file": "package.json", "dep": "vite",            "type": "node-static",  "build": "npm run build",  "out": "dist",          "port": 3000},
    "react-scripts": {"file": "package.json", "dep": "react-scripts",   "type": "node-static",  "build": "npm run build",  "out": "build",         "port": 3000},
    "gatsby":        {"file": "package.json", "dep": "gatsby",          "type": "node-static",  "build": "gatsby build",   "out": "public",        "port": 3000},
    "astro":         {"file": "package.json", "dep": "astro",           "type": "node-static",  "build": "npm run build",  "out": "dist",          "port": 3000},
    "svelte-kit":    {"file": "package.json", "dep": "@sveltejs/kit",   "type": "node-static",  "build": "npm run build",  "out": "build",         "port": 3000},
    "vue-cli":       {"file": "package.json", "dep": "@vue/cli-service","type": "node-static",  "build": "npm run build",  "out": "dist",          "port": 3000},
    # Node.js SSR apps
    "nuxt":          {"file": "package.json", "dep": "nuxt",            "type": "node-ssr",     "build": "npm run build",  "out": ".output",       "port": 3000},
    "nextjs":        {"file": "package.json", "dep": "next",            "type": "node-ssr",     "build": "npm run build",  "out": ".next",         "port": 3000},
    "remix":         {"file": "package.json", "dep": "@remix-run/react","type": "node-ssr",     "build": "npm run build",  "out": "build",         "port": 3000},
    # Node.js servers
    "express":       {"file": "package.json", "dep": "express",         "type": "node-server",  "build": None,             "out": None,            "port": 3000},
    "nestjs":        {"file": "package.json", "dep": "@nestjs/core",    "type": "node-server",  "build": "npm run build",  "out": "dist",          "port": 3000},
    # Python
    "django":        {"file": "requirements.txt", "dep": "django",      "type": "python",       "build": None,             "out": None,            "port": 8000},
    "flask":         {"file": "requirements.txt", "dep": "flask",       "type": "python",       "build": None,             "out": None,            "port": 5000},
    "fastapi":       {"file": "requirements.txt", "dep": "fastapi",     "type": "python",       "build": None,             "out": None,            "port": 8000},
    "streamlit":     {"file": "requirements.txt", "dep": "streamlit",   "type": "python",       "build": None,             "out": None,            "port": 8501},
    # Go
    "go":            {"file": "go.mod",           "dep": None,          "type": "go",           "build": None,             "out": None,            "port": 8080},
    # Ruby
    "rails":         {"file": "Gemfile",          "dep": "rails",       "type": "ruby",         "build": None,             "out": None,            "port": 3000},
    "sinatra":       {"file": "Gemfile",          "dep": "sinatra",     "type": "ruby",         "build": None,             "out": None,            "port": 4567},
    # PHP
    "laravel":       {"file": "composer.json",    "dep": "laravel",     "type": "php",          "build": None,             "out": None,            "port": 8000},
    "php":           {"file": "composer.json",    "dep": None,          "type": "php",          "build": None,             "out": None,            "port": 8080},
    # Rust
    "rust":          {"file": "Cargo.toml",       "dep": None,          "type": "rust",         "build": None,             "out": None,            "port": 8080},
}


def detect_package_manager(build_context: str) -> str:
    """Detect pnpm / yarn / npm by checking for lock files."""
    if os.path.exists(os.path.join(build_context, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.exists(os.path.join(build_context, "yarn.lock")):
        return "yarn"
    return "npm"


def check_dependency(file_path: str, dep_name: str) -> bool:
    """
    Check if a JSON/text dependency file contains a given dependency name.
    Supports ``package.json``, ``requirements.txt``, ``Gemfile``,
    and ``composer.json``.
    """
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (OSError, IOError):
        return False

    name_lower = dep_name.lower()

    if file_path.endswith("package.json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return name_lower in content.lower()
        deps = {
            **data.get("dependencies", {}),
            **data.get("devDependencies", {}),
            **data.get("peerDependencies", {}),
        }
        return any(name_lower == k.lower() for k in deps)

    elif file_path.endswith("requirements.txt"):
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                pkg = stripped.split("==")[0].split(">=")[0].split("<=")[0].split("!=")[0].strip()
                if pkg.lower() == name_lower:
                    return True
        return False

    elif file_path.endswith("Gemfile"):
        return name_lower in content.lower()

    elif file_path.endswith("composer.json"):
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return name_lower in content.lower()
        deps = {
            **data.get("require", {}),
            **data.get("require-dev", {}),
        }
        return any(name_lower == k.lower() for k in deps)

    return name_lower in content.lower()


def enrich_detection(result: dict, build_context: str) -> None:
    """Enrich the detection dict with language, install/start commands."""
    fw = result["framework"]
    fw_type = result["type"]

    if fw_type in ("node-static", "node-ssr", "node-server"):
        result["language"] = "node"
        pm = detect_package_manager(build_context)
        result["package_manager"] = pm

        if pm == "pnpm":
            result["install_command"] = "pnpm install --frozen-lockfile"
        elif pm == "yarn":
            result["install_command"] = "yarn install --frozen-lockfile"
        else:
            result["install_command"] = "npm ci"

        pkg_json = os.path.join(build_context, "package.json")
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            if "scripts" in pkg:
                scripts = pkg["scripts"]
                if "start" in scripts:
                    result["start_command"] = scripts["start"]
                elif "dev" in scripts:
                    result["start_command"] = scripts["dev"]
        except Exception:
            pass
    elif fw_type == "python":
        result["language"] = "python"
        if not result.get("install_command"):
            result["install_command"] = "pip install -r requirements.txt"
    elif fw_type == "go":
        result["language"] = "go"
        result["install_command"] = "go mod download"
    elif fw_type == "ruby":
        result["language"] = "ruby"
        result["install_command"] = "bundle install"
    elif fw_type == "php":
        result["language"] = "php"
        result["install_command"] = "composer install --no-dev --no-interaction"
    elif fw_type == "rust":
        result["language"] = "rust"
        result["install_command"] = "cargo build --release"
        result["build_command"] = "cargo build --release"


def detect_framework(
    build_context: str,
    user_framework: Optional[str] = None,
) -> dict:
    """
    Detect the framework & language used by a project at *build_context*.

    Parameters
    ----------
    build_context : str
        Path to the project directory to scan.
    user_framework : str or None
        If set to a known framework name (e.g. ``"nextjs"``) it will be used
        directly instead of auto-detecting. Pass ``"auto"`` to force
        auto-detection.

    Returns
    -------
    dict
        A dictionary with keys: framework, type, language, build_command,
        install_command, start_command, output_dir, port, package_manager.
    """
    result = {
        "framework": user_framework or "unknown",
        "type": "unknown",
        "language": "unknown",
        "build_command": None,
        "install_command": None,
        "start_command": None,
        "output_dir": None,
        "port": 3000,
        "package_manager": "npm",
    }

    # User-specified framework (skip auto-detect)
    if user_framework and user_framework != "auto":
        normalized = (
            user_framework.lower().replace(" ", "-").replace("_", "-")
        )
        if normalized in FRAMEWORK_PATTERNS:
            pattern = FRAMEWORK_PATTERNS[normalized]
            result["framework"] = normalized
            result["type"] = pattern["type"]
            result["build_command"] = pattern["build"]
            result["output_dir"] = pattern["out"]
            result["port"] = pattern["port"]
            enrich_detection(result, build_context)
            return result

    # Auto-detect: match against known frameworks
    for fw_name, pattern in FRAMEWORK_PATTERNS.items():
        file_path = os.path.join(build_context, pattern["file"])
        if not os.path.exists(file_path):
            continue
        if pattern["dep"]:
            matched = check_dependency(file_path, pattern["dep"])
            if not matched:
                continue
        result["framework"] = fw_name
        result["type"] = pattern["type"]
        result["build_command"] = pattern["build"]
        result["output_dir"] = pattern["out"]
        result["port"] = pattern["port"]
        enrich_detection(result, build_context)
        return result

    # Fallback: generic Node.js (package.json)
    pkg_json = os.path.join(build_context, "package.json")
    if os.path.exists(pkg_json):
        result["framework"] = "node"
        result["type"] = "node-server"
        result["language"] = "node"
        result["package_manager"] = detect_package_manager(build_context)
        result["install_command"] = f"{result['package_manager']} install"
        try:
            with open(pkg_json) as f:
                pkg = json.load(f)
            if "scripts" in pkg:
                scripts = pkg["scripts"]
                if "start" in scripts:
                    result["start_command"] = scripts["start"]
                elif "dev" in scripts:
                    result["start_command"] = scripts["dev"]
        except Exception:
            pass
        return result

    # Fallback: Python (requirements.txt)
    req_txt = os.path.join(build_context, "requirements.txt")
    if os.path.exists(req_txt):
        result["framework"] = "python"
        result["type"] = "python"
        result["language"] = "python"
        result["install_command"] = "pip install -r requirements.txt"
        return result

    # Fallback: Static HTML
    index_html = os.path.join(build_context, "index.html")
    if os.path.exists(index_html):
        result["framework"] = "static"
        result["type"] = "static"
        result["language"] = "static"
        result["port"] = 80
        return result

    return result
