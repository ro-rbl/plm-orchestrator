#!/bin/zsh
# Overnight supervisor for the FUSE_RULE run: waits for AC power, keeps qwen3:8b from staying pinned
# (the user's assistant pins it "Forever"; a pinned 8B leaves the coder no room), and resumes the run
# after a stall. Usage: results/fusion_supervisor.sh >> results/fusion_judged_m.log 2>&1 &
cd "$(dirname "$0")/.."
log() { print -r -- "[supervisor $(date +%H:%M)] $*"; }
for attempt in {1..20}; do
  until pmset -g batt | grep -q "AC Power"; do log "waiting for AC power"; sleep 300; done
  ollama ps | grep -q "qwen3:8b.*Forever" && { log "unpinning qwen3:8b"; ollama stop qwen3:8b >/dev/null 2>&1; }
  ( while true; do sleep 30; ollama ps | grep -q "qwen3:8b.*Forever" && { log "unpinning qwen3:8b"; ollama stop qwen3:8b >/dev/null 2>&1; }; done ) &
  watcher=$!
  log "attempt $attempt"
  results/run_fusion_judged.sh
  rc=$?
  kill $watcher 2>/dev/null
  if [[ $rc -eq 0 ]]; then log "finished"; exit 0; fi
  log "run stopped (exit $rc); retrying in 2 min"
  sleep 120
done
log "gave up after 20 attempts"
exit 1
