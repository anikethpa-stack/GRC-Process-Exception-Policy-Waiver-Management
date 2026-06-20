"""
models.py
----------
SQLAlchemy ORM model for the exception registry.

Uses SQLite for zero-setup local development (matches the hackathon's 48-hour
constraint — no DB server to install). The same models work unchanged against
PostgreSQL in production: just change the engine connection string in db_setup.py
from "sqlite:///exceptions.db" to "postgresql://user:pass@host/dbname".
"""

from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Exception_(Base):
    """
    Named Exception_ (trailing underscore) because 'Exception' shadows Python's
    built-in exception base class — using the bare name would work but is
    confusing/risky in a file that also handles errors.
    """
    __tablename__ = "exceptions"

    exception_id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    requester = Column(String, nullable=False)
    approver = Column(String, nullable=False)
    department = Column(String, nullable=False)
    justification = Column(String, nullable=True)
    start_date = Column(String, nullable=False)   # stored as ISO 'YYYY-MM-DD' string
    end_date = Column(String, nullable=False)
    status = Column(String, nullable=False)
    risk_level = Column(String, nullable=False)
    review_requested_date = Column(String, nullable=True)

    def to_dict(self):
        return {
            "exception_id": self.exception_id,
            "type": self.type,
            "requester": self.requester,
            "approver": self.approver,
            "department": self.department,
            "justification": self.justification,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "status": self.status,
            "risk_level": self.risk_level,
            "review_requested_date": self.review_requested_date or "",
        }


def get_engine(db_path="sqlite:///../data/exceptions.db"):
    """
    db_path examples:
      SQLite (default, no setup):  "sqlite:///../data/exceptions.db"
      PostgreSQL (production):     "postgresql://user:password@localhost:5432/grc_db"
    """
    return create_engine(db_path, echo=False)


def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()


def init_db(engine):
    """Creates the exceptions table if it doesn't already exist."""
    Base.metadata.create_all(engine)
