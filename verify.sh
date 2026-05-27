#!/usr/bin/env bash
#
# ADK Training Workshop - preflight verification
#
# Run after setup.sh and after editing .env, to catch common misconfigurations
# (mapstools not enabled, API key restricted, model not callable, broken adk
# CLI on PATH, etc.) BEFORE the workshop starts.
#
# Run from the repository root:
#   ./verify.sh

set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; PASS=$((PASS+1)); }
fail() { printf '\033[1;31m[FAIL]\033[0m %s\n' "$*"; FAIL=$((FAIL+1)); }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*"; WARN=$((WARN+1)); }
info() { printf '\033[1;34m[ .. ]\033[0m %s\n' "$*"; }

# ---------- 1. required commands ----------
info "Checking required commands..."
for cmd in gcloud uv curl python3; do
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd is available"
  else
    fail "$cmd is missing"
  fi
done

# ---------- 2. .env present and loaded ----------
if [[ -f .env ]]; then
  ok ".env exists"
  set -a; source .env; set +a
else
  fail ".env is missing — run ./setup.sh first"
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"

if [[ -n "${PROJECT_ID}" && "${PROJECT_ID}" != "(unset)" ]]; then
  ok "GCP project: ${PROJECT_ID}"
else
  fail "GCP project not configured — gcloud config set project <ID>"
fi

# ---------- 3. APIs enabled ----------
info "Checking required APIs are enabled on ${PROJECT_ID}..."
enabled_apis="$(gcloud services list --enabled --project="${PROJECT_ID}" \
  --format='value(config.name)' 2>/dev/null || true)"
for api in aiplatform.googleapis.com mapstools.googleapis.com run.googleapis.com cloudbuild.googleapis.com; do
  if echo "${enabled_apis}" | grep -q "^${api}$"; then
    ok "${api} enabled"
  else
    fail "${api} NOT enabled — gcloud services enable ${api}"
  fi
done

