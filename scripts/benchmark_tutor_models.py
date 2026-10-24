"""Compara candidatos reales con la misma muestra; no sustituye la evaluación pedagógica."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("sample", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text())
    sample = [json.loads(line) for line in args.sample.read_text().splitlines() if line]
    if not sample or any(item["review"]["status"] != "approved" for item in sample):
        parser.error("La muestra debe contener únicamente ejemplos aprobados.")
    reports = []
    for candidate in candidates:
        if not {"url", "model_id", "revision", "license", "quantization"} <= set(candidate):
            parser.error("Cada candidato requiere URL, modelo, revisión, licencia y cuantización.")
        latencies, responses = [], []
        for item in sample:
            payload = {"messages": [{"role": "system", "content": "Orienta sin dar una solución completa. Devuelve JSON con content y uncertainty."},
                {"role": "user", "content": json.dumps({key: item[key] for key in ("problem", "language", "faulty_code", "verdict", "concept")}, ensure_ascii=True)}],
                "max_tokens": 400, "temperature": 0, "seed": 2026}
            request = urllib.request.Request(candidate["url"] + "/v1/chat/completions", json.dumps(payload).encode(), {"Content-Type": "application/json"})
            started = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=15) as result:
                    raw = result.read(16001)
                if len(raw) > 16000:
                    raise ValueError("size")
                response = json.loads(raw)["choices"][0]["message"]["content"]
                status = "completed"
            except Exception:
                response, status = "", "failed"
            elapsed = round((time.monotonic() - started) * 1000)
            latencies.append(elapsed)
            responses.append({"example_id": item["example_id"], "content": response, "status": status, "latency_ms": elapsed,
                              "human_review": "pending"})
        values = sorted(latencies)
        reports.append({"candidate": {key: value for key, value in candidate.items() if key != "url"}, "responses": responses,
            "latency_p50_ms": statistics.median(values), "latency_p95_ms": values[max(0, (len(values) * 95 + 99) // 100 - 1)],
            "memory": "not-measured", "errors": sum(item["status"] != "completed" for item in responses)})
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump({"sample_sha256": hashlib.sha256(args.sample.read_bytes()).hexdigest(), "hardware": platform.platform(),
                   "seed": 2026, "rubric_version": "1.0", "reports": reports, "selection": "pending-human-and-memory-review"}, stream, indent=2, ensure_ascii=True)


if __name__ == "__main__":
    main()
