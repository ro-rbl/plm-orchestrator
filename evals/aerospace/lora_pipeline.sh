#!/bin/zsh
# The aerospace 4B LoRA experiment, end to end (ROADMAP 3b). Rule committed first: evals/score_lora.py.
#   MLX_PY=<python with mlx-lm> LLAMACPP=<llama.cpp checkout> WORK=<scratch dir> evals/aerospace/lora_pipeline.sh
# Route proven in the preflight (NEXT.md): MLX LoRA -> fuse + dequantize -> llama.cpp GGUF -> Ollama.
# Both models go out as Q8_0 straight from the converter (no quantize tool is built here, and an f16
# import leaves an 8 GB blob behind), so the tuned model and its control share one route.
set -u
cd "$(dirname "$0")/../.."
BASE=mlx-community/Qwen3-4B-4bit
TUNED=plm-qwen3-4b-aero-lora
CONTROL=plm-qwen3-4b-control
mkdir -p "$WORK"

step() { echo "\n=== $1  $(date '+%H:%M:%S')"; }
drop_list_tokens() {  # mlx-lm writes extra_special_tokens as a list; the converter's transformers wants a dict
  $MLX_PY -c "import json,sys; p=sys.argv[1]; c=json.load(open(p)); c.pop('extra_special_tokens', None); json.dump(c, open(p,'w'), indent=2)" "$1/tokenizer_config.json"
}
to_ollama() {  # $1 = HF folder, $2 = Ollama name
  drop_list_tokens "$1"
  with-timeout 1800 $MLX_PY "$LLAMACPP/convert_hf_to_gguf.py" "$1" --outfile "$1.gguf" --outtype q8_0 || exit 1
  rm -rf "$1"
  printf "FROM $1.gguf\n" > "$1.Modelfile"
  with-timeout 1800 ollama create "$2" -f "$1.Modelfile" || exit 1
  rm -f "$1.gguf"
}

step "training data"
.venv/bin/python evals/aerospace/lora_train.py "$WORK/data" || exit 1

step "train LoRA (fixed before results: 600 iters, batch 4, 16 layers, lr 5e-5, prompt masked, seed 0)"
with-timeout 7200 $MLX_PY -m mlx_lm lora --model $BASE --train --data "$WORK/data" --iters 600 --batch-size 4 \
  --num-layers 16 --learning-rate 5e-5 --mask-prompt --seed 0 --steps-per-report 50 --steps-per-eval 100 \
  --val-batches 20 --adapter-path "$WORK/adapters" || exit 1

step "tuned model -> Ollama ($TUNED)"
with-timeout 1800 $MLX_PY -m mlx_lm fuse --model $BASE --adapter-path "$WORK/adapters" --save-path "$WORK/tuned" --dequantize || exit 1
to_ollama "$WORK/tuned" $TUNED

step "control: the same model and route, no adapter ($CONTROL)"
with-timeout 1800 $MLX_PY -m mlx_lm convert --hf-path $BASE --mlx-path "$WORK/control" --dequantize || exit 1
to_ollama "$WORK/control" $CONTROL

step "judge set, every model with the calculator"
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M $CONTROL $TUNED qwen3:8b; do
  with-timeout 3600 .venv/bin/python evals/run.py evals/aerospace/fresh_lora.jsonl --model "$m" --strategy tool || exit 1
done

step "verdict"
.venv/bin/python evals/score_lora.py
