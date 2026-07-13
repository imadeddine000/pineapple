.PHONY: dev backend frontend test smoke build-deb clean dev-install

# Start full dev environment (backend auto-restart + frontend hot reload)
dev:
	python3 scripts/dev.py

# Start backend only (auto-restarts on .py changes)
backend:
	PYTHONPATH=src python3 scripts/dev.py 2>/dev/null || \
	while true; do PYTHONPATH=src python3 -m pineapple dashboard; sleep 1; done

# Start frontend only (Vite hot reload)
frontend:
	cd frontend && npm run dev

# Run full test suite (clone + detection + API)
test:
	PYTHONPATH=src python3 tests/test_clone_detect.py

# Quick CLI smoke test (no network, no .deb needed)
smoke:
	PYTHONPATH=src python3 scripts/test_cli.py

# ────────────────────────────────────────────────────────────────────────────
# One-time setup — creates a venv + installs the package in editable mode.
# After this, you can just run:
#   ./pineapple <args>
# from anywhere in the project root, like it's installed via .deb.
# ────────────────────────────────────────────────────────────────────────────
dev-install:
	python3 -m venv .venv
	.venv/bin/pip install -e .
	@echo ""
	@echo "  ✓ Dev environment ready!"
	@echo ""
	@echo "  Now test with:"
	@echo "    ./pineapple --help"
	@echo "    ./pineapple generate . --framework vite --quiet"
	@echo "    ./pineapple verify docker"
	@echo ""
	@echo "  Or add to your ~/.bashrc for global access:"
	@echo "    export PATH=\$$PATH:$(CURDIR)"

# Build frontend for production
build-frontend:
	cd frontend && npm run build && cp -r dist/* ../src/pineapple/static/

# Build .deb package
build-deb: build-frontend
	dpkg-buildpackage -us -uc -b

# Clean build artifacts
clean:
	rm -rf .venv src/pineapple/static frontend/dist *.egg-info
	rm -f ../*.deb ../*.buildinfo ../*.changes ../*.dsc ../*.tar.*
