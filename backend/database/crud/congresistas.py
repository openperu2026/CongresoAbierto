from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from backend.database.models import Congresista
from backend.database.raw_models import RawCongresista

########################################
# Raw Congresista CRUD Operations
########################################

def get_last_congresistas_by_period(
    session: Session,
    leg_period: str,
) -> list[RawCongresista]:

    subq = (
        session.query(
            RawCongresista.url,
            func.max(RawCongresista.timestamp).label("max_ts"),
        )
        .filter(RawCongresista.leg_period == leg_period)
        .group_by(RawCongresista.url)
        .subquery()
    )

    return (
        session.query(RawCongresista)
        .join(
            subq,
            and_(
                RawCongresista.url == subq.c.url,
                RawCongresista.timestamp == subq.c.max_ts,
            ),
        )
        .filter(RawCongresista.leg_period == leg_period)
        .all()
    )

def mark_raw_cong_processed(session: Session, id: int) -> bool:
    """
    Utility funtion to update the processed attribute in the RawDB

    Args:
        - session (Session): Raw DB Session from Open Peru DB
        - id (int): unique identifier from the RawCongresista
    """
    raw_cong = session.get(RawCongresista, id)
    if raw_cong is None:
        return False

    raw_cong.processed = True
    session.commit()
    return True
