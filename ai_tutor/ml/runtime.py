import math
import re
from collections import Counter


def tokens(record):
    # Excluye explicación, pistas, categoría objetivo, revisión e identidad del autor.
    text = record["language"] + " verdict_" + str(record["verdict"]) + " " + record["faulty_code"] + " " + " ".join(record["evidence"])
    return re.findall(r"[\w]+|[{}();]", text.lower())[:6000]


def predict(model, record):
    features = Counter(tokens(record))
    size = max(1, len(model["vocabulary"]))
    scores = {}
    for category, documents in model["classes"].items():
        counts = model["counts"][category]
        total = sum(counts.values()) + size
        score = math.log(documents / sum(model["classes"].values()))
        for token, count in features.items():
            if token in model["vocabulary"]:
                score += count * math.log((counts.get(token, 0) + 1) / total)
        scores[category] = score
    best = max(scores, key=scores.get)
    normalizer = sum(math.exp(score - scores[best]) for score in scores.values())
    confidence = 1 / normalizer
    return (best if confidence >= model["threshold"] else "unknown"), confidence


