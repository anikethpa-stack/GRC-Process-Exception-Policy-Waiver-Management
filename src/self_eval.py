"""
self_eval.py
-------------
Evaluates the detection engine against the ground-truth labels, matching the
pattern shown in the problem statement (classification_report + critical-catch rate).

Run:
    python self_eval.py
"""

import csv
import os
from datetime import datetime
from sklearn.metrics import classification_report, precision_score, recall_score

from detection_engine import assess_exception

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TODAY = datetime(2026, 4, 15)  # must match generate_data.py's TODAY


def load_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


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
    print(classification_report(y_true, y_pred, target_names=["Compliant", "At-Risk Exception"]))

    print(f"Overall Precision: {precision_score(y_true, y_pred):.2%}")
    print(f"Overall Recall:    {recall_score(y_true, y_pred):.2%}")
    print()

    # Critical-severity catch rate (most important number for auditors)
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
