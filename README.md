# Exception Registry — GRC Process Exception & Policy Waiver Management

A centralized system for tracking, scoring, and auditing policy exceptions across an enterprise.

## What it does

- Centralizes every policy exception/waiver into one registry
- Detects 5 categories of risk automatically:
  | Rule | Trigger | Severity |
  |---|---|---|
  | `EXPIRED_ACTIVE_EXCEPTION` | End date passed, still marked `ACTIVE` | CRITICAL/HIGH |
  | `CRITICAL_RISK_EXCEPTION` | Risk level = Critical, currently active | HIGH |
  | `LONG_RUNNING_EXCEPTION` | Active >180 days without renewal | HIGH |
  | `HIGH_RISK_LONG_EXCEPTION` | High-risk type, active >90 days without review | MEDIUM |
  | `STALLED_REVIEW` | Renewal requested, pending >30 days | MEDIUM |
- Scores and ranks every exception so the riskiest items surface first
- Visualizes the portfolio (by type, department, severity) on a live dashboard
- Exports audit-ready reports (text summary + flagged-items CSV) in one click
- Flags risk accumulation — people holding 3+ simultaneous active exceptions

## 📸 Application Screenshots
### Dashboard GRC
<img width="1366" height="647" alt="Dashboard GRC" src="https://github.com/user-attachments/assets/7f5a0722-8688-4314-a092-fe5a560f1cd2" />

### Executive Action and Lifecycle
<img width="1298" height="537" alt="Executive Action and Lifecycle" src="https://github.com/user-attachments/assets/0d19ebdb-73de-4323-b97e-dc217cdf5b5d" />

### Department Exposure Rankings
<img width="1293" height="557" alt="Department Exposure Rankings" src="https://github.com/user-attachments/assets/f10bb92e-35ab-41f5-a7d4-c1de8111ca08" />

### Priority Remediation Queue and Audit Findings
<img width="1240" height="610" alt="Priority Remediation Queue and Audit Findings" src="https://github.com/user-attachments/assets/ca91c5f8-53fb-4672-9485-02b658934f41" />

### Enterprise Registry
<img width="1226" height="526" alt="Enterprise Registry" src="https://github.com/user-attachments/assets/a93eed1e-b130-4f94-a40d-8e2f8aec95a2" />


## Project structure

```
grc-exception-tracker/
├── data/
│   ├── exception_registry.csv
│   └── exception_labels.csv
├── src/
│   ├── generate_data.py
│   ├── models.py
│   ├── db_setup.py
│   ├── detection_engine.py
│   ├── risk_scoring.py
│   ├── self_eval.py
│   └── app.py
├── templates/
│   └── dashboard.html
├── static/
│   ├── style.css
│   └── dashboard.js
├── docs/
│   ├── architecture.md
│   └── data_dictionary.md
├── reports/
│   └── sample_audit_report.txt
├── requirements.txt
└── README.md
```

## Setup

### Prerequisites
- Python 3.10+
- pip

### Install & run

```bash
git clone https://github.com/<your-username>/grc-exception-tracker.git
cd grc-exception-tracker

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

cd src
python generate_data.py
python db_setup.py
python self_eval.py
python app.py
```

Then open **http://localhost:5000** in your browser.

If `db_setup.py` is skipped, the app falls back to reading the CSV directly.

## API routes

| Route | Returns |
|---|---|
| `GET /` | Dashboard UI |
| `GET /api/exceptions` | All exceptions with computed risk + alerts (JSON) |
| `GET /api/summary` | Portfolio summary stats (JSON) |
| `GET /api/audit-readiness` | Audit readiness percentages (JSON) |
| `GET /api/report/audit` | Downloadable plain-text audit report |
| `GET /api/report/csv` | Downloadable CSV of all flagged exceptions |

## Self-evaluation

```bash
cd src
python self_eval.py
```

Outputs precision/recall/F1 plus a critical-severity catch rate against ground-truth labels.

## Compliance framework alignment

- **NIST AC-2** — Account Management
- **NIST PL-4** — Rules of Behavior
- **GDPR Article 25** — Data Protection by Design
- **CIS Controls 1.1** — Inventory of IT assets

---

**Hackathon:** Soc-Gen Hackathon
**Team:** Definsive Drivers
