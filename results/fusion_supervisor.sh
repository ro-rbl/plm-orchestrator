#!/bin/zsh
# Overnight supervisor: waits for AC power, keeps qwen3:8b from staying pinned (the user's assistant pins it
# "Forever"; a pinned 8B leaves the coder no room), resumes a run after a stall, and stops everything at the
# deadline (HH:MM, default 05:30) so the assistant has Ollama to itself by morning.
# ALLOW_BATTERY=1: start without AC, but stop (to resume later) when the battery falls below 25%.
# At the deadline it also unloads the models the runs use (the coder and the 4B), never the assistant's qwen3:8b.
# Usage: results/fusion_supervisor.sh [run script] [deadline] >> <log> 2>&1 &
cd "$(dirname "$0")/.."
run=${1:-results/run_fusion_judged.sh}
deadline=${2:-05:30}
log() { print -r -- "[supervisor $(date +%H:%M)] $*"; }
on_ac() { pmset -g batt | grep -q "AC Power"; }
battery() { pmset -g batt | grep -o "[0-9]*%" | tr -d %; }
power_ok() { on_ac || { [[ -n "$ALLOW_BATTERY" ]] && (( $(battery) >= 25 )); }; }
unload_ours() { for m in qwen2.5-coder:14b hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M; do ollama stop $m >/dev/null 2>&1; done; log "unloaded the coder and the 4B"; }
past_deadline() { [[ "$(date +%H:%M)" > "$deadline" && "$(date +%H:%M)" < "12:00" ]]; }
for attempt in {1..20}; do
  until power_ok; do past_deadline && { log "deadline"; unload_ours; exit 2; }; log "waiting for AC power (battery $(battery)%)"; sleep 120; done
  past_deadline && { log "deadline reached before starting"; unload_ours; exit 2; }
  ollama ps | grep -q "qwen3:8b.*Forever" && { log "unpinning qwen3:8b"; ollama stop qwen3:8b >/dev/null 2>&1; }
  ( while true; do sleep 30; ollama ps | grep -q "qwen3:8b.*Forever" && { log "unpinning qwen3:8b"; ollama stop qwen3:8b >/dev/null 2>&1; }; done ) &
  watcher=$!
  $run &
  job=$!
  log "attempt $attempt: $run (pid $job)"
  while kill -0 $job 2>/dev/null; do
    if past_deadline; then log "deadline: stopping the run (it resumes later)"; pkill -P $job; kill $job; break; fi
    if ! power_ok; then log "battery $(battery)% and no AC: pausing the run (it resumes)"; pkill -P $job; kill $job; break; fi
    sleep 30
  done
  wait $job; rc=$?
  kill $watcher 2>/dev/null
  past_deadline && { log "stopped at the deadline"; unload_ours; exit 2; }
  if [[ $rc -eq 0 ]]; then log "finished"; [[ -n "$UNLOAD_AT_END" ]] && unload_ours; exit 0; fi
  log "run stopped (exit $rc); retrying in 2 min"
  sleep 120
done
log "gave up after 20 attempts"
exit 1
