"""Ajuste LoRA/QLoRA explícito sobre particiones aprobadas y selección documentada."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess

from ai_tutor.dataset.pipeline import load_dataset, canonical, sha
from ai_tutor.ml.prompt import training_messages


def training_dtype(torch):
    """bf16 solo con soporte nativo (capacidad >= 8.0); en Turing/T4 se emula y conviene fp16."""
    if not torch.cuda.is_available():
        return torch.float32
    return torch.bfloat16 if torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16


def training_source(selection, candidate):
    """No confundir el GGUF medido con los pesos safetensors de origen."""
    source = selection.get("training_model")
    if source is None:
        if "gguf" in selection["model_id"].casefold():
            raise ValueError("El candidato GGUF requiere training_model con procedencia safetensors revisada.")
        return {key: selection[key] for key in ("model_id", "revision", "license")}
    required = {"model_id", "revision", "license", "provenance"}
    if not isinstance(source, dict) or not required <= source.keys() or any(not isinstance(source[key], str) or not source[key].strip() for key in required):
        raise ValueError("training_model requiere model_id, revision, license y provenance no vacíos.")
    if "gguf" in source["model_id"].casefold() or not re.fullmatch(r"[0-9a-f]{40}", source["revision"]):
        raise ValueError("training_model debe identificar pesos entrenables y su revisión inmutable.")
    if candidate.get("training_model") != source:
        raise ValueError("training_model no coincide con la procedencia incluida en el benchmark revisado.")
    return source


def validate_selection(selection, benchmark, technical_demo=False):
    required = {"model_id", "revision", "license", "decision", "rubric_version"}
    if not required <= set(selection) or not selection["license"]:
        raise ValueError("Falta una selección revisada con licencia y evidencia de benchmark.")
    if technical_demo:
        if selection["decision"] != "demonstration" or selection.get("scope") != "technical-demo":
            raise ValueError("La selección debe declarar demostración técnica, sin aprobación humana.")
    elif selection["decision"] != "selected" or not selection.get("reviewer") or selection.get("scope") == "technical-demo":
        raise ValueError("Falta una selección con aprobación humana.")
    if not re.fullmatch(r"[0-9a-f]{40}", selection["revision"]):
        raise ValueError("La revisión del modelo debe ser un commit inmutable.")
    reports = benchmark.get("reports", [])
    candidates = {item["candidate"]["model_id"] for item in reports}
    selected = [item for item in reports if item["candidate"]["model_id"] == selection["model_id"] and item["candidate"]["revision"] == selection["revision"]]
    if len(candidates) < 2 or len(selected) != 1 or not selected[0].get("responses"):
        raise ValueError("Se requieren al menos dos candidatos medidos y una selección coincidente.")
    if not technical_demo and any(response.get("human_review") != "approved" for response in selected[0]["responses"]):
        raise ValueError("La muestra del modelo elegido requiere revisión humana real.")
    return training_source(selection, selected[0]["candidate"])


def model_location(source):
    if not source.get("snapshot_directory"):
        return source["model_id"]
    root = Path(source["snapshot_directory"]).resolve()
    files = source.get("snapshot_files")
    if not isinstance(files, dict) or not files or not any(name.endswith(".safetensors") for name in files):
        raise ValueError("El snapshot local requiere checksums de sus pesos safetensors.")
    for name, digest in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file() or sha(path) != digest:
            raise ValueError("El snapshot local no corresponde a los archivos fijados.")
    return str(root)


def train_model(dataset_directory, selection_path, output_directory, resume=False, quantized=True, technical_demo=False):
    partitions, dataset_manifest = load_dataset(dataset_directory, technical_demo=technical_demo)
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    if not {"benchmark_file", "benchmark_sha256"} <= selection.keys():
        raise ValueError("Falta evidencia de benchmark con checksum.")
    benchmark_path = (Path(selection_path).resolve().parent / selection["benchmark_file"]).resolve()
    if not re.fullmatch(r"[0-9a-f]{64}", selection["benchmark_sha256"]) or sha(benchmark_path) != selection["benchmark_sha256"]:
        raise ValueError("El checksum del benchmark revisado no coincide.")
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    source = validate_selection(selection, benchmark, technical_demo=technical_demo)
    location = model_location(source)
    output = Path(output_directory)
    if output.exists() and not resume:
        raise ValueError("El destino ya existe; use reanudación explícita.")
    if resume:
        old = json.loads((output / "training-input.json").read_text())
        if old != {"dataset": dataset_manifest["version"], "selection": sha(selection_path)}:
            raise ValueError("El checkpoint no corresponde a estos datos o modelo.")
    # Las dependencias grandes se importan solo después de validar datos y permisos.
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig,
                              DataCollatorForSeq2Seq, Trainer, TrainingArguments, set_seed)
    if quantized and not torch.cuda.is_available():
        raise ValueError("QLoRA requiere una GPU CUDA compatible. Para un ensayo LoRA en CPU use --no-quantization.")
    output.mkdir(parents=True, exist_ok=True)
    (output / "training-input.json").write_text(canonical({"dataset": dataset_manifest["version"], "selection": sha(selection_path)}))
    set_seed(2026)
    dtype = training_dtype(torch)
    config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype) if quantized else None
    tokenizer = AutoTokenizer.from_pretrained(location, revision=source["revision"], trust_remote_code=False,
                                              token=os.environ.get("HF_TOKEN"))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(location, revision=source["revision"], trust_remote_code=False,
        use_safetensors=True, token=os.environ.get("HF_TOKEN"), quantization_config=config,
        device_map="auto" if torch.cuda.is_available() else None, dtype=dtype)
    if quantized:
        model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM"))

    def encode(records):
        rows = []
        for record in records:
            for level, key in enumerate(("concept", "location", "strategy"), start=1):
                answer = canonical({"content": record["hints"][key], "uncertainty": record["uncertainty"]["reason"], "model_version": "adapter"}) + tokenizer.eos_token
                source = tokenizer.apply_chat_template(training_messages(record, level), tokenize=True, add_generation_prompt=True, return_dict=False)
                target = tokenizer.encode(answer, add_special_tokens=False)
                if len(source) + len(target) > 2048:
                    raise ValueError("Un ejemplo supera 2048 tokens; revise el presupuesto sin truncar silenciosamente la respuesta.")
                rows.append({"input_ids": source + target, "attention_mask": [1] * (len(source) + len(target)), "labels": [-100] * len(source) + target})
        return Dataset.from_list(rows)

    arguments = TrainingArguments(output_dir=str(output), seed=2026, data_seed=2026, num_train_epochs=3,
        per_device_train_batch_size=1, per_device_eval_batch_size=1, gradient_accumulation_steps=8,
        learning_rate=0.0002, eval_strategy="epoch", save_strategy="epoch", save_total_limit=2,
        report_to="none", logging_steps=10, bf16=dtype == torch.bfloat16, fp16=dtype == torch.float16, dataloader_num_workers=0)
    trainer = Trainer(model=model, args=arguments, train_dataset=encode(partitions["train"]), eval_dataset=encode(partitions["validation"]),
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True), processing_class=tokenizer)
    result = trainer.train(resume_from_checkpoint=True if resume else None)
    trainer.save_model(str(output / "adapter"))
    tokenizer.save_pretrained(str(output / "adapter"))
    metrics = {"training": result.metrics, "validation": trainer.evaluate(), "hardware": {"platform": platform.platform(),
        "cuda": torch.version.cuda, "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "dtype": str(dtype).replace("torch.", "")},
        "scope": dataset_manifest.get("scope", "reviewed"), "human_review": "not-performed" if technical_demo else "recorded-in-selection",
        "dataset_version": dataset_manifest["version"], "selection_sha256": sha(selection_path), "training_model": source,
        "files": {str(file.relative_to(output)): sha(file) for file in (output / "adapter").rglob("*") if file.is_file()}}
    (output / "training-result.json").write_text(canonical(metrics), encoding="utf-8")
    # No publicar ni registrar variables de entorno que puedan contener credenciales.
    freeze = subprocess.check_output([os.sys.executable, "-m", "pip", "freeze"], text=True)
    (output / "environment.txt").write_text(freeze, encoding="utf-8")
    return metrics