# ---------- 4. adk CLI is the project venv one ----------
adk_path="$(command -v adk 2>/dev/null || true)"
if [[ -n "${adk_path}" ]]; then
  case "${adk_path}" in
    *.venv/bin/adk|*/.local/share/uv/*)
      ok "adk on PATH: ${adk_path} (project venv)"
      ;;
    *)
      warn "adk on PATH is ${adk_path} (NOT the project venv)."
      warn "  Always run 'uv run adk ...' to ensure the right one is used."
      ;;
  esac
fi

# Project venv adk should work
if uv run --no-sync adk --version >/dev/null 2>&1; then
  ok "uv run adk: $(uv run --no-sync adk --version 2>&1 | tail -1)"
else
  fail "uv run adk fails — try './setup.sh' or 'uv sync'"
fi

# ---------- 5. MAPS_API_KEY set ----------
if [[ -z "${MAPS_API_KEY:-}" ]] || [[ "${MAPS_API_KEY}" == YOUR_* ]]; then
  fail "MAPS_API_KEY is not set in .env (still placeholder)"
else
  ok "MAPS_API_KEY is set (${#MAPS_API_KEY} chars)"
fi

# ---------- 6. MAPS_API_KEY can hit mapstools.googleapis.com/mcp ----------
if [[ -n "${MAPS_API_KEY:-}" && "${MAPS_API_KEY}" != YOUR_* ]]; then
  info "Probing mapstools.googleapis.com MCP endpoint..."
  http_code="$(curl -s -o /dev/null -w '%{http_code}' \
    -X POST 'https://mapstools.googleapis.com/mcp' \
    -H "X-Goog-Api-Key: ${MAPS_API_KEY}" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"verify.sh","version":"1.0"}}}' \
    --max-time 10 2>/dev/null || echo "000")"

  case "${http_code}" in
    200|202)
      ok "mapstools.googleapis.com responds OK (HTTP ${http_code})"
      ;;
    403)
      fail "mapstools.googleapis.com returns 403 — API key restrictions exclude Maps Grounding Lite, or API not enabled"
      ;;
    401)
      fail "mapstools.googleapis.com returns 401 — MAPS_API_KEY is invalid"
      ;;
    000)
      warn "mapstools.googleapis.com unreachable (network / DNS issue?)"
      ;;
    *)
      warn "mapstools.googleapis.com returned HTTP ${http_code} (unexpected)"
      ;;
  esac
fi

# ---------- 7. ADC + quota project ----------
if gcloud auth application-default print-access-token >/dev/null 2>&1; then
  ok "Application Default Credentials work"
  if [[ -n "${PROJECT_ID}" ]]; then
    gcloud auth application-default set-quota-project "${PROJECT_ID}" >/dev/null 2>&1 || true
    ok "ADC quota project set to ${PROJECT_ID}"
  fi
else
  fail "ADC not configured — run: gcloud auth application-default login"
fi

# ---------- 8. Gemini model callable ----------
MODEL="${ADK_TRAINING_MODEL:-gemini-3.5-flash}"
if [[ -n "${PROJECT_ID}" ]] && gcloud auth application-default print-access-token >/dev/null 2>&1; then
  info "Probing Vertex AI ${MODEL} (location=${LOCATION})..."
  if [[ "${LOCATION}" == "global" ]]; then
    endpoint="https://aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/global/publishers/google/models/${MODEL}:generateContent"
  else
    endpoint="https://${LOCATION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/publishers/google/models/${MODEL}:generateContent"
  fi
  http_code="$(curl -s -o /tmp/verify_gemini_$$.json -w '%{http_code}' \
    -X POST "${endpoint}" \
    -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
    -H 'Content-Type: application/json' \
    -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}],"generationConfig":{"maxOutputTokens":5}}' \
    --max-time 30 2>/dev/null || echo "000")"
  case "${http_code}" in
    200)
      ok "Vertex AI ${MODEL} @ ${LOCATION} is callable"
      ;;
    403|404)
      fail "Vertex AI ${MODEL} @ ${LOCATION} returned ${http_code} — model not enabled / not accessible. Try ADK_TRAINING_MODEL=gemini-2.5-flash ./verify.sh"
      ;;
    *)
      warn "Vertex AI ${MODEL} returned HTTP ${http_code}. Response head:"
      head -c 500 /tmp/verify_gemini_$$.json 2>/dev/null || true
      ;;
  esac
  rm -f /tmp/verify_gemini_$$.json
fi

# ---------- 9. AgentLoader sanity (catches Python import errors) ----------
info "Probing agent module imports..."
if MAPS_API_KEY="${MAPS_API_KEY:-DUMMY_FOR_IMPORT_ONLY}" uv run --no-sync python -c "
from google.adk.cli.utils.agent_loader import AgentLoader
loader = AgentLoader('.')
loader.load_agent('app')
" >/dev/null 2>&1; then
  ok "app/ agent imports cleanly"
else
  fail "app/agent.py has an import error — run: MAPS_API_KEY=DUMMY uv run python -c 'from google.adk.cli.utils.agent_loader import AgentLoader; AgentLoader(\".\").load_agent(\"app\")'"
fi

# ---------- summary ----------
echo
printf '\033[1m=== Summary ===\033[0m\n'
printf '  PASS: %d\n  WARN: %d\n  FAIL: %d\n' "${PASS}" "${WARN}" "${FAIL}"
if [[ ${FAIL} -gt 0 ]]; then
  printf '\033[1;31m\nverify FAILED — fix the issues above before the workshop.\033[0m\n'
  exit 1
elif [[ ${WARN} -gt 0 ]]; then
  printf '\033[1;33m\nverify passed with warnings — review and proceed at your discretion.\033[0m\n'
  exit 0
else
  printf '\033[1;32m\nverify passed cleanly. You are ready.\033[0m\n'
  exit 0
fi
