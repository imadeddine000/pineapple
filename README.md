![pineapple logo](./octopack.png)

# 🍍 pineapple

**Smart framework detection, Dockerfile generation & container builds** — zero dependencies, pure Python stdlib.

Scans any project directory, detects the framework and language, and generates a
production-ready **multi-stage Dockerfile**. A lightweight alternative to nixpacks
that produces standard, human-readable Dockerfiles — and can even build them for you.

## Features

- **23+ frameworks** detected: Vite, Next.js, Nuxt, Remix, Gatsby, Astro, SvelteKit,
  Vue CLI, Express, NestJS, Django, Flask, FastAPI, Streamlit, Go, Rails, Sinatra,
  Laravel, PHP, Rust, and static HTML
- **Package manager aware**: detects `pnpm`, `yarn`, or `npm` and generates the
  correct install commands (with pnpm auto-install in the container!)
- **Multi-stage Dockerfiles**: lean production images with Caddy (static sites),
  node:alpine (SSR/servers), python:3.11-slim, golang:alpine, etc.
- **Zero-config**: just run `pineapple` in any project — no arguments needed
- **One-command build**: add `--build` / `-b` to automatically build the container
  image after generating the Dockerfile
- **Docker verification**: `pineapple verify docker` checks that Docker is installed
  and the daemon is accessible, with helpful error messages
- **Zero deps**: uses only Python standard library — no pip install required
- **CLI & library**: use as `python -m pineapple` or `import pineapple`

## Installation

### From source (pip)

```bash
git clone https://github.com/your-username/pineapple.git
cd pineapple
pip install -e .
```

### Debian package (.deb)

```bash
# Build the .deb package
sudo apt install devscripts debhelper dh-python python3-all python3-setuptools
dpkg-buildpackage -us -uc -b

# Install it
sudo dpkg -i ../python3-pineapple_1.0.0-1_all.deb
```

### Or just run without installing

```bash
cd /path/to/pineapple
python -m pineapple /path/to/project
```

## Usage

### Quickstart — zero arguments

```bash
# Just run it in any project folder — it scans ., detects, and writes Dockerfile
cd /path/to/my-project
pineapple
```

### CLI examples

```bash
# Scan current directory, write Dockerfile (default)
  pineapple
  ✓ Scanning /home/user/my-project ...
  ✓ Detected: express (node-server)
  ✓ Generating Dockerfile ...
  ✓ Dockerfile written to ./Dockerfile

# Scan a specific project
  pineapple ./path/to/project

# Write to a custom path
  pineapple -o output/Dockerfile
  pineapple gen ./project -o ../Dockerfile

# Print Dockerfile to stdout (for piping)
  pineapple --quiet
  pineapple --quiet > Dockerfile

# JSON detection output (for CI/CD)
  pineapple --json

# Generate & build in one command
  pineapple --build
  pineapple ./project --build --tag myapp:v1

# Explicit framework (skip auto-detection)
  pineapple -f nextjs

# Verify Docker is available
  pineapple verify docker

# Version info
  pineapple --version
```

### As a library

```python
from pineapple.detect import detect_framework
from pineapple.dockerfile import generate_dockerfile
from pineapple.builder import build_image

# Detect
detection = detect_framework("/path/to/my-project")
print(detection["framework"])  # e.g. "vite"
print(detection["language"])   # e.g. "node"
print(detection["port"])       # e.g. 3000

# Generate Dockerfile
dockerfile = generate_dockerfile(detection, build_context="/path/to/my-project")
print(dockerfile)

# Build the image
build_image("/path/to/my-project", tag="myapp:latest")
```

## Supported frameworks

| Language | Frameworks |
|----------|------------|
| Node.js (static) | Vite, react-scripts, Gatsby, Astro, SvelteKit, Vue CLI |
| Node.js (SSR) | Next.js, Nuxt, Remix |
| Node.js (server) | Express, NestJS, generic Node.js |
| Python | Django, Flask, FastAPI, Streamlit |
| Go | Any Go project |
| Ruby | Rails, Sinatra |
| PHP | Laravel, generic PHP |
| Rust | Any Cargo project |
| Static | Any folder with index.html |

## How it works

1. **Scan** the project directory for known files (`package.json`, `requirements.txt`, `go.mod`, etc.)
2. **Match** against framework patterns by checking dependencies inside those files
3. **Detect** the package manager by checking for lock files (`pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`)
4. **Enrich** with install/build/start commands tailored to the framework
5. **Generate** a production-ready multi-stage Dockerfile
6. **Build** (optional) — run `docker build` to create the container image

## License

MIT
