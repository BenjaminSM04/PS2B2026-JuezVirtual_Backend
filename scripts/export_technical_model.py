"""Fusiona un adaptador experimental y produce GGUF con herramientas fijadas."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LLAMA_REVISION = "c7fc5094179bf8a9c73c18593db714f8da41a402"
LLAMA_IMAGE = "ghcr.io/ggml-org/llama.cpp:server@sha256:8c74db29f1a2bef3f0a331b52c4d6214601dfceed4bee0b94cc48b3b23ff257d"


def load_export_base(source, model_loader, tokenizer_loader, dtype):
    from ai_tutor.ml.training import model_location
    location = model_location(source)
    model = model_loader.from_pretrained(location, revision=source["revision"], dtype=dtype, device_map="cpu", use_safetensors=True, trust_remote_code=False)
    tokenizer = tokenizer_loader.from_pretrained(location, revision=source["revision"], trust_remote_code=False)
    return model, tokenizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--llama-directory", required=True, type=Path)
    parser.add_argument("--run-name", default="training-fp16")
    parser.add_argument("--runtime-name", default="runtime")
    args = parser.parse_args()
    if not all(re.fullmatch(r"[a-zA-Z0-9_-]+", value) for value in (args.run_name, args.runtime_name)):
        parser.error("Los nombres deben ser simples.")
    directory = args.directory.resolve()
    training = directory / args.run_name
    runtime = directory / args.runtime_name
    merged = directory / ("merged-" + args.runtime_name)
    result = json.loads((training / "training-result.json").read_text(encoding="utf-8"))
    if result.get("scope") != "technical-demo" or result.get("human_review") != "not-performed":
        parser.error("Solo se exportan aquí resultados reales del modo técnico.")
    if runtime.exists() or merged.exists():
        parser.error("El destino ya existe; elegir otro runtime-name para conservarlo.")
    revision = subprocess.check_output(["git", "-C", str(args.llama_directory), "rev-parse", "HEAD"], text=True).strip()
    if revision != LLAMA_REVISION:
        parser.error("El conversor no corresponde a la revisión fijada.")
    from django.conf import settings
    if not settings.configured:
        settings.configure(USE_I18N=False, INSTALLED_APPS=[])
    import django
    django.setup()
    from ai_tutor.dataset.pipeline import sha, canonical
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    source = result["training_model"]
    for name, digest in result["files"].items():
        file = (training / name).resolve()
        if not file.is_relative_to(training) or sha(file) != digest:
            parser.error("El adaptador cambió después del entrenamiento.")
    model, tokenizer = load_export_base(source, AutoModelForCausalLM, AutoTokenizer, torch.float16)
    model = PeftModel.from_pretrained(model, training / "adapter", is_trainable=False)
    merged_model = model.merge_and_unload(safe_merge=True)
    merged_model.save_pretrained(merged, safe_serialization=True, max_shard_size="2GB")
    tokenizer.save_pretrained(merged)
    del merged_model, model
    runtime.mkdir()
    float_model = directory / (args.runtime_name + "-f16.gguf")
    subprocess.run([sys.executable, str(args.llama_directory / "convert_hf_to_gguf.py"), str(merged), "--outfile", str(float_model), "--outtype", "f16"], check=True)
    subprocess.run(["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                    "--memory", "3g", "--cpus", "4", "--mount", "type=bind,source=" + str(directory) + ",target=/artifacts", "--entrypoint", "/app/llama",
                    LLAMA_IMAGE, "quantize", "--max-buffer-size", "512", "/artifacts/" + float_model.name,
                    "/artifacts/" + args.runtime_name + "/model.gguf", "Q4_K_M", "4"], check=True)
    shutil.copyfile(directory / "classifier.json", runtime / "classifier.json")
    generator_sha = sha(runtime / "model.gguf")
    manifest = {"scope": "technical-demo", "decision": "demonstration", "human_review": "not-performed", "license": source["license"],
                "model_revision": "sha256:" + generator_sha, "base_model_id": source["model_id"], "base_model_revision": source["revision"],
                "dataset_version": result["dataset_version"], "training_result_sha256": sha(training / "training-result.json"),
                "conversion_revision": revision, "quantization": "Q4_K_M", "created_at": datetime.now(timezone.utc).isoformat(),
                "generator": {"file": "model.gguf", "sha256": generator_sha},
                "classifier": {"file": "classifier.json", "sha256": sha(runtime / "classifier.json")}}
    (runtime / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    print(canonical({"scope": manifest["scope"], "model_sha256": generator_sha, "human_approvals": 0, "runtime": str(runtime)}))


if __name__ == "__main__":
    main()
