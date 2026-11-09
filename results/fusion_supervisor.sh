#!/bin/zsh
# Overnight supervisor: waits for AC power, keeps qwen3:8b from staying pinned (the user's assistant pins it
# "Forever"; a pinned 8B leaves the coder no room), resumes a run after a stall, and stops everything at the
# deadline (HH:MM, default 05:30) so the assistant has Ollama to itself by morning.
# Usage: results/fusion_supervisor.sh [run script] [deadline] >> <log> 2>&1 &
cd "$(dirname "$0")/.."
run=${1:-results/run_fusion_judged.sh}
deadline=${2:-05:30}
log() { print -r -- "[supervisor $(date +%H:%M)] $*"; }
past_deadline() { [[ "$(date +%H:%M)" > "$deadline" && "$(date +%H:%M)" < "12:00" ]]; }
for attempt in {1..20}; do
  until pmset -g batt | grep -q "AC Power"; do past_deadline && { log "deadline"; exit 2; }; log "waiting for AC power"; sleep 300; done
  past_deadline && { log "deadline reached before starting"; exit 2; }
  ollama ps | grep -q "qwen3:8b.*Forever" && { log "unpinning qwen3:8b"; ollama stop qwen3:8b >/dev/null 2>&1; }
  ( while true; do sleep 30; ollama ps | grep -q "qwen3:8b.*Forever" && { log "unpinning qwen3:8b"; ollama stop qwen3:8b >/dev/null 2>&1; }; done ) &
  watcher=$!
  $run &
  job=$!
  log "attempt $attempt: $run (pid $job)"
  while kill -0 $job 2>/dev/null; do
    if past_deadline; then log "deadline: stopping the run (it resumes later)"; pkill -P $job; kill $job; break; fi
    sleep 30
  done
  wait $job; rc=$?
  kill $watcher 2>/dev/null
  past_deadline && { log "stopped at the deadline"; exit 2; }
  if [[ $rc -eq 0 ]]; then log "finished"; exit 0; fi
  log "run stopped (exit $rc); retrying in 2 min"
  sleep 120
done
log "gave up after 20 attempts"
exit 1
