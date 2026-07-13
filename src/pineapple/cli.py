"""
Pineapple CLI — Smart framework detection, Dockerfile generation & container builds.

Usage:
    pineapple                           Scan ., write Dockerfile
    pineapple ./project                  Scan ./project, write Dockerfile
    pineapple --build                    Scan ., generate & build
    pineapple --json                     Print detection as JSON to stdout
    pineapple --json file.json           Print detection as JSON to file
    pineapple --quiet                    Print Dockerfile to stdout
    pineapple verify docker              Check Docker availability
    pineapple dashboard                  Open web dashboard
    pineapple github setup               Configure GitHub App credentials
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


def cmd_github_config(args: argparse.Namespace) -> int:
    """
    Configure GitHub App credentials.

    Credentials are stored in ~/.pineapple/.env for later use
    (webhook registration, auto-deploy, etc.).
    """
    from pineapple.env import get_github_config, save_github_config

    cfg = get_github_config()

    print("  GitHub App Configuration")
    print("  " + "=" * 40)
    print()
    print("  Create a GitHub App at https://github.com/settings/apps/new")
    print()
    print("  Required fields:")
    print("    - App ID (numeric)")
    print("    - Client ID")
    print("    - Client secret")
    print("    - Private key (PEM file)")
    print()

    # Read private key if --private-key-file was given
    private_key = cfg.get("private_key", "")
    if args.private_key_file:
        try:
            with open(args.private_key_file) as f:
                private_key = f.read()
            _ok("Read private key from %s", args.private_key_file)
        except FileNotFoundError:
            _err("File not found: %s", args.private_key_file)
            return 1
        except Exception as e:
            _err("Error reading private key: %s", e)
            return 1

    app_id = input(f"  App ID [{cfg.get('app_id', '')}]: ").strip() or cfg.get("app_id", "")
    if not app_id:
        _err("App ID is required")
        return 1

    client_id = input(f"  Client ID [{cfg.get('client_id', '')}]: ").strip() or cfg.get("client_id", "")
    if not client_id:
        _err("Client ID is required")
        return 1

    client_secret = input(f"  Client Secret [{cfg.get('client_secret', '')[:4]}...]: ").strip() or cfg.get("client_secret", "")
    if not client_secret:
        _err("Client Secret is required")
        return 1

    if not private_key:
        print("  Private key: paste the full PEM key below (Ctrl+D when done):")
        print("  " + "-" * 40)
        private_key_lines = []
        try:
            for line in sys.stdin:
                private_key_lines.append(line)
        except KeyboardInterrupt:
            print()
            _err("Cancelled")
            return 1
        private_key = "".join(private_key_lines).strip()

    if not private_key:
        _err("Private key is required")
        return 1

    save_github_config(app_id, client_id, client_secret, private_key)
    _ok("GitHub App credentials saved to ~/.pineapple/.env")
    print()
    _info("Future features (coming soon):")
    _info("  pineapple github webhook register <repo>   — Register a deploy webhook")
    _info("  pineapple github webhook listen             — Listen for push events")
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

    # ── github subcommand ─────────────────────────────────────────────
    github_parser = subparsers.add_parser(
        "github",
        help="Configure GitHub App integration",
        description="Configure GitHub App credentials for future webhook / auto-deploy features.",
        epilog="Examples:\n"
        "  pineapple github setup                      Interactive config\n"
        "  pineapple github setup --private-key-file   Config with key file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    github_sub = github_parser.add_subparsers(dest="github_command", metavar="")

    config_parser = github_sub.add_parser(
        "setup", aliases=["config"],
        help="Configure GitHub App credentials (App ID, client secret, private key)",
    )
    config_parser.add_argument(
        "--private-key-file", "-k",
        default=None,
        help="Path to the GitHub App PEM private key file",
    )
    config_parser.set_defaults(func=cmd_github_config)

    # ── verify subcommand ──────────────────────────────────────────────
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
