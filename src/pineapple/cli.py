"""
Pineapple CLI — Smart framework detection, Dockerfile generation & container builds.

Usage:
    pineapple                           Scan ., write Dockerfile
    pineapple ./project                  Scan ./project, write Dockerfile
    pineapple --build                    Scan ., generate & build
    pineapple --json                     Print detection as JSON to stdout
    pineapple --json output.json         Print detection as JSON to file
    pineapple --quiet                    Print Dockerfile to stdout
    pineapple verify docker              Check Docker availability
    pineapple --version / -v / version   Show version
    pineapple --help / -h                Show this help
"""

import argparse
import json
import os
import sys

from pineapple import __version__
from pineapple.detect import detect_framework
from pineapple.dockerfile import generate_dockerfile
from pineapple.builder import build_image, check_docker
from pineapple.server import run_dashboard


# ── Helpers ───────────────────────────────────────────────────────────────

def _info(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  {message}", file=sys.stderr)


def _ok(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  \u2713 {message}", file=sys.stderr)


def _warn(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  \u26a0 {message}", file=sys.stderr)


def _err(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  \u2717 {message}", file=sys.stderr)


# ── Known generate flags (for top-level forwarding) ───────────────────────
# Any flag not in this set is treated as a generate subcommand flag

def _is_generate_flag(arg: str) -> bool:
    """Check if an arg looks like a flag that belongs to the generate subcommand."""
    if not arg.startswith("-"):
        return False
    # Strip leading dashes and =value suffix
    name = arg.lstrip("-").split("=")[0]
    # These are parsed at the top level
    if name in {"h", "-help", "v", "-version"}:
        return False
    # Everything else is a generate flag
    return True


# ── Subcommand handlers ──────────────────────────────────────────────────


def cmd_generate(args: argparse.Namespace) -> int:
    """Handle the ``generate`` subcommand."""
    raw_dir = args.project_dir or "."
    project_dir = os.path.abspath(raw_dir)

    if not os.path.isdir(project_dir):
        _err("'%s' is not a directory", raw_dir)
        return 1

    quiet = args.quiet
    is_json = bool(args.json)

    # ── Detect ──────────────────────────────────────────────────────────
    if not quiet and not is_json:
        _info("Scanning %s ...", project_dir)

    detection = detect_framework(project_dir, user_framework=args.framework)
    fw = detection.get("framework", "unknown")
    fw_type = detection.get("type", "unknown")

    # ── JSON output (handled early, no other progress) ──────────────────
    if is_json:
        output = json.dumps(detection, indent=2, default=str)
        # --json can take an optional filename:  pineapple --json file.json
        json_path = args.json if isinstance(args.json, str) else None
        if json_path:
            with open(json_path, "w") as f:
                f.write(output + "\n")
            if not quiet:
                _ok("Detection written to %s", json_path)
        elif args.output:
            with open(args.output, "w") as f:
                f.write(output + "\n")
            if not quiet:
                _ok("Detection written to %s", args.output)
        else:
            print(output)
        return 0

    # ── Progress messages (non-JSON) ────────────────────────────────────
    if fw == "unknown":
        if not quiet:
            _warn("Could not detect any known framework in '%s'", project_dir)
            _info("Generating fallback static Dockerfile")
    elif not quiet:
        _info("Detected: %s (%s)", fw, fw_type)

    # ── Generate Dockerfile ────────────────────────────────────────────
    if not quiet:
        _info("Generating Dockerfile ...")

    dockerfile = generate_dockerfile(detection, build_context=project_dir)

    # Output path logic:
    #   --quiet (no -o)  -> stdout (for piping)
    #   -o PATH          -> PATH
    #   default           -> <project_dir>/Dockerfile
    output_path = args.output

    if quiet and output_path is None:
        print(dockerfile, end="")
        write_target = None
    elif output_path is not None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(dockerfile)
        write_target = output_path
    else:
        output_path = os.path.join(project_dir, "Dockerfile")
        with open(output_path, "w") as f:
            f.write(dockerfile)
        write_target = output_path

    if write_target and not quiet:
        try:
            rel = os.path.relpath(write_target, os.getcwd())
            if rel.startswith(".."):
                rel = os.path.abspath(write_target)
        except ValueError:
            rel = os.path.abspath(write_target)
        _ok("Dockerfile written to %s", rel)

    # ── Build if requested ──────────────────────────────────────────────
    if args.build:
        if write_target is None:
            write_target = os.path.join(project_dir, "Dockerfile")
            with open(write_target, "w") as f:
                f.write(dockerfile)

        builder = args.builder or "docker"
        tag = args.tag or f"{os.path.basename(project_dir)}:latest"

        if not quiet:
            print(file=sys.stderr)

        return build_image(
            project_dir=project_dir,
            tag=tag,
            builder=builder,
            dockerfile_path=write_target,
            quiet=quiet,
        )

    return 0


def cmd_github_setup(args: argparse.Namespace) -> int:
    """Interactive setup for GitHub App credentials."""
    from pineapple.env import get_github_config, save_github_config
    cfg = get_github_config()
    print("  GitHub App Setup")
    print("  " + "=" * 40)
    print("  Create a GitHub App at https://github.com/settings/apps/new")
    print("  with callback URL: http://localhost:8765/api/github/callback")
    print()
    app_id = input("  App ID: ").strip() or cfg.get("app_id", "")
    client_id = input("  Client ID: ").strip() or cfg.get("client_id", "")
    client_secret = input("  Client Secret: ").strip() or cfg.get("client_secret", "")
    print("  Private Key (PEM) - paste the full key, then Ctrl+D:")
    print("  " + "-" * 40)
    import sys
    private_key_lines = []
    try:
        for line in sys.stdin:
            private_key_lines.append(line)
    except KeyboardInterrupt:
        pass
    private_key = "".join(private_key_lines).strip() or cfg.get("private_key", "")
    if not all([app_id, client_id, client_secret, private_key]):
        print("  ✗ All fields are required")
        return 1
    save_github_config(app_id, client_id, client_secret, private_key)
    print(f"  ✓ GitHub App credentials saved to ~/.pineapple/.env")
    print(f"  Run 'pineapple github connect' to link your GitHub account.")
    return 0


def cmd_github_connect(args: argparse.Namespace) -> int:
    """Connect a GitHub account by installing the app."""
    from pineapple.env import get_github_config, has_github_config
    if not has_github_config():
        print("  ✗ GitHub App not configured. Run 'pineapple github setup' first.")
        return 1
    cfg = get_github_config()
    import secrets, threading, http.server, json, urllib.request, webbrowser, sys
    
    # Start a temporary server for the OAuth callback
    port = 8765
    install_data = {}
    
    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            inst_id = qs.get("installation_id", [None])[0]
            if inst_id:
                install_data["installation_id"] = inst_id
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Connected!</h1><p>You can close this tab.</p><script>window.close()</script></body></html>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Error</h1>")
    
    # Open the install URL
    install_url = f"https://github.com/apps/{cfg['client_id']}/installations/new"
    print(f"  Opening browser to install the GitHub App...")
    webbrowser.open(install_url)
    
    # Start a quick server to catch the callback
    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120
    print(f"  Waiting for authorization on http://localhost:{port}...")
    print(f"  (Callback URL must be set to http://localhost:{port}/api/github/callback)")
    
    try:
        while not install_data.get("installation_id"):
            server.handle_request()
    except KeyboardInterrupt:
        print("  Cancelled")
        return 1
    
    inst_id = install_data["installation_id"]
    print(f"  Installation ID: {inst_id}")
    
    # Generate JWT and get installation token
    import time as _time, base64
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    
    now = int(_time.time())
    headers = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 60, "exp": now + 600, "iss": cfg["app_id"]}
    def _b64(d): return base64.urlsafe_b64encode(d).rstrip(b"=").decode()
    h = _b64(json.dumps(headers).encode())
    p = _b64(json.dumps(payload).encode())
    key = serialization.load_pem_private_key(cfg["private_key"].encode(), password=None)
    sig = _b64(key.sign(f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    jwt = f"{h}.{p}.{sig}"
    
    # Exchange for installation token
    req = urllib.request.Request(
        f"https://api.github.com/app/installations/{inst_id}/access_tokens",
        data=b"", method="POST",
        headers={"Authorization": f"Bearer {jwt}", "Accept": "application/vnd.github.v3+json", "User-Agent": "pineapple"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    token = resp.get("token")
    if not token:
        print(f"  ✗ Failed to get token: {resp}")
        return 1
    
    # Get account name
    req2 = urllib.request.Request(
        "https://api.github.com/installation/repositories",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "pineapple"},
    )
    data = json.loads(urllib.request.urlopen(req2, timeout=10).read())
    repos = data.get("repositories", [])
    account_name = repos[0]["owner"]["login"] if repos else "unknown"
    
    # Save to DB
    from pineapple.db import create_github_account
    acct = create_github_account(account_name, inst_id, token, now + 3600)
    print(f"  ✓ Connected as: {account_name}")
    print(f"  ✓ Access to {len(repos)} repositories")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Handle the ``verify`` subcommand."""
    if args.tool == "docker":
        result = check_docker()
        if result == 0:
            print("  \u2713 Docker is installed and the daemon is accessible.")
        return result
    elif args.tool == "podman":
        _err("Podman support is coming in a future release.")
        return 1
    else:
        _err("Unknown tool: %s", args.tool)
        return 1


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Handle the ``dashboard`` subcommand — start the web UI."""
    return run_dashboard(
        port=args.port or 8765,
        open_browser=not args.no_open,
    )


# ── Parser construction ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="pineapple",
        description="Smart framework detection, Dockerfile generation & container builds. "
        "Scans any project directory, detects the framework and language, "
        "and generates a production-ready Dockerfile \u2014 zero deps, pure Python.",
        epilog="Examples:\n"
        "  pineapple                          Scan ., write Dockerfile\n"
        "  pineapple ./project                Scan project, write Dockerfile\n"
        "  pineapple --build                  Generate + build image\n"
        "  pineapple --json                   Detection as JSON (stdout)\n"
        "  pineapple --json output.json       Detection as JSON (file)\n"
        "  pineapple --quiet                  Print Dockerfile to stdout\n"
        "  pineapple verify docker            Check Docker availability\n"
        "  pineapple --version                Show version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help",
        action="help",
        help="Show this help message and exit",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"pineapple {__version__}",
        help="Show version and exit",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="")

    # ── generate subcommand ────────────────────────────────────────────
    gen_parser = subparsers.add_parser(
        "generate", aliases=["gen", "g"],
        help="Detect framework & generate a Dockerfile (default command)",
        description="Detect project framework and generate a production-ready Dockerfile.",
        epilog="Examples:\n"
        "  pineapple generate                 Scan ., write Dockerfile\n"
        "  pineapple gen ./project -o df     Write to custom path\n"
        "  pineapple g ./project --build     Generate + build image",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gen_parser.add_argument(
        "project_dir", nargs="?", default=".",
        help="Path to the project directory (default: current directory)",
    )
    gen_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write Dockerfile to this path (default: <project>/Dockerfile)",
    )
    gen_parser.add_argument(
        "--json", "-j",
        nargs="?", const=True, default=False,
        help="Output detection as JSON (optionally specify output file)",
    )
    gen_parser.add_argument(
        "--framework", "-f",
        default=None,
        help="Explicitly specify the framework (e.g. 'nextjs', 'fastapi')",
    )
    gen_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Print Dockerfile to stdout instead of writing to a file",
    )
    gen_parser.add_argument(
        "--build", "-b",
        action="store_true",
        help="Build the container image after generating the Dockerfile",
    )
    gen_parser.add_argument(
        "--tag", "-t",
        default=None,
        help="Image tag in 'name:tag' format (default: <dir-name>:latest)",
    )
    gen_parser.add_argument(
        "--builder",
        default="docker",
        choices=["docker", "podman"],
        help="Container builder to use (default: docker)",
    )
    gen_parser.set_defaults(func=cmd_generate)

    # ── verify subcommand ──────────────────────────────────────────────
    # ── github subcommand ─────────────────────────────────────────────
    github_parser = subparsers.add_parser(
        "github",
        help="Manage GitHub integration",
        description="Setup and manage GitHub App integration.",
    )
    github_sub = github_parser.add_subparsers(dest="github_command", metavar="")
    
    setup_parser = github_sub.add_parser("setup", help="Configure GitHub App credentials")
    setup_parser.set_defaults(func=cmd_github_setup)
    
    connect_parser = github_sub.add_parser("connect", help="Connect a GitHub account")
    connect_parser.set_defaults(func=cmd_github_connect)
    
    # ── verify subcommand ──
    verify_parser = subparsers.add_parser(
        "verify",
        help="Check if a container tool (docker/podman) is available",
        description="Verify that a container runtime is installed and the daemon is accessible.",
        epilog="Examples:\n"
        "  pineapple verify docker\n"
        "  pineapple verify podman",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    verify_parser.add_argument(
        "tool",
        choices=["docker", "podman"],
        help="Container tool to verify",
    )
    verify_parser.set_defaults(func=cmd_verify)

    # ── dashboard subcommand ────────────────────────────────────────────
    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Open the pineapple web dashboard",
        description="Start a local web server with a GUI for detection, Dockerfile generation, and builds.",
        epilog="Examples:\n"
        "  pineapple dashboard\n"
        "  pineapple dashboard --port 8765\n"
        "  pineapple dashboard --no-open",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    dashboard_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="Port to bind (default: 8765, auto-finds next free if busy)",
    )
    dashboard_parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't automatically open the browser",
    )
    dashboard_parser.set_defaults(func=cmd_dashboard)

    return parser


# ── Main entry point ─────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point.

    Rules:
    - ``pineapple``                   -> generate on cwd
    - ``pineapple /path``             -> generate on /path
    - ``pineapple --json``            -> generate --json on cwd
    - ``pineapple --json file.json``  -> generate --json=file.json on cwd
    - ``pineapple --build``           -> generate --build on cwd
    - ``pineapple verify docker``     -> verify docker
    - ``pineapple version``           -> print version
    - ``pineapple -v / --version``    -> print version
    - ``pineapple -h / --help``       -> show help
    """
    if argv is None:
        argv = sys.argv[1:]

    # ── Handle ``version`` command (not a subcommand) ──────────────────
    if argv and argv[0] == "version":
        print(f"pineapple {__version__}")
        return 0

    # ── Intercept top-level ``-v`` / ``--version`` at the top level ────
    # (before any subcommand forwarding, so they work cleanly)
    if argv:
        first = argv[0]
        if first in ("-v", "--version"):
            print(f"pineapple {__version__}")
            return 0
        if first in ("-h", "--help"):
            parser = build_parser()
            parser.print_help()
            return 0

    # ── If no args at all, default to generate on cwd ──────────────────
    if not argv:
        argv = ["generate"]

    first = argv[0]
    subcommands = {"generate", "gen", "g", "verify", "dashboard", "github"}

    # ── If first arg is not a subcommand, assume generate ───────────────
    if first not in subcommands:
        argv = ["generate"] + list(argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
