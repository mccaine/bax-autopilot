# BAX Autopilot — root control surface. Every service runs from here.
.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help up run down logs ps kickoff build-image test fmt lint dev-orchestrator rebuild purge reset

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Build + start the harness (dashboard + orchestrator + postgres)
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build
	@echo "Dashboard:    http://localhost:3000"
	@echo "Orchestrator: http://localhost:8080  (health: /healthz)"

run: up ## Alias for `up`

down: ## Stop the harness
	$(COMPOSE) down

logs: ## Tail orchestrator logs
	$(COMPOSE) logs -f orchestrator

ps: ## Show harness services
	$(COMPOSE) ps

kickoff: ## Start a run:  make kickoff INTENT="a todo app with auth"
	@test -n "$(INTENT)" || (echo "usage: make kickoff INTENT=\"...\"" && exit 1)
	./bin/bax "$(INTENT)"

build-image: ## Build only the orchestrator image
	$(COMPOSE) build orchestrator

rebuild: ## Rebuild + restart the orchestrator and dashboard images (after code changes)
	$(COMPOSE) build orchestrator dashboard
	$(COMPOSE) up -d --force-recreate orchestrator dashboard
	@echo "Rebuilt. Dashboard: http://localhost:3000"

purge: ## DANGER: delete ALL projects — db state, workspaces/, runs/, generated-app stacks
	@echo ">> Tearing down any leftover generated-app stacks…"
	-@for p in $$(docker compose ls -a --format '{{.Name}}' 2>/dev/null | grep '^autopilot-' || true); do \
		echo "   down $$p"; docker compose -p "$$p" down -v --rmi local --remove-orphans 2>/dev/null || true; \
	done
	@echo ">> Removing harness + database volume (projects + checkpointer state)…"
	$(COMPOSE) down -v
	@echo ">> Wiping workspaces/ and runs/ (keeping .gitkeep)…"
	rm -rf workspaces/* runs/*
	@echo "Purged. Run 'make up' for a clean start."

reset: purge up ## Full clean slate: purge everything, then rebuild + start

test: ## Run orchestrator unit tests inside the image
	$(COMPOSE) run --rm --no-deps orchestrator python -m pytest -q

fmt: ## Format orchestrator code
	$(COMPOSE) run --rm --no-deps orchestrator ruff format autopilot tests

lint: ## Lint orchestrator code
	$(COMPOSE) run --rm --no-deps orchestrator ruff check autopilot tests

dev-orchestrator: ## Run the orchestrator on the host (needs pyenv 3.12 venv)
	cd services/orchestrator && python -m uvicorn autopilot.server:app --reload --port 8080
