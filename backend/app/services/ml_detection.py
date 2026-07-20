"""Evidence-based numeric anomaly model selection for the generated operation."""
from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any


@dataclass
class ModelSelection:
    name: str
    f1: float
    accuracy: float
    precision: float
    recall: float
    inventory_scores: dict[str, float]
    candidates: list[dict[str, Any]] = field(default_factory=list)


def _features(wms: int, erp: int, physical: int) -> list[float]:
    highest = max(wms, erp, physical)
    lowest = min(wms, erp, physical)
    baseline = max(1, (wms + erp + physical) / 3)
    return [float(wms), float(erp), float(physical), highest - lowest, abs(wms - erp), abs(erp - physical), (highest - lowest) / baseline]


def _calibration_data(seed: int) -> tuple[list[list[float]], list[int]]:
    """Create labeled normal/error movement records from the same defect physics as the demo."""
    rng = random.Random(seed + 501)
    features: list[list[float]] = []
    labels: list[int] = []
    for _ in range(1500):
        physical = rng.randint(20, 900)
        is_fault = rng.random() < .18
        if is_fault:
            wms = physical + rng.randint(20, 80)
            erp = physical + rng.randint(-8, 22)
        else:
            wms = physical + rng.randint(-2, 2)
            erp = physical + rng.randint(-2, 2)
        features.append(_features(wms, erp, physical)); labels.append(int(is_fault))
    return features, labels


def select_best_inventory_model(records: list[dict[str, Any]], seed: int) -> ModelSelection:
    """Benchmark candidates and retain only the top F1 model for current inventory scoring.

    F1 is primary because injected faults are rare; raw accuracy would reward a model that
    incorrectly calls every record normal. Accuracy is a tie-breaker and reported for audit.
    """
    try:
        from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    except ImportError as exc:  # pragma: no cover - requirements install scikit-learn
        raise RuntimeError("scikit-learn is required for the inventory anomaly model") from exc

    X, y = _calibration_data(seed)
    # Preserve sequence order: validation must represent unseen later operational
    # periods, not a random sample that can leak repeated defect patterns.
    split = int(len(X) * .75)
    X_train, X_test, y_train, y_test = X[:split], X[split:], y[:split], y[split:]
    candidates = {
        "extra_trees": ExtraTreesClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", random_state=seed, n_jobs=-1),
        "random_forest": RandomForestClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", random_state=seed, n_jobs=-1),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=180, learning_rate=.08, max_leaf_nodes=18, random_state=seed),
    }
    evaluated = []
    for name, candidate in candidates.items():
        candidate.fit(X_train, y_train)
        predicted = candidate.predict(X_test)
        evaluated.append((
            f1_score(y_test, predicted, zero_division=0),
            accuracy_score(y_test, predicted),
            precision_score(y_test, predicted, zero_division=0),
            recall_score(y_test, predicted, zero_division=0),
            name,
            candidate,
        ))
    # Name final tie-breaker makes model selection reproducible and auditable.
    f1, accuracy, precision, recall, name, selected = max(evaluated, key=lambda item: (item[0], item[1], item[4]))
    selected.fit(X, y)
    inventory_features = [_features(row["wms"], row["erp"], row["physical"]) for row in records]
    probabilities = selected.predict_proba(inventory_features)[:, 1]
    return ModelSelection(
        name=name,
        f1=round(float(f1), 4),
        accuracy=round(float(accuracy), 4),
        precision=round(float(precision), 4),
        recall=round(float(recall), 4),
        # A stock keeping unit can have several physical positions. Key scores by
        # position so one normal bin cannot overwrite a faulty bin for the same SKU.
        inventory_scores={row["id"]: round(float(score), 4) for row, score in zip(records, probabilities)},
        candidates=[
            {"name": c_name, "f1": round(float(c_f1), 4), "accuracy": round(float(c_acc), 4), "precision": round(float(c_prec), 4), "recall": round(float(c_rec), 4), "selected": c_name == name}
            for c_f1, c_acc, c_prec, c_rec, c_name, _ in sorted(evaluated, key=lambda item: -item[0])
        ],
    )


def train_selected_classifier(name: str, seed: int):
    """Refit the already-selected model type on the calibration data.

    Used when a live incident is injected: the persisted per-position scores are
    stale for a freshly mutated record, so the store lazily rebuilds the winning
    classifier once and re-scores only the affected positions.
    """
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier

    factories = {
        "extra_trees": lambda: ExtraTreesClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", random_state=seed, n_jobs=-1),
        "random_forest": lambda: RandomForestClassifier(n_estimators=180, min_samples_leaf=2, class_weight="balanced", random_state=seed, n_jobs=-1),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(max_iter=180, learning_rate=.08, max_leaf_nodes=18, random_state=seed),
    }
    classifier = factories.get(name, factories["random_forest"])()
    X, y = _calibration_data(seed)
    classifier.fit(X, y)
    return classifier


def score_records(classifier, records: list[dict[str, Any]]) -> dict[str, float]:
    features = [_features(row["wms"], row["erp"], row["physical"]) for row in records]
    probabilities = classifier.predict_proba(features)[:, 1]
    return {row["id"]: round(float(score), 4) for row, score in zip(records, probabilities)}
