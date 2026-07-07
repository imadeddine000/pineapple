"""
Pineapple CLI — Smart framework detection, Dockerfile generation & container builds.

Usage:
    pineapple /path/to/project                    Detect & print Dockerfile
    pineapple generate /path/to/project --build    Detect, generate & build
    pineapple verify docker                        Check Docker availability
    pineapple --version                            Show version
    pineapple --help                               Show this help
"""


import argparse
import json
import os
import sys

from pineapple import __version__
from pineapple.detect import detect_framework
from pineapple.dockerfile import generate_dockerfile
from pineapple.builder import build_image, check_docker


# ── Subcommand handlers ───────────────────────────────────────


def cmd_generate(args: argparse.Namespace) -> int:
    """Handle the ``generate`` subcommand."""
    project_dir = os.path.abspath(args.project_dir)
    if not os.path.isdir(project_dir):
        print(f"Error: '{args.project_dir}' is not a directory", file=sys.stderr)
        return 1

    # ── Detect ────────────────────────────────────────────────
    detection = detect_framework(project_dir, user_framework=args.framework)

    if detection["framework"] == "unknown" and not args.quiet:
        print(
            f"Warning: could not detect any known framework in '{project_dir}'",
            file=sys.stderr,
        )

    if args.json:
        # ── JSON output ────────────────────────────────────────
        output = json.dumps(detection, indent=2, default=str)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output + "\n")
            if not args.quiet:
                print(f"Detection written to {args.output}")
        else:
            print(output)
        return 0

    # ── Generate Dockerfile ──────────────────────────────────
    dockerfile = generate_dockerfile(detection, build_context=project_dir)

    # Determine output path
    output_path = args.output
    if args.build and output_path is None:
        # When building, write to project dir by default
        output_path = os.path.join(project_dir, "Dockerfile")

    if output_path:
        with open(output_path, "w") as f:
            f.write(dockerfile)
        if not args.quiet:
            print(f"Dockerfile written to {output_path}", file=sys.stderr)
            if detection["framework"] != "unknown":
                print(
                    f"Detected: {detection['framework']} ({detection['type']})",
                    file=sys.stderr,
                )
    else:
        # Print to stdout — Dockerfile only
        print(dockerfile, end="")

    # ── Build if requested ────────────────────────────────────
    if args.build:
        builder = args.builder or "docker"
        tag = args.tag or f"{os.path.basename(project_dir)}:latest"
        return build_image(
            project_dir=project_dir,
            tag=tag,
            builder=builder,
            dockerfile_path=output_path,
            quiet=args.quiet,
        )

    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Handle the ``verify`` subcommand."""
    if args.tool == "docker":
        result = check_docker()
        if result == 0:
            print("✓ Docker is installed and the daemon is accessible.")
        return result
    elif args.tool == "podman":
        print("Podman support is coming in a future release.", file=sys.stderr)
        return 1
    else:
        print(f"Unknown tool: {args.tool}", file=sys.stderr)
        return 1


# ── Parser construction ───────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="pineapple",
        description="Smart framework detection, Dockerfile generation & container builds. "
        "Scans any project directory, detects the framework and language, "
        "and generates a production-ready Dockerfile — zero deps, pure Python.",
        epilog="Examples:\n"
        "  pineapple ./my-project                Detect & print Dockerfile\n"
        "  pineapple gen ./my-project -o df      Write Dockerfile to 'df'\n"
        "  pineapple g ./my-project --build      Generate + build image\n"
        "  pineapple ./my-project -b -t v1       Generate + build with tag\n"
        "  pineapple verify docker               Check Docker availability\n"
        "  pineapple --version                   Show version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"pineapple {__version__}",
        help="Show version and exit",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="")

    # ── generate subcommand ─────────────────────────────────────
    gen_parser = subparsers.add_parser(
        "generate", aliases=["gen", "g"],
        help="Detect framework & generate a Dockerfile (default command)",
        description="Detect project framework and generate a production-ready Dockerfile.",
        epilog="Examples:\n"
        "  pineapple generate ./my-project\n"
        "  pineapple gen ./my-project -o Dockerfile\n"
        "  pineapple g ./my-project --build --tag myapp:v1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    gen_parser.add_argument(
        "project_dir",
        help="Path to the project directory to scan",
    )
    gen_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Write Dockerfile to this path instead of stdout",
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
        help="Suppress info messages, output only the Dockerfile",
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

    # ── verify subcommand ───────────────────────────────────────
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


# ── Main entry point ──────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """
    Main entry point.

    If no subcommand is given but positional arguments are present,
    ``generate`` is assumed (so ``pineapple /path`` works as shorthand).
    """
    parser = build_parser()

    if argv is None:
        argv = sys.argv[1:]

    # If the first argument doesn't look like a subcommand or flag,
    # treat it as a project directory and prepend "generate"
    if argv and not argv[0].startswith("-"):
        first = argv[0]
        subcommands = {"generate", "gen", "g", "verify"}
        if first not in subcommands:
            argv = ["generate"] + list(argv)

    # First pass: try parsing as-is
    args = parser.parse_args(argv)

    # If no subcommand was matched and we have positional-like arguments,
    # prepend "generate" and re-parse
    if args.command is None and argv:
        # Only do this if the first arg isn't a flag
        first = argv[0]
        if not first.startswith("-"):
            new_argv = ["generate"] + list(argv)
            args = parser.parse_args(new_argv)

    if args.command is None:
        # Still no subcommand — show help
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
