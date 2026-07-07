"""
Container build support for pineapple.

Handles running Docker (and in the future Podman) to build images
from generated Dockerfiles.
"""

import subprocess
import sys


def _info(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  {message}", file=sys.stderr)


def _ok(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  \u2713 {message}", file=sys.stderr)


def _err(message: str, *args: object) -> None:
    if args:
        message = message % args
    print(f"  \u2717 {message}", file=sys.stderr)


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
            _err("Docker daemon is not running or not accessible.")
            print(f"     {result.stderr.strip()}", file=sys.stderr)
            return 1
    except FileNotFoundError:
        _err("Docker is not installed.")
        _info("Install it with: sudo apt install docker.io")
        _info("Or visit: https://docs.docker.com/engine/install/")
        return 1
    except subprocess.TimeoutExpired:
        _err("Docker info command timed out.")
        return 1
    except Exception as e:
        _err("Unexpected error checking Docker: %s", e)
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
        _err("Podman build is not yet supported. Use --builder docker.")
        return 1

    # Check Docker availability
    if check_docker() != 0:
        return 1

    cmd = ["docker", "build"]

    if dockerfile_path:
        cmd.extend(["-f", dockerfile_path])

    cmd.extend(["-t", tag, project_dir])

    if not quiet:
        _info("Building image: %s", tag)
        _info("Context: %s", project_dir)
        print(file=sys.stderr)

    try:
        result = subprocess.run(cmd)
        if result.returncode == 0:
            if not quiet:
                _ok("Successfully built %s", tag)
            return 0
        else:
            _err("Build failed for %s", tag)
            return result.returncode
    except FileNotFoundError:
        _err("Docker binary not found.")
        return 1
    except Exception as e:
        _err("Build error: %s", e)
        return 1
