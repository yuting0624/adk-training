#!/usr/bin/env bash
#
# ADK Training Workshop - Cloud Shell setup script
#
# Run from the repository root:
#   ./setup.sh
#
# Re-runnable. Stops on first error so problems surface immediately.

set -euo pipefail

# ---------- helpers ----------
log() { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command not found: $1"
    exit 1
  fi
}

# ---------- 0. preconditions ----------
log "Checking required commands..."
require_cmd gcloud
require_cmd curl
require_cmd python3

# ---------- 1. GCP project ----------
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  err "No GCP project configured. Run: gcloud config set project <PROJECT_ID>"
  exit 1
fi
log "GCP project: ${PROJECT_ID}"

# Vertex AI region default — change with GOOGLE_CLOUD_LOCATION env var
REGION="${GOOGLE_CLOUD_LOCATION:-us-central1}"
log "Vertex AI region: ${REGION}"

# ---------- 2. enable APIs ----------
log "Enabling required GCP APIs (this may take 1-2 min on first run)..."
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  maps-backend.googleapis.com \
  --project="${PROJECT_ID}"

# ---------- 3. install uv ----------
if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv (Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
else
  log "uv already installed: $(uv --version)"
fi

# ---------- 4. install dependencies ----------
log "Installing Python dependencies via uv..."
uv sync

# ---------- 5. .env ----------
if [[ ! -f .env ]]; then
  log "Creating .env from .env.example..."
  cp .env.example .env
fi

# Inject project + region into .env (idempotent)
python3 - "$PROJECT_ID" "$REGION" <<'PY'
import sys, pathlib, re
project_id, region = sys.argv[1], sys.argv[2]
path = pathlib.Path(".env")
text = path.read_text()
def setkv(key, value, t):
    pattern = rf"^{key}=.*$"
    line = f"{key}={value}"
    if re.search(pattern, t, flags=re.M):
        return re.sub(pattern, line, t, flags=re.M)
    return t.rstrip() + "\n" + line + "\n"
text = setkv("GOOGLE_CLOUD_PROJECT", project_id, text)
text = setkv("GOOGLE_CLOUD_LOCATION", region, text)
text = setkv("GOOGLE_GENAI_USE_VERTEXAI", "TRUE", text)
path.write_text(text)
PY

# Maps API key warning
if ! grep -qE '^MAPS_API_KEY=.+' .env || grep -qE '^MAPS_API_KEY=YOUR_' .env; then
  warn "MAPS_API_KEY is not set in .env. Section 2-2b (MCP) will fail without it."
  warn "Set it manually: edit .env and replace YOUR_MAPS_API_KEY_HERE"
fi

# ---------- 6. ADC ----------
log "Verifying Application Default Credentials..."
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  warn "ADC not configured. Run: gcloud auth application-default login"
  warn "Then re-run this script."
  exit 1
fi
gcloud auth application-default set-quota-project "${PROJECT_ID}" >/dev/null 2>&1 || true

# ---------- 7. smoke test ----------
log "Running smoke test (import Agent + Workflow, check adk CLI)..."
if uv run python -c "
from google.adk import Agent, Workflow
from google.adk.tools.mcp_tool import McpToolset
import google.adk
print('ADK version:', getattr(google.adk, '__version__', 'unknown'))
"; then
  log "Python import OK."
else
  err "Smoke test failed: could not import google.adk (Agent / Workflow / McpToolset)."
  exit 1
fi

if uv run adk --version >/dev/null 2>&1; then
  log "adk CLI OK: $(uv run adk --version 2>&1 | head -1)"
else
  err "adk CLI not available."
  exit 1
fi

# ---------- done ----------
cat <<EOF

\033[1;32m[setup] Done.\033[0m
Next: open the workshop materials and start at Section 1-1
(\`adk create\` will scaffold app/agent.py during that section).

EOF
