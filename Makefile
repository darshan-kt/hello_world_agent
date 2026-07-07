# ──────────────────────────────────────────────────────────
# Makefile — Hello Agent
# Usage: make <command>
# ──────────────────────────────────────────────────────────

IMAGE_NAME  := hello-agent
CONTAINER   := hello-agent-app
ENV_FILE    := .env
PORT        := 8000
DOCKERFILE  := docker/Dockerfile

# ── Colors ─────────────────────────────────────────────
GREEN  := \033[0;32m
CYAN   := \033[0;36m
YELLOW := \033[1;33m
RESET  := \033[0m

.PHONY: help up down build run run-cli run-msg stop logs shell clean rebuild dev dev-server _env_check

# ── Default target: show help ───────────────────────────
help:
	@echo ""
	@echo "  $(CYAN)🤖 Hello Agent — Make Commands$(RESET)"
	@echo "  ────────────────────────────────────────"
	@echo "  $(GREEN)make up$(RESET)             Start everything with Docker Compose (recommended)"
	@echo "  $(GREEN)make down$(RESET)           Stop the Compose stack"
	@echo "  $(GREEN)make build$(RESET)          Build the Docker image"
	@echo "  $(GREEN)make run$(RESET)            Start the web UI  →  http://localhost:$(PORT)"
	@echo "  $(GREEN)make run-cli$(RESET)        Start interactive CLI chat inside Docker"
	@echo "  $(GREEN)make run-msg MSG='...'$(RESET)  Send one message and exit"
	@echo "  $(GREEN)make stop$(RESET)           Stop the running container"
	@echo "  $(GREEN)make logs$(RESET)           Follow container logs"
	@echo "  $(GREEN)make shell$(RESET)          Open a shell inside the container"
	@echo "  $(GREEN)make rebuild$(RESET)        Stop → rebuild → run"
	@echo "  $(GREEN)make clean$(RESET)          Remove container and image"
	@echo "  $(GREEN)make dev$(RESET)            Run locally without Docker (venv)"
	@echo "  $(GREEN)make dev-server$(RESET)     Run web server locally without Docker"
	@echo ""

# ── Docker Compose (recommended) ────────────────────────
up: _env_check
	@echo "$(CYAN)▶ Starting Hello Agent (Docker Compose)...$(RESET)"
	docker compose up -d --build
	@echo "$(GREEN)✓ Running → http://localhost:$(PORT)$(RESET)"

down:
	docker compose down

# ── Build ───────────────────────────────────────────────
build:
	@echo "$(CYAN)▶ Building Docker image '$(IMAGE_NAME)'...$(RESET)"
	docker build -f $(DOCKERFILE) -t $(IMAGE_NAME) .
	@echo "$(GREEN)✓ Image built: $(IMAGE_NAME)$(RESET)"

# ── Run: Web Server (default) ───────────────────────────
run: _env_check
	@echo "$(CYAN)▶ Starting Hello Agent web server...$(RESET)"
	@echo "$(CYAN)  Open → http://localhost:$(PORT)$(RESET)"
	docker run -it --rm \
		--name $(CONTAINER) \
		--env-file $(ENV_FILE) \
		-e RUN_MODE=server \
		-p $(PORT):$(PORT) \
		-v $$(pwd)/data:/app/data \
		$(IMAGE_NAME)

# ── Run: CLI (interactive terminal chat) ────────────────
run-cli: _env_check
	@echo "$(CYAN)▶ Starting CLI chat...$(RESET)"
	docker run -it --rm \
		--name $(CONTAINER)-cli \
		--env-file $(ENV_FILE) \
		-e RUN_MODE=cli \
		-v $$(pwd)/data:/app/data \
		$(IMAGE_NAME)

# ── Run: Single message (non-interactive) ───────────────
run-msg: _env_check
	@[ -n "$(MSG)" ] || (echo "$(YELLOW)Usage: make run-msg MSG='your question here'$(RESET)" && exit 1)
	docker run --rm \
		--env-file $(ENV_FILE) \
		-e RUN_MODE=message \
		-e AGENT_MESSAGE="$(MSG)" \
		-v $$(pwd)/data:/app/data \
		$(IMAGE_NAME)

# ── Stop ────────────────────────────────────────────────
stop:
	@echo "$(CYAN)▶ Stopping container '$(CONTAINER)'...$(RESET)"
	@docker stop $(CONTAINER) 2>/dev/null || echo "  (container not running)"

# ── Logs ────────────────────────────────────────────────
logs:
	docker logs -f $(CONTAINER)

# ── Shell ───────────────────────────────────────────────
shell:
	@echo "$(CYAN)▶ Opening shell in '$(IMAGE_NAME)'...$(RESET)"
	docker run -it --rm \
		--entrypoint /bin/bash \
		--env-file $(ENV_FILE) \
		-v $$(pwd)/data:/app/data \
		$(IMAGE_NAME)

# ── Rebuild ─────────────────────────────────────────────
rebuild: stop build run

# ── Clean ───────────────────────────────────────────────
clean: stop
	@echo "$(CYAN)▶ Removing image '$(IMAGE_NAME)'...$(RESET)"
	@docker rmi $(IMAGE_NAME) 2>/dev/null || echo "  (image not found)"
	@echo "$(GREEN)✓ Cleaned$(RESET)"

# ── Local Dev (no Docker) ───────────────────────────────
dev:
	@[ -f .venv/bin/activate ] || python3 -m venv .venv
	@. .venv/bin/activate && pip install -q -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(RESET)"
	. .venv/bin/activate && python main.py

dev-server:
	@[ -f .venv/bin/activate ] || python3 -m venv .venv
	@. .venv/bin/activate && pip install -q -r requirements.txt
	@echo "$(CYAN)▶ Starting local server → http://localhost:$(PORT)$(RESET)"
	. .venv/bin/activate && python main.py --server

# ── Internal: check .env exists ─────────────────────────
_env_check:
	@[ -f $(ENV_FILE) ] || (echo "$(YELLOW)✗ .env file not found. Run: cp .env.example .env$(RESET)" && exit 1)
