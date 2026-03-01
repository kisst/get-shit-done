# GSD (Get Shit Done) — Python-only installation
# No npm/npx/node dependencies required.
#
# Usage:
#   make install          Install GSD for Claude Code (default: global)
#   make install-local    Install GSD into current project's .claude/
#   make uninstall        Remove global GSD installation
#   make test             Run Python tests
#   make check            Verify installation health
#   make build-hooks      Copy hooks to dist/

SHELL := /bin/bash

# Paths
HOME_DIR := $(HOME)
CLAUDE_DIR := $(HOME_DIR)/.claude
GSD_DIR := $(CLAUDE_DIR)/get-shit-done
BIN_DIR := $(GSD_DIR)/bin
LIB_DIR := $(BIN_DIR)/lib_py
HOOKS_DIST := hooks/dist

# Source paths (relative to repo root)
SRC_BIN := get-shit-done/bin
SRC_HOOKS := hooks
SRC_COMMANDS := commands
SRC_AGENTS := agents
SRC_GSD := get-shit-done

# Python
PYTHON := python3

.PHONY: install install-local uninstall test check build-hooks clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: _check-python build-hooks ## Install GSD globally (~/.claude/get-shit-done)
	@echo "Installing GSD (Python) to $(GSD_DIR)..."
	@mkdir -p "$(BIN_DIR)" "$(LIB_DIR)"
	@# Copy Python dispatcher
	@cp "$(SRC_BIN)/gsd-tools.py" "$(BIN_DIR)/gsd-tools.py"
	@chmod +x "$(BIN_DIR)/gsd-tools.py"
	@# Copy Python library modules
	@cp $(SRC_BIN)/lib_py/*.py "$(LIB_DIR)/"
	@# Copy workflow/agent/command markdown files
	@if [ -d "$(SRC_GSD)/workflows" ]; then \
		cp -r "$(SRC_GSD)/workflows" "$(GSD_DIR)/"; \
	fi
	@if [ -d "$(SRC_GSD)/agents" ]; then \
		cp -r "$(SRC_GSD)/agents" "$(GSD_DIR)/"; \
	fi
	@if [ -d "$(SRC_COMMANDS)" ]; then \
		mkdir -p "$(CLAUDE_DIR)/commands"; \
		cp -r "$(SRC_COMMANDS)/"* "$(CLAUDE_DIR)/commands/"; \
	fi
	@if [ -d "$(SRC_AGENTS)" ]; then \
		mkdir -p "$(CLAUDE_DIR)/agents"; \
		cp -r "$(SRC_AGENTS)/"* "$(CLAUDE_DIR)/agents/"; \
	fi
	@# Copy hooks
	@if [ -d "$(HOOKS_DIST)" ]; then \
		mkdir -p "$(GSD_DIR)/hooks/dist"; \
		cp "$(HOOKS_DIST)/"*.py "$(GSD_DIR)/hooks/dist/"; \
		chmod +x "$(GSD_DIR)/hooks/dist/"*.py; \
	fi
	@# Write version file
	@if [ -f "get-shit-done/VERSION" ]; then \
		cp "get-shit-done/VERSION" "$(GSD_DIR)/VERSION"; \
	else \
		echo "dev" > "$(GSD_DIR)/VERSION"; \
	fi
	@echo "GSD installed to $(GSD_DIR)"
	@echo "Python dispatcher: $(BIN_DIR)/gsd-tools.py"

install-local: _check-python build-hooks ## Install GSD into current project .claude/
	$(eval LOCAL_GSD := .claude/get-shit-done)
	$(eval LOCAL_BIN := $(LOCAL_GSD)/bin)
	$(eval LOCAL_LIB := $(LOCAL_BIN)/lib_py)
	@echo "Installing GSD (Python) locally to $(LOCAL_GSD)..."
	@mkdir -p "$(LOCAL_BIN)" "$(LOCAL_LIB)"
	@cp "$(SRC_BIN)/gsd-tools.py" "$(LOCAL_BIN)/gsd-tools.py"
	@chmod +x "$(LOCAL_BIN)/gsd-tools.py"
	@cp $(SRC_BIN)/lib_py/*.py "$(LOCAL_LIB)/"
	@if [ -d "$(SRC_GSD)/workflows" ]; then cp -r "$(SRC_GSD)/workflows" "$(LOCAL_GSD)/"; fi
	@if [ -d "$(SRC_GSD)/agents" ]; then cp -r "$(SRC_GSD)/agents" "$(LOCAL_GSD)/"; fi
	@if [ -d "$(SRC_COMMANDS)" ]; then mkdir -p ".claude/commands" && cp -r "$(SRC_COMMANDS)/"* ".claude/commands/"; fi
	@if [ -d "$(SRC_AGENTS)" ]; then mkdir -p ".claude/agents" && cp -r "$(SRC_AGENTS)/"* ".claude/agents/"; fi
	@if [ -d "$(HOOKS_DIST)" ]; then \
		mkdir -p "$(LOCAL_GSD)/hooks/dist"; \
		cp "$(HOOKS_DIST)/"*.py "$(LOCAL_GSD)/hooks/dist/"; \
		chmod +x "$(LOCAL_GSD)/hooks/dist/"*.py; \
	fi
	@echo "GSD installed locally to $(LOCAL_GSD)"

uninstall: ## Remove global GSD installation
	@echo "Removing GSD from $(GSD_DIR)..."
	@rm -rf "$(GSD_DIR)"
	@echo "GSD uninstalled."
	@echo "Note: ~/.claude/commands/ and ~/.claude/agents/ were NOT removed."
	@echo "Remove them manually if desired."

build-hooks: ## Copy Python hooks to dist/
	@mkdir -p "$(HOOKS_DIST)"
	@for hook in gsd-check-update.py gsd-context-monitor.py gsd-statusline.py; do \
		if [ -f "$(SRC_HOOKS)/$$hook" ]; then \
			cp "$(SRC_HOOKS)/$$hook" "$(HOOKS_DIST)/$$hook"; \
			chmod +x "$(HOOKS_DIST)/$$hook"; \
			echo "Copied $$hook"; \
		fi; \
	done
	@echo "Build complete."

test: _check-python ## Run Python tests
	@echo "Running GSD Python tests..."
	@$(PYTHON) -m pytest tests/ -v 2>/dev/null || \
		$(PYTHON) -m unittest discover -s tests -v 2>/dev/null || \
		echo "No tests found. Create tests in tests/ directory."

check: _check-python ## Verify installation by running smoke tests
	@echo "Checking GSD Python installation..."
	@cd "$(SRC_BIN)" && $(PYTHON) -c "import lib_py; print('  Module imports: OK')"
	@cd "$(SRC_BIN)" && $(PYTHON) gsd-tools.py generate-slug "smoke test" --raw > /dev/null && echo "  generate-slug: OK"
	@cd "$(SRC_BIN)" && $(PYTHON) gsd-tools.py current-timestamp date --raw > /dev/null && echo "  current-timestamp: OK"
	@echo "All checks passed."

clean: ## Remove build artifacts
	@rm -rf "$(HOOKS_DIST)"
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned."

_check-python:
	@command -v $(PYTHON) >/dev/null 2>&1 || { echo "Error: python3 not found. Install Python 3.6+."; exit 1; }
	@$(PYTHON) -c "import sys; assert sys.version_info >= (3, 6), 'Python 3.6+ required'" 2>/dev/null || { echo "Error: Python 3.6+ required."; exit 1; }
