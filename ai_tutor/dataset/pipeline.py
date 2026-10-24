"""Versionado, partición por problema y clasificador reproducible sin dependencias pesadas."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re

from ai_tutor.dataset.schema import TutorExampleSerializer
from ai_tutor.ml.runtime import tokens, predict

CATEGORIES = ["compilation", "runtime", "logic", "complexity", "concept", "unknown"]


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_records(records, approved=True):
    if not isinstance(records, list) or not records:
        raise ValueError("Se requiere una lista no vacía de ejemplos.")
    ids = set()
    for index, item in enumerate(records):
        serializer = TutorExampleSerializer(data=item)
        if not serializer.is_valid():
            raise ValueError("Registro inválido en posición " + str(index) + ". Ejecute validate_tutor_examples.")
        if item["example_id"] in ids:
            raise ValueError("Identificador duplicado.")
        ids.add(item["example_id"])
        if approved and item["review"]["status"] != "approved":
            raise ValueError("No se admite entrenamiento o evaluación con ejemplos sin aprobación humana.")


def group(item):
    # El enunciado original es la identidad del grupo, compartida por sus variantes y lenguajes.
    return hashlib.sha256(" ".join(item["problem"].casefold().split()).encode()).hexdigest()


def build_dataset(records, output, seed=2026):
    validate_records(records)
    output = Path(output)
    groups = sorted({group(item) for item in records})
    if len(groups) < 3:
        raise ValueError("Se necesitan al menos tres problemas originales para separar train, validation y test.")
    random.Random(seed).shuffle(groups)
    test_count = max(1, len(groups) // 6)
    validation_count = max(1, len(groups) // 6)
    assignment = {key: "test" if index < test_count else ("validation" if index < test_count + validation_count else "train") for index, key in enumerate(groups)}
    partitions = {key: [] for key in ("train", "validation", "test")}
    for item in records:
        partitions[assignment[group(item)]].append(item)
    check_partitions(partitions)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": "1.0", "seed": seed, "source_sha256": hashlib.sha256(canonical(records).encode()).hexdigest(),
                "pipeline_sha256": sha(__file__), "files": {}, "counts": {}, "groups": assignment}
    for name, items in partitions.items():
        path = output / (name + ".jsonl")
        path.write_text("".join(canonical(item) + "\n" for item in sorted(items, key=lambda item: item["example_id"])), encoding="utf-8")
        manifest["files"][path.name] = sha(path)
        manifest["counts"][name] = dict(Counter(item["category"] for item in items))
    manifest["version"] = hashlib.sha256(canonical(manifest).encode()).hexdigest()
    (output / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
    return manifest


def check_partitions(partitions):
    seen_groups, seen_code, seen_ids = {}, {}, set()
    for name, items in partitions.items():
        validate_records(items)
        for item in items:
            code_hash = hashlib.sha256(item["faulty_code"].strip().encode()).hexdigest()
            if item["example_id"] in seen_ids or seen_groups.get(group(item), name) != name or seen_code.get(code_hash, name) != name:
                raise ValueError("Contaminación entre particiones o ejemplo duplicado.")
            seen_ids.add(item["example_id"])
            seen_groups[group(item)] = name
            seen_code[code_hash] = name


def load_dataset(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    identity = dict(manifest)
    version = identity.pop("version")
    if hashlib.sha256(canonical(identity).encode()).hexdigest() != version:
        raise ValueError("El manifiesto fue alterado.")
    parts = {}
    for name in ("train", "validation", "test"):
        path = directory / (name + ".jsonl")
        if sha(path) != manifest["files"][path.name]:
            raise ValueError("Una partición no coincide con su checksum.")
        parts[name] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    check_partitions(parts)
    return parts, manifest


def fit(records):
    validate_records(records)
    counts, documents, vocabulary = defaultdict(Counter), Counter(), set()
    for record in records:
        category = record["category"]
        documents[category] += 1
        features = tokens(record)
        counts[category].update(features)
        vocabulary.update(features)
    return {"algorithm": "multinomial-nb-1", "classes": dict(documents), "counts": {key: dict(value) for key, value in counts.items()},
            "vocabulary": sorted(vocabulary), "threshold": 0.65}


def metrics(expected, actual):
    matrix = {key: {other: 0 for other in CATEGORIES} for key in CATEGORIES}
    for target, predicted in zip(expected, actual):
        matrix[target][predicted] += 1
    categories = {}
    for key in CATEGORIES:
        true = matrix[key][key]
        support = sum(matrix[key].values())
        positives = sum(row[key] for row in matrix.values())
        precision = true / positives if positives else 0
        recall = true / support if support else 0
        categories[key] = {"precision": precision, "recall": recall, "support": support,
                           "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0}
    return {"macro_f1": sum(item["f1"] for item in categories.values()) / len(CATEGORIES), "categories": categories, "confusion": matrix}


def train(directory, output):
    parts, manifest = load_dataset(directory)
    model = fit(parts["train"])
    best_score, threshold = -1, None
    for candidate in (0.5, 0.65, 0.8, 0.9):
        model["threshold"] = candidate
        result = metrics([item["category"] for item in parts["validation"]], [predict(model, item)[0] for item in parts["validation"]])
        if result["macro_f1"] > best_score:
            best_score, threshold = result["macro_f1"], candidate
    model.update(threshold=threshold, dataset_version=manifest["version"], validation_macro_f1=best_score)
    with Path(output).open("x", encoding="utf-8") as stream:
        stream.write(canonical(model))
    return model


def evaluate(directory, model_path):
    parts, manifest = load_dataset(directory)
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    if model["dataset_version"] != manifest["version"]:
        raise ValueError("El modelo y el dataset no corresponden a la misma versión.")
    test = parts["test"]
    majority = max(model["classes"], key=model["classes"].get)
    return {"dataset_version": manifest["version"], "model_sha256": sha(model_path),
            "overall": metrics([item["category"] for item in test], [predict(model, item)[0] for item in test]),
            "baseline": metrics([item["category"] for item in test], [majority] * len(test)),
            "languages": {language: metrics([item["category"] for item in test if item["language"] == language],
                [predict(model, item)[0] for item in test if item["language"] == language]) for language in sorted({item["language"] for item in test})}}
