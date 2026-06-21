import csv
import os

from models import get_engine, get_session, init_db, Exception_

SRC_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(SRC_DIR, "..", "data")
CSV_PATH = os.path.join(DATA_DIR, "exception_registry.csv")
DB_PATH = os.path.join(DATA_DIR, "exceptions.db")


def load_csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(
            f"{CSV_PATH} not found. Run generate_data.py first, or drop the "
            f"hackathon's official sample_data/exception_registry.csv into data/."
        )

    engine = get_engine(f"sqlite:///{DB_PATH}")
    init_db(engine)
    session = get_session(engine)

    session.query(Exception_).delete()
    session.commit()

    rows = load_csv_rows(CSV_PATH)
    objects = [
        Exception_(
            exception_id=row["exception_id"],
            type=row["type"],
            requester=row["requester"],
            approver=row["approver"],
            department=row["department"],
            justification=row["justification"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            status=row["status"],
            risk_level=row["risk_level"],
            review_requested_date=row.get("review_requested_date", ""),
        )
        for row in rows
    ]

    session.bulk_save_objects(objects)
    session.commit()

    count = session.query(Exception_).count()
    print(f"Loaded {count} exception records into {DB_PATH}")

    session.close()


if __name__ == "__main__":
    main()
