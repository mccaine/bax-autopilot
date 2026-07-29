FROM python:3.12-slim

# Tools the agents drive: docker CLI (docker-out-of-docker), git, gh, terraform, curl.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates gnupg lsb-release unzip \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
    && curl -fsSL https://apt.releases.hashicorp.com/gpg -o /etc/apt/keyrings/hashicorp.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/hashicorp.asc] https://apt.releases.hashicorp.com $(. /etc/os-release && echo $VERSION_CODENAME) main" > /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        docker-ce-cli docker-compose-plugin gh terraform \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the repo root (see docker-compose.yml).
COPY services/orchestrator/pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY services/orchestrator/autopilot ./autopilot
COPY services/orchestrator/tests ./tests
# Ship the generated-app template so the scaffolder can render it in-container.
COPY stacks ./stacks

ENV AUTOPILOT_STACKS_DIR=/app/stacks

EXPOSE 8080
CMD ["uvicorn", "autopilot.server:app", "--host", "0.0.0.0", "--port", "8080"]
