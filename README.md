# BAX Autopilot

Autonomous multi-agent coding system. Give it an intent in plain English and it
drives a team of specialized agents to produce a working, tested, containerized
**microservice monorepo** (Next.js frontend + Node.js services + PostgreSQL) and
opens a git PR — no human in the loop.

The workflow runs locally on **`bax`** (Apple Studio M3 Ultra, 96 GB) using
**local Ollama models**. Claude is an optional, env-gated override. Generated
apps deploy to **GCP Cloud Run** via generated Terraform.

## Architecture at a glance

```
intent ─▶ spec ─▶ architect ─▶ scaffold ─▶ implement (fan-out per service)
                                                │
                                                ▼
                                   compose-up + integration/e2e test
                                                │
                              fail (iter<N) ┌──── review ────┐ approve
                                    fix ◀───┘                └──▶ terraform validate/plan
                                     ▲                                    │
                                     └────── loop ──────                  ▼
                                                             integrate (branch/commit/PR) ─▶ DONE
```

- **Orchestration:** LangGraph `StateGraph` with a bounded build→test→fix loop,
  hard step/iteration/token budgets, and a Postgres checkpointer (resumable).
- **Models:** `autopilot/models/registry.py` maps a *role* (coder / planner /
  router) to a LangChain chat model. Local (Ollama) by default; flip
  `AUTOPILOT_PROVIDER=anthropic` for Claude. Nothing else changes.
- **Sandbox:** the orchestrator mounts the Docker socket and runs all generated
  code (build / `docker compose up` / tests / terraform) in containers, never on
  the host.

## Quickstart (on bax)

```bash
# 0. Host prep (once)
pyenv install 3.12        # .python-version pins it
nvm install 20            # .nvmrc pins it
brew install ollama && ollama serve &
ollama pull qwen2.5-coder:32b
ollama pull qwen2.5:32b-instruct
ollama pull llama3.2:3b

# 1. Configure + run the harness
cp .env.example .env
make up                   # dashboard + orchestrator + postgres via docker compose

# 2. Kick off a run — from the dashboard or the CLI
#    Dashboard:  http://localhost:3000   (type an intent, click Start)
bin/bax "a full-stack todo app with email/password auth and a tasks API"
# ...or:  make kickoff INTENT="a todo app with auth"
```

Each intent becomes its own **project** in `workspaces/<run-id>/`. Only one
project runs at a time — additional intents queue and run in order. Watch
progress on the dashboard (Running / Queued / History with live journals), or
`make logs`. Run state lives in Postgres.

## Layout

| Path | What |
|---|---|
| `docker-compose.yml`, `Makefile`, `bin/bax` | Harness control surface (runs on bax) |
| `services/orchestrator/` | Python 3.12 + LangGraph agent graph + FastAPI control API |
| `stacks/microservice-monorepo/` | The generated-app stack template |
| `dashboard/` | Next.js control UI — submit intents, watch runs |
| `workspaces/`, `runs/` | Generated apps + logs (gitignored) |

## Configuration

All knobs live in `.env` (see `.env.example`). Highlights:

| Var | Default | Meaning |
|---|---|---|
| `AUTOPILOT_PROVIDER` | `ollama` | `ollama` (local) or `anthropic` (cloud) |
| `AUTOPILOT_MODEL_*` | qwen2.5 roster | Per-role local models |
| `AUTOPILOT_MAX_FIX_ITERS` | `6` | Build→test→fix loop cap |
| `AUTOPILOT_DEPLOY` | `plan` | `plan` = terraform validate+plan; `apply` = also apply (needs GCP creds) |

## Development

```bash
make test     # unit tests (mock models) inside the orchestrator image
make lint     # ruff
```
