# octopack

**Smart framework detection & Dockerfile generation** — zero dependencies, pure Python stdlib.

Scans any project directory, detects the framework and language, and generates a
production-ready **multi-stage Dockerfile**. A lightweight alternative to nixpacks
that produces standard, human-readable Dockerfiles.

## Features

- **23+ frameworks** detected: Vite, Next.js, Nuxt, Remix, Gatsby, Astro, SvelteKit,
  Vue CLI, Express, NestJS, Django, Flask, FastAPI, Streamlit, Go, Rails, Sinatra,
  Laravel, PHP, Rust, and static HTML
- **Package manager aware**: detects `pnpm`, `yarn`, or `npm` and generates the
  correct install commands (with pnpm auto-install in the container!)
- **Multi-stage Dockerfiles**: lean production images with Caddy (static sites),
  node:alpine (SSR/servers), python:3.11-slim, golang:alpine, etc.
- **Zero deps**: uses only Python standard library — no pip install required
- **CLI & library**: use as `python -m octopack` or `import octopack`

## Installation

### From source

```bash
git clone https://github.com/imadeddine/octopack.git
cd octopack
pip install -e .
```

### Or just run without installing

```bash
cd /path/to/octopack
python -m octopack /path/to/project
```

## Usage

### CLI

```bash
# Basic detection + Dockerfile to stdout
python -m octopack /path/to/my-project

# Write Dockerfile to file
python -m octopack /path/to/my-project --output Dockerfile

# JSON output (for CI/CD pipelines)
python -m octopack /path/to/my-project --json

# Explicit framework (skip auto-detection)
python -m octopack /path/to/my-project --framework nextjs

# Quiet mode (Dockerfile only, no stderr)
python -m octopack /path/to/my-project --quiet
```

### As a library

```python
from octopack.detect import detect_framework
from octopack.dockerfile import generate_dockerfile

# Detect
detection = detect_framework("/path/to/my-project")
print(detection["framework"])  # e.g. "vite"
print(detection["language"])   # e.g. "node"
print(detection["port"])       # e.g. 3000

# Generate Dockerfile
dockerfile = generate_dockerfile(detection, build_context="/path/to/my-project")
print(dockerfile)
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

## License

MIT
