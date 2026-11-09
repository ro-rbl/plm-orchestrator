#!/bin/zsh
# Double-click to open plm's full-screen interface in a Terminal window.
# It finds the repo it lives in (or PLM_HOME), makes sure Ollama is answering, sizes the window, and runs plm.
# A copy elsewhere (e.g. on the Desktop) works too: set PLM_HOME below, or keep the default path.
PLM_HOME=${PLM_HOME:-$HOME/ClaudeCoding/plm-orchestrator}
[[ -x "${0:A:h}/.venv/bin/plm" ]] && PLM_HOME=${0:A:h}
cd "$PLM_HOME" || { echo "plm: can't find $PLM_HOME (set PLM_HOME in this file)"; read -k1; exit 1; }

printf '\e]0;plm\a'          # window title
printf '\e[8;46;160t'        # 46 rows x 160 columns, room for the side panel

ollama_up() { curl -s -m 2 "${OLLAMA_HOST:-http://127.0.0.1:11434}/api/version" | grep -q version; }
if ! ollama_up; then
  echo "plm: Ollama isn't answering; starting it..."
  if command -v brew >/dev/null && brew services list 2>/dev/null | grep -q '^ollama'; then
    brew services start ollama >/dev/null
  elif [[ -d /Applications/Ollama.app ]]; then
    open -a Ollama
  fi
  for i in {1..30}; do ollama_up && break; sleep 1; done
  ollama_up || { echo "plm: Ollama still isn't answering. Start it (ollama serve) and try again."; read -k1; exit 1; }
fi

[[ -n "$PLM_COMMAND_DRYRUN" ]] && { echo "dry run: would start $PLM_HOME/.venv/bin/plm"; exit 0; }
exec "$PLM_HOME/.venv/bin/plm"
