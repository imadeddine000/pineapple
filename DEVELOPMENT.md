# Development

## Quick Start — One-time setup

```bash
make dev-install
```

This creates a virtual environment and installs pineapple in editable mode.
After that, just use `./pineapple` from the project root:

```bash
./pineapple --help
./pineapple generate . --framework vite --quiet
./pineapple verify docker
./pineapple dashboard --no-open
```

To use `pineapple` from **anywhere** (not just the project root), add this to your `~/.bashrc`:
```bash
export PATH=$PATH:/home/madeb/pineapple
```
Then:
```bash
pineapple --version
cd /some/project && pineapple
```

Changes to `src/pineapple/*.py` are picked up **immediately** — no rebuild needed.

## Dev environment with dashboard

```bash
make dev
```

This starts:
- **Backend** on http://localhost:8765 (auto-restarts when you edit `.py` files)
- **Frontend** on http://localhost:5173 (hot-reloads when you edit `.jsx`/`.css` files)

Open **http://localhost:5173** in your browser — it proxies `/api/*` to the backend.

## Manual (two terminals)

### Terminal 1 — Backend
```bash
cd /home/madeb/pineapple
./pineapple dashboard
# Ctrl+C → up-arrow → Enter to restart after edits
```

### Terminal 2 — Frontend
```bash
cd /home/madeb/pineapple/frontend
npm run dev
# Auto-reloads on any file change
```

## Testing

```bash
make smoke       # Quick CLI smoke test (15 tests, no network)
make test        # Full test suite (clone + detection + API)
```

## Other commands

```bash
make frontend    # Frontend dev server only
make backend     # Backend with auto-restart
make build-deb   # Build .deb package
make clean       # Remove venv + build artifacts
```
