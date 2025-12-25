from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from backend.database.models import Committee
from backend.database.raw_models import RawCommittee

########################################
# Raw Committee CRUD Operations
########################################

def get_last_congresistas_by_period(
    session: Session,
    leg_period: str,
) -> list[RawCommittee]:

    subq = (
        session.query(
            RawCommittee.url,
            func.max(RawCommittee.timestamp).label("max_ts"),
        )
        .filter(RawCommittee.leg_period == leg_period)
        .group_by(RawCommittee.url)
        .subquery()
    )

    return (
        session.query(RawCommittee)
        .join(
            subq,
            and_(
                RawCommittee.url == subq.c.url,
                RawCommittee.timestamp == subq.c.max_ts,
            ),
        )
        .filter(RawCommittee.leg_period == leg_period)
        .all()
    )

def mark_raw_committee_processed(session: Session, id: int) -> bool:
    """
    Utility funtion to update the processed attribute in the RawDB

    Args:
        - session (Session): Raw DB Session from Open Peru DB
        - id (int): unique identifier from the RawCommittee
    """
    raw_committee = session.get(RawCommittee, id)
    if raw_committee is None:
        return False

    raw_committee.processed = True
    session.commit()
    return True
