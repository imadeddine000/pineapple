# Development

## One command to start everything

```bash
cd /home/madeb/pineapple
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
PYTHONPATH=src python3 -m pineapple dashboard
# Ctrl+C → up-arrow → Enter to restart after edits
```

### Terminal 2 — Frontend
```bash
cd /home/madeb/pineapple/frontend
npm run dev
# Auto-reloads on any file change
```

## Workflow

| You do | What happens |
|--------|-------------|
| Edit a `.py` file | Backend auto-restarts (via `make dev`) |
| Edit a `.jsx`/`.css` | Browser updates instantly (Vite HMR) |
| Add a new API route | Backend restarts, frontend picks it up |

## Other commands

```bash
make test       # Run test suite
make frontend   # Frontend dev server only
make backend    # Backend with auto-restart
make build-deb  # Build .deb package

# GitHub CLI (no dashboard needed)
PYTHONPATH=src python3 -m pineapple github setup
PYTHONPATH=src python3 -m pineapple github connect
```
