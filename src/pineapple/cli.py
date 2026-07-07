"""
Pineapple CLI — Smart framework detection, Dockerfile generation & container builds.

Usage:
    pineapple                           Scan ., generate & write Dockerfile
    pineapple ./project                  Scan ./project, generate & write Dockerfile
    pineapple ./project --build          Scan, generate & build image
    pineapple ./project --quiet          Print Dockerfile to stdout (for piping)
    pineapple --json                     Print detection as JSON
    pineapple verify docker              Check Docker availability
    pineapple --version                  Show version
    pineapple --help                     Show this help
"""

import argparse
import json
import os
import sys

from pineapple import __version__
from pineapple.detect import detect_framework
from pineapple.dockerfile import generate_dockerfile
from pineapple.builder import build_image, check_docker


# ── Helpers ───────────────────────────────────────────────────────────────

def _info(message: str, *args: object) -> None:
    """Print an info message to stderr."""
    if args:
        message = message % args
    print(f"  {message}", file=sys.stderr)


def _ok(message: str, *args: object) -> None:
    """Print a success message to stderr."""
    if args:
        message = message % args
    print(f"  ✓ {message}", file=sys.stderr)


def _warn(message: str, *args: object) -> None:
    """Print a warning message to stderr."""
    if args:
        message = message % args
    print(f"  ⚠ {message}", file=sys.stderr)


def _err(message: str, *args: object) -> None:
    """Print an error message to stderr."""
    if args:
        message = message % args
    print(f"  ✗ {message}", file=sys.stderr)


# ── Subcommand handlers ──────────────────────────────────────────────────


def cmd_generate(args: argparse.Namespace) -> int:
    """Handle the ``generate`` subcommand."""
    # Use cwd if no project dir given
    raw_dir = args.project_dir or "."
    project_dir = os.path.abspath(raw_dir)

    if not os.path.isdir(project_dir):
        _err("'%s' is not a directory", raw_dir)
        return 1

    quiet = args.quiet

    # ── Detect ──────────────────────────────────────────────────────────
    if not quiet and not args.json:
        _info("Scanning %s ...", project_dir)

    detection = detect_framework(project_dir, user_framework=args.framework)
    fw = detection.get("framework", "unknown")
    fw_type = detection.get("type", "unknown")

    if fw == "unknown" and not args.json:
        if not quiet:
            _warn("Could not detect any known framework in '%s'", project_dir)
            _info("Generating fallback static Dockerfile")
    elif not quiet and not args.json:
        _info("Detected: %s (%s)", fw, fw_type)

    if args.json:
        output = json.dumps(detection, indent=2, default=str)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output + "\n")
            if not quiet:
                _ok("Detection written to %s", args.output)
        else:
            print(output)
        return 0

    # ── Generate Dockerfile ────────────────────────────────────────────
    if not quiet:
        _info("Generating Dockerfile ...")

    dockerfile = generate_dockerfile(detection, build_context=project_dir)

    # Determine output path
    # Default: write to Dockerfile in project dir
    # --quiet flag: print to stdout (for piping)
    # -o flag: write to specified path
    output_path = args.output

    if quiet and output_path is None:
        # Quiet mode with no -o: stdout (old default, for piping)
        print(dockerfile, end="")
        write_target = None
    elif output_path is not None:
        # Explicit -o path
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(dockerfile)
        write_target = output_path
    else:
        # Default: write to project_dir/Dockerfile
        output_path = os.path.join(project_dir, "Dockerfile")
        with open(output_path, "w") as f:
            f.write(dockerfile)
        write_target = output_path

    if write_target and not quiet:
        # Show a clean path: relative if inside cwd, absolute otherwise
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
            # In quiet+stdout mode, write to project dir first for build
            write_target = os.path.join(project_dir, "Dockerfile")
            with open(write_target, "w") as f:
                f.write(dockerfile)

        builder = args.builder or "docker"
        tag = args.tag or f"{os.path.basename(project_dir)}:latest"

        if not quiet:
            print(file=sys.stderr)  # blank line before build section

        return build_image(
            project_dir=project_dir,
            tag=tag,
            builder=builder,
            dockerfile_path=write_target,
            quiet=quiet,
        )

    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Handle the ``verify`` subcommand."""
    if args.tool == "docker":
        result = check_docker()
        if result == 0:
            print("  ✓ Docker is installed and the daemon is accessible.")
        return result
    elif args.tool == "podman":
        _err("Podman support is coming in a future release.")
        return 1
    else:
        _err("Unknown tool: %s", args.tool)
        return 1


# ── Parser construction ──────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="pineapple",
        description="Smart framework detection, Dockerfile generation & container builds. "
        "Scans any project directory, detects the framework and language, "
        "and generates a production-ready Dockerfile — zero deps, pure Python.",
        epilog="Examples:\n"
        "  pineapple                          Scan ., write Dockerfile\n"
        "  pineapple ./project                Scan project, write Dockerfile\n"
        "  pineapple ./project --build        Generate + build image\n"
        "  pineapple --quiet                  Print Dockerfile to stdout\n"
        "  pineapple --json                   Detection as JSON\n"
        "  pineapple verify docker            Check Docker availability\n"
        "  pineapple --version                Show version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", "-V",
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
        action="store_true",
        help="Output the detection result as JSON instead of a Dockerfile",
    )
    gen_parser.add_argument(
        "--framework", "-f",
        default=None,
        help="Explicitly specify the framework (e.g. 'nextjs', 'fastapi'). Skips auto-detection.",
    )
    gen_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Print Dockerfile to stdout instead of writing to a file (for piping)",
    )
    gen_parser.add_argument(
        "--build", "-b",
        action="store_true",
        help="Build the container image after generating the Dockerfile",
    )
    gen_parser.add_argument(
        "--tag", "-t",
        default=None,
        help="Image tag in 'name:tag' format (default: <project-dir-name>:latest)",
    )
    gen_parser.add_argument(
        "--builder",
        default="docker",
        choices=["docker", "podman"],
        help="Container builder to use (default: docker)",
    )
    gen_parser.set_defaults(func=cmd_generate)

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

    return parser


# ── Main entry point ─────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point.

    If no subcommand is given, ``generate`` is assumed.
    If no project directory is given, the current directory is used.
    """
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]

    # If the first argument doesn't look like a subcommand or flag,
    # treat it as a project directory and prepend "generate"
    if argv:
        first = argv[0]
        subcommands = {"generate", "gen", "g", "verify"}
        if not first.startswith("-") and first not in subcommands:
            argv = ["generate"] + list(argv)

    args = parser.parse_args(argv)

    if args.command is None:
        # No subcommand — default to "generate" with cwd
        args = parser.parse_args(["generate"] + list(argv))

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
