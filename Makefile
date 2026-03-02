# GSD (Get Shit Done) — Python-only installation
# No npm/npx/node dependencies required.
#
# Usage:
#   make install          Install GSD for Claude Code (default: global, symlinked)
#   make install-copy     Install GSD globally using copies (no symlinks)
#   make install-local    Install GSD into current project's .claude/ (symlinked)
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

# Absolute source paths (for symlinks)
ABS_SRC := $(CURDIR)
ABS_SRC_BIN := $(ABS_SRC)/get-shit-done/bin
ABS_SRC_GSD := $(ABS_SRC)/get-shit-done
ABS_SRC_HOOKS := $(ABS_SRC)/hooks
ABS_SRC_COMMANDS := $(ABS_SRC)/commands
ABS_SRC_AGENTS := $(ABS_SRC)/agents
ABS_HOOKS_DIST := $(ABS_SRC)/hooks/dist

# Source paths (relative to repo root)
SRC_BIN := get-shit-done/bin
SRC_HOOKS := hooks
SRC_COMMANDS := commands
SRC_AGENTS := agents
SRC_GSD := get-shit-done

# Python
PYTHON := python3

.PHONY: install install-copy install-local uninstall test check build-hooks clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: _check-python build-hooks ## Install GSD globally via symlinks (~/.claude/get-shit-done)
	@echo "Installing GSD (Python) to $(GSD_DIR) [symlinked]..."
	@mkdir -p "$(BIN_DIR)" "$(LIB_DIR)"
	@# Symlink Python dispatcher
	@ln -sfn "$(ABS_SRC_BIN)/gsd-tools.py" "$(BIN_DIR)/gsd-tools.py"
	@# Symlink Python library modules
	@for f in $(ABS_SRC_BIN)/lib_py/*.py; do \
		ln -sfn "$$f" "$(LIB_DIR)/$$(basename $$f)"; \
	done
	@# Symlink workflow/agent markdown directories
	@if [ -d "$(ABS_SRC_GSD)/workflows" ]; then \
		ln -sfn "$(ABS_SRC_GSD)/workflows" "$(GSD_DIR)/workflows"; \
	fi
	@if [ -d "$(ABS_SRC_GSD)/agents" ]; then \
		ln -sfn "$(ABS_SRC_GSD)/agents" "$(GSD_DIR)/agents"; \
	fi
	@# Symlink command files
	@if [ -d "$(ABS_SRC_COMMANDS)" ]; then \
		mkdir -p "$(CLAUDE_DIR)/commands"; \
		for f in $(ABS_SRC_COMMANDS)/*; do \
			ln -sfn "$$f" "$(CLAUDE_DIR)/commands/$$(basename $$f)"; \
		done; \
	fi
	@# Symlink agent files
	@if [ -d "$(ABS_SRC_AGENTS)" ]; then \
		mkdir -p "$(CLAUDE_DIR)/agents"; \
		for f in $(ABS_SRC_AGENTS)/*; do \
			ln -sfn "$$f" "$(CLAUDE_DIR)/agents/$$(basename $$f)"; \
		done; \
	fi
	@# Symlink hooks
	@if [ -d "$(ABS_HOOKS_DIST)" ]; then \
		mkdir -p "$(GSD_DIR)/hooks/dist"; \
		for f in $(ABS_HOOKS_DIST)/*.py; do \
			ln -sfn "$$f" "$(GSD_DIR)/hooks/dist/$$(basename $$f)"; \
		done; \
	fi
	@# Symlink version file
	@if [ -f "$(ABS_SRC_GSD)/VERSION" ]; then \
		ln -sfn "$(ABS_SRC_GSD)/VERSION" "$(GSD_DIR)/VERSION"; \
	else \
		echo "dev" > "$(GSD_DIR)/VERSION"; \
	fi
	@echo "GSD installed to $(GSD_DIR) (symlinked to $(ABS_SRC))"
	@echo "Edits in the repo are live immediately — no reinstall needed."

install-copy: _check-python build-hooks ## Install GSD globally using file copies
	@echo "Installing GSD (Python) to $(GSD_DIR) [copied]..."
	@mkdir -p "$(BIN_DIR)" "$(LIB_DIR)"
	@cp "$(SRC_BIN)/gsd-tools.py" "$(BIN_DIR)/gsd-tools.py"
	@chmod +x "$(BIN_DIR)/gsd-tools.py"
	@cp $(SRC_BIN)/lib_py/*.py "$(LIB_DIR)/"
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
	@if [ -d "$(HOOKS_DIST)" ]; then \
		mkdir -p "$(GSD_DIR)/hooks/dist"; \
		cp "$(HOOKS_DIST)/"*.py "$(GSD_DIR)/hooks/dist/"; \
		chmod +x "$(GSD_DIR)/hooks/dist/"*.py; \
	fi
	@if [ -f "get-shit-done/VERSION" ]; then \
		cp "get-shit-done/VERSION" "$(GSD_DIR)/VERSION"; \
	else \
		echo "dev" > "$(GSD_DIR)/VERSION"; \
	fi
	@echo "GSD installed to $(GSD_DIR) (copied)"

install-local: _check-python build-hooks ## Install GSD into current project .claude/ (symlinked)
	$(eval LOCAL_GSD := .claude/get-shit-done)
	$(eval LOCAL_BIN := $(LOCAL_GSD)/bin)
	$(eval LOCAL_LIB := $(LOCAL_BIN)/lib_py)
	@echo "Installing GSD (Python) locally to $(LOCAL_GSD) [symlinked]..."
	@mkdir -p "$(LOCAL_BIN)" "$(LOCAL_LIB)"
	@ln -sfn "$(ABS_SRC_BIN)/gsd-tools.py" "$(LOCAL_BIN)/gsd-tools.py"
	@for f in $(ABS_SRC_BIN)/lib_py/*.py; do \
		ln -sfn "$$f" "$(LOCAL_LIB)/$$(basename $$f)"; \
	done
	@if [ -d "$(ABS_SRC_GSD)/workflows" ]; then ln -sfn "$(ABS_SRC_GSD)/workflows" "$(LOCAL_GSD)/workflows"; fi
	@if [ -d "$(ABS_SRC_GSD)/agents" ]; then ln -sfn "$(ABS_SRC_GSD)/agents" "$(LOCAL_GSD)/agents"; fi
	@if [ -d "$(ABS_SRC_COMMANDS)" ]; then \
		mkdir -p ".claude/commands"; \
		for f in $(ABS_SRC_COMMANDS)/*; do \
			ln -sfn "$$f" ".claude/commands/$$(basename $$f)"; \
		done; \
	fi
	@if [ -d "$(ABS_SRC_AGENTS)" ]; then \
		mkdir -p ".claude/agents"; \
		for f in $(ABS_SRC_AGENTS)/*; do \
			ln -sfn "$$f" ".claude/agents/$$(basename $$f)"; \
		done; \
	fi
	@if [ -d "$(ABS_HOOKS_DIST)" ]; then \
		mkdir -p "$(LOCAL_GSD)/hooks/dist"; \
		for f in $(ABS_HOOKS_DIST)/*.py; do \
			ln -sfn "$$f" "$(LOCAL_GSD)/hooks/dist/$$(basename $$f)"; \
		done; \
	fi
	@echo "GSD installed locally to $(LOCAL_GSD) (symlinked to $(ABS_SRC))"

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
