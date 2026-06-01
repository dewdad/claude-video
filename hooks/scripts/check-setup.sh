#!/usr/bin/env bash
# SessionStart hook for /watch — one-line status so users know what's wired up.
# Silent on ready state to avoid spam. Points at the installer when something
# is missing.
set -euo pipefail

# Mirror the Python scripts' resolution order: ~/.config/watch/.env (canonical)
# then a project-local .env (cwd fallback). See whisper.py:65, multimodal.py:43.
CANONICAL_CONFIG="$HOME/.config/watch/.env"
LOCAL_CONFIG="$(pwd)/.env"

CONFIG_FILES=()
[[ -f "$CANONICAL_CONFIG" ]] && CONFIG_FILES+=("$CANONICAL_CONFIG")
[[ -f "$LOCAL_CONFIG" && "$LOCAL_CONFIG" != "$CANONICAL_CONFIG" ]] && CONFIG_FILES+=("$LOCAL_CONFIG")

# Warn if the canonical secrets file has loose permissions. (Try BSD stat first
# since the documented default platform is macOS; fall back to GNU stat.)
if [[ -f "$CANONICAL_CONFIG" ]]; then
  perms=$(stat -f '%Lp' "$CANONICAL_CONFIG" 2>/dev/null || stat -c '%a' "$CANONICAL_CONFIG" 2>/dev/null || echo "")
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    echo "/watch: WARNING — $CANONICAL_CONFIG has permissions $perms (should be 600)."
    echo "  Fix: chmod 600 $CANONICAL_CONFIG"
  fi
fi

# Load API keys from env first, then any config file (canonical wins over cwd).
read_key() {
  local name="$1"
  if [[ -n "${!name:-}" ]]; then
    echo "${!name}"
    return
  fi
  for cfg in "${CONFIG_FILES[@]}"; do
    local value
    value=$(awk -F= -v k="$name" '
      /^[[:space:]]*#/ { next }
      $1 == k {
        sub(/^[[:space:]]*/, "", $2); sub(/[[:space:]]*$/, "", $2);
        gsub(/^["'\'']|["'\'']$/, "", $2);
        print $2; exit
      }
    ' "$cfg")
    if [[ -n "$value" ]]; then
      echo "$value"
      return
    fi
  done
}

HAS_FFMPEG=""
HAS_YTDLP=""
command -v ffmpeg >/dev/null 2>&1 && HAS_FFMPEG="yes"
command -v yt-dlp >/dev/null 2>&1 && HAS_YTDLP="yes"

HAS_GROQ="$(read_key GROQ_API_KEY)"
HAS_OPENAI="$(read_key OPENAI_API_KEY)"
HAS_MULTIMODAL="$(read_key MULTIMODAL_API_KEY)"
HAS_NGC="$(read_key NGC_API_KEY)"
SETUP_COMPLETE="$(read_key SETUP_COMPLETE)"

if [[ "$SETUP_COMPLETE" == "true" && -n "$HAS_FFMPEG" && -n "$HAS_YTDLP" ]]; then
  exit 0
fi

if [[ -z "$HAS_FFMPEG" || -z "$HAS_YTDLP" ]]; then
  echo "/watch: needs ffmpeg + yt-dlp. Run \`python3 \$SKILL_DIR/scripts/setup.py\` once to install and scaffold config."
elif [[ -z "$HAS_GROQ" && -z "$HAS_OPENAI" && -z "$HAS_MULTIMODAL" && -z "$HAS_NGC" ]]; then
  echo "/watch: ready for videos with native captions. Add GROQ_API_KEY, OPENAI_API_KEY, or MULTIMODAL_API_KEY to ~/.config/watch/.env to unlock transcription fallbacks."
else
  echo "/watch: ready."
fi
