"""Prepara o entrena la demostración sintética sin base de datos ni aprobaciones ficticias."""
import argparse
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "train"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--measurements", type=Path)
    parser.add_argument("--base-directory", type=Path)
    parser.add_argument("--base-revision")
    parser.add_argument("--examples", type=Path, default=ROOT / "docs/ai-tutor/variantes/ejemplos-borrador.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-name", default="training")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_name):
        parser.error("run-name debe ser un nombre simple.")
    # Solo serializers/pipeline; no se carga oj.settings ni se conecta PostgreSQL.
    from django.conf import settings
    if not settings.configured:
        settings.configure(USE_I18N=False, USE_TZ=True, TIME_ZONE="UTC", INSTALLED_APPS=[])
    import django
    django.setup()
    from ai_tutor.dataset.pipeline import build_dataset, train, evaluate, canonical, sha
    from ai_tutor.ml.training import train_model

    if args.action == "train":
        result = train_model(args.output / "dataset", args.output / "selection.json", args.output / args.run_name,
                             resume=args.resume, technical_demo=True)
        print(canonical({"scope": result["scope"], "training": result["training"], "validation": result["validation"]}))
        return
    if not args.measurements or not args.base_directory or not args.base_revision:
        parser.error("prepare requiere measurements, base-directory y base-revision fijada.")
    if args.output.exists():
        parser.error("El destino ya existe; no se sobrescribe.")
    measured = json.loads(args.measurements.read_text(encoding="utf-8"))
    if len(measured.get("candidatos", [])) < 2 or measured.get("alcance") != "medicion-preliminar-sobre-borradores":
        parser.error("Se requiere una medición real de al menos dos candidatos sobre sintéticos.")
    base = args.base_directory.resolve()
    files = {path.name: sha(path) for path in base.iterdir() if path.is_file()}
    if "model.safetensors" not in files:
        parser.error("No se encontraron los pesos safetensors del modelo base.")
    source = {"model_id": "Qwen/Qwen2.5-Coder-1.5B-Instruct", "revision": args.base_revision, "license": "apache-2.0",
              "provenance": "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
              "snapshot_directory": str(base), "snapshot_files": files}
    reports = []
    for candidate in measured["candidatos"]:
        metadata = dict(candidate["candidato"])
        if metadata["model_id"] == "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF":
            metadata["training_model"] = source
        reports.append({"candidate": metadata, "latency_p50_ms": candidate["latencia_p50_ms"],
                        "latency_p95_ms": candidate["latencia_p95_ms"], "ram_peak_mib": candidate["ram_pico_mib"],
                        "responses": [{"example_id": row["example_id"], "status": row["estado"],
                                       "latency_ms": row["latencia_ms"], "content": row.get("muestra_respuesta", ""),
                                       "human_review": "not-performed"} for row in candidate["respuestas"]]})
    selected = next(item["candidate"] for item in reports if "training_model" in item["candidate"])
    args.output.mkdir(parents=True)
    benchmark = args.output / "benchmark-technical.json"
    benchmark.write_text(canonical({"scope": "technical-demo", "human_review": "not-performed",
                                    "source_sha256": sha(args.measurements), "reports": reports}), encoding="utf-8")
    selection = {**selected, "scope": "technical-demo", "decision": "demonstration", "human_review": "not-performed",
                 "rationale": "Candidato con menor latencia y RAM de los dos medidos bajo límites CPU; selección técnica, no pedagógica.",
                 "benchmark_file": benchmark.name, "benchmark_sha256": sha(benchmark), "rubric_version": "technical-1"}
    (args.output / "selection.json").write_text(canonical(selection), encoding="utf-8")
    records = json.loads(args.examples.read_text(encoding="utf-8"))
    manifest = build_dataset(records, args.output / "dataset", technical_demo=True)
    train(args.output / "dataset", args.output / "classifier.json", technical_demo=True)
    evaluation = evaluate(args.output / "dataset", args.output / "classifier.json", technical_demo=True)
    (args.output / "classifier-evaluation.json").write_text(canonical(evaluation), encoding="utf-8")
    print(canonical({"scope": "technical-demo", "source_records": len(records), "counts": manifest["counts"],
                     "excluded_duplicates": len(manifest["excluded_duplicate_code_ids"]),
                     "classifier_macro_f1": evaluation["overall"]["macro_f1"], "human_approvals": 0}))


if __name__ == "__main__":
    main()
