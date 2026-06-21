import csv
import os
from datetime import datetime

from detection_engine import assess_exception

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY = datetime(2026, 4, 15)


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def classification_report_pure(y_true, y_pred, target_names):
    classes = [0, 1]
    precision = {}
    recall = {}
    f1 = {}
    support = {}

    for c in classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp == c)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != c and yp == c)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == c and yp != c)
        support[c] = sum(1 for yt in y_true if yt == c)

        precision[c] = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall[c] = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1[c] = (2 * precision[c] * recall[c] / (precision[c] + recall[c])) if (precision[c] + recall[c]) > 0 else 0.0

    lines = []
    lines.append(f"{'':<25} {'precision':>10} {'recall':>10} {'f1-score':>10} {'support':>10}")
    lines.append("")

    for i, name in enumerate(target_names):
        lines.append(f"{name:<25} {precision[i]:>10.2f} {recall[i]:>10.2f} {f1[i]:>10.2f} {support[i]:>10}")

    lines.append("")

    acc = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp) / len(y_true)
    total_support = len(y_true)
    lines.append(f"{'accuracy':<25} {'':>10} {'':>10} {acc:>10.2f} {total_support:>10}")

    macro_prec = sum(precision.values()) / len(classes)
    macro_rec = sum(recall.values()) / len(classes)
    macro_f1 = sum(f1.values()) / len(classes)
    lines.append(f"{'macro avg':<25} {macro_prec:>10.2f} {macro_rec:>10.2f} {macro_f1:>10.2f} {total_support:>10}")

    weighted_prec = sum(precision[c] * support[c] for c in classes) / total_support
    weighted_rec = sum(recall[c] * support[c] for c in classes) / total_support
    weighted_f1 = sum(f1[c] * support[c] for c in classes) / total_support
    lines.append(f"{'weighted avg':<25} {weighted_prec:>10.2f} {weighted_rec:>10.2f} {weighted_f1:>10.2f} {total_support:>10}")

    return "\n".join(lines)


def precision_score_pure(y_true, y_pred):
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def recall_score_pure(y_true, y_pred):
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def main():
    registry = load_csv(os.path.join(DATA_DIR, "exception_registry.csv"))
    labels = {row["exception_id"]: row for row in load_csv(os.path.join(DATA_DIR, "exception_labels.csv"))}

    y_true = []
    y_pred = []
    severity_true = []

    for record in registry:
        eid = record["exception_id"]
        truth = labels[eid]

        assessment = assess_exception(record, TODAY)

        y_true.append(1 if truth["is_anomaly"] == "True" else 0)
        y_pred.append(1 if assessment.is_flagged else 0)
        severity_true.append(truth["severity"])

    print("=" * 60)
    print("CLASSIFICATION REPORT (Compliant vs At-Risk Exception)")
    print("=" * 60)
    print(classification_report_pure(y_true, y_pred, target_names=["Compliant", "At-Risk Exception"]))
    print()
    print(f"Overall Precision: {precision_score_pure(y_true, y_pred):.2%}")
    print(f"Overall Recall:    {recall_score_pure(y_true, y_pred):.2%}")
    print()

    critical_indices = [i for i, sev in enumerate(severity_true) if sev == "CRITICAL"]
    if critical_indices:
        caught = sum(1 for i in critical_indices if y_pred[i] == 1)
        print(f"CRITICAL exception detection rate: {caught}/{len(critical_indices)} "
              f"({caught / len(critical_indices):.1%})")

    high_indices = [i for i, sev in enumerate(severity_true) if sev == "HIGH"]
    if high_indices:
        caught_high = sum(1 for i in high_indices if y_pred[i] == 1)
        print(f"HIGH exception detection rate:     {caught_high}/{len(high_indices)} "
              f"({caught_high / len(high_indices):.1%})")

    print()
    print("Target: Precision > 75%, Recall > 70%, Critical detection ~100%")


if __name__ == "__main__":
    main()
