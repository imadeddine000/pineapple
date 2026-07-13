.PHONY: dev backend frontend test build deb clean

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

# Run tests
test:
	PYTHONPATH=src python3 tests/test_clone_detect.py

# Build frontend for production
build-frontend:
	cd frontend && npm run build && cp -r dist/* ../src/pineapple/static/

# Build .deb package
build-deb: build-frontend
	dpkg-buildpackage -us -uc -b

# Clean build artifacts
clean:
	rm -rf src/pineapple/static frontend/dist *.egg-info
	rm -f ../*.deb ../*.buildinfo ../*.changes ../*.dsc ../*.tar.*
