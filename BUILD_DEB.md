# Building the pineapple .deb Package

## Prerequisites

```bash
sudo apt update
sudo apt install devscripts debhelper dh-python python3-all python3-setuptools
```

## Build the .deb

```bash
cd /path/to/pineapple
dpkg-buildpackage -us -uc -b
```

The `.deb` will be at `../python3-pineapple_1.0.0-1_all.deb`.

## Install

```bash
sudo dpkg -i ../python3-pineapple_1.0.0-1_all.deb
sudo apt --fix-broken install
```

## Build the frontend (before building .deb)

The React frontend must be built before packaging:

```bash
cd frontend
npm install
npm run build
# This copies the build to src/pineapple/static/
cd ..
dpkg-buildpackage -us -uc -b
```

## One-command build (recommended)

```bash
cd /path/to/pineapple
(cd frontend && npm install && npm run build) && dpkg-buildpackage -us -uc -b
```

## Verify

```bash
pineapple --version
pineapple dashboard --help
pineapple dashboard
```

## File structure

```
frontend/            # React app (Vite)
  src/               # React components
  dist/              # Build output (copied to src/pineapple/static/)
src/pineapple/
  server.py          # FastAPI-ready HTTP server
  db.py              # SQLite database layer
  static/            # Built React frontend
  _dashboard_html.py # Embedded fallback for .deb
```
