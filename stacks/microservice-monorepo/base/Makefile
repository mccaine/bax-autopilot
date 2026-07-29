# Generated app — every service runs from this repo root.
.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down build test logs ps dev

help: ## Show targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Build + start the whole system (waits for healthchecks)
	$(COMPOSE) up -d --build --wait

dev: ## Start in the foreground with logs
	$(COMPOSE) up --build

build: ## Build all images
	$(COMPOSE) build

test: ## Run each Node service's tests against the running stack
	$(COMPOSE) up -d --build --wait
	@for svc in $$($(COMPOSE) config --services | grep -vE '^(db|frontend)$$'); do \
		echo "== testing $$svc =="; $(COMPOSE) exec -T $$svc npm test --silent || exit 1; \
	done

logs: ## Tail logs
	$(COMPOSE) logs -f

ps: ## Service status
	$(COMPOSE) ps

down: ## Stop and remove
	$(COMPOSE) down -v
