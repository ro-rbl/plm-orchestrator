#!/bin/zsh
# Q8_0 vs Q4_K_M small tier (evals/score_quant.py, rule QUANT_RULE fixed before this ran).
# The Q8_0 4B on the three eval sets; all four model setups on the fresh sets. The Q4_K_M and 8B
# answers on the eval sets are the saved ones. Resumes: problems already in a results file are skipped.
cd "$(dirname "$0")/.."
Q4=hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M
Q8=hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q8_0
# A missing model would be saved as error rows, which resuming then skips: refuse instead.
ollama list | grep -q "Qwen_Qwen3-4B-GGUF:Q8_0" || { echo "pull $Q8 first"; exit 1; }
for p in electrical aerospace physics; do
  with-timeout 3600 .venv/bin/python evals/run.py evals/$p/problems.jsonl --model $Q8 --strategy tool
done
for p in electrical aerospace physics; do
  for m in $Q4 $Q8 qwen3:8b; do
    with-timeout 1800 .venv/bin/python evals/run.py evals/$p/fresh_quant.jsonl --model $m --strategy tool
  done
  with-timeout 1800 .venv/bin/python evals/run.py evals/$p/fresh_quant.jsonl --model qwen3:8b
done
.venv/bin/python evals/score_quant.py
