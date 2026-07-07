"""
Container build support for pineapple.

Handles running Docker (and in the future Podman) to build images
from generated Dockerfiles.
"""

import os
import subprocess
import sys


def check_docker() -> int:
    """
    Check if Docker is installed and the daemon is accessible.

    Returns 0 if Docker is available, 1 otherwise.
    Prints user-friendly error messages on failure.
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return 0
        else:
            print(
                "✗ Docker daemon is not running or not accessible.",
                file=sys.stderr,
            )
            print(f"  {result.stderr.strip()}", file=sys.stderr)
            return 1
    except FileNotFoundError:
        print(
            "✗ Docker is not installed.",
            file=sys.stderr,
        )
        print(
            "  Install it with: sudo apt install docker.io",
            file=sys.stderr,
        )
        print(
            "  Or visit: https://docs.docker.com/engine/install/",
            file=sys.stderr,
        )
        return 1
    except subprocess.TimeoutExpired:
        print("✗ Docker info command timed out.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"✗ Unexpected error checking Docker: {e}", file=sys.stderr)
        return 1


def build_image(
    project_dir: str,
    tag: str = "latest",
    builder: str = "docker",
    dockerfile_path: str | None = None,
    quiet: bool = False,
) -> int:
    """
    Build a container image from the generated Dockerfile.

    Parameters
    ----------
    project_dir : str
        Path to the project directory (build context).
    tag : str
        Image tag (e.g. ``"myapp:latest"``).
    builder : str
        Container builder to use (``"docker"`` or ``"podman"``).
    dockerfile_path : str or None
        Path to the Dockerfile. If None, Docker will look for ``Dockerfile``
        in the build context.
    quiet : bool
        If True, suppress status messages.

    Returns
    -------
    int
        0 on success, 1 on failure.
    """
    if builder == "podman":
        print(
            "Podman build is not yet supported. Use --builder docker.",
            file=sys.stderr,
        )
        return 1

    # Check Docker availability
    if check_docker() != 0:
        return 1

    cmd = ["docker", "build"]

    if dockerfile_path:
        cmd.extend(["-f", dockerfile_path])

    cmd.extend(["-t", tag, project_dir])

    if not quiet:
        print(f"\n→ Building image: {tag}", file=sys.stderr)
        print(f"  Context: {project_dir}", file=sys.stderr)
        if dockerfile_path:
            print(f"  Dockerfile: {dockerfile_path}", file=sys.stderr)
        print(file=sys.stderr)

    try:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            if not quiet:
                print(f"\n✓ Successfully built {tag}", file=sys.stderr)
            return 0
        else:
            print(f"\n✗ Build failed for {tag}", file=sys.stderr)
            return result.returncode
    except FileNotFoundError:
        print("✗ Docker binary not found.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"✗ Build error: {e}", file=sys.stderr)
        return 1
