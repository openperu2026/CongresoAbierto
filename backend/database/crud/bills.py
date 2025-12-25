from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database.models import (
    Bill,
    BillCommittees,
    BillCongresistas,
    BillStep,
)
from backend.database.raw_models import RawBill

########################################
# Raw Bill CRUD Operations
########################################

def get_bills_ids(session: Session) -> list[str]:
    """
    Gets all the bill's ids from the RawDB

    Args:
        - session (Session): Raw DB Session from Open Peru DB

    Returns: List of bill's ids
    """
    return [row[0] for row in session.query(RawBill.id).distinct().all()]


def get_bill_last(session: Session, bill_id: str) -> RawBill | None:
    """
    Gets the last record from an specific bill_id in the Raw DB

    Args:
        - session (Session): Raw DB Session from Open Peru DB
        - bill_id (str): unique identifier from the bill

    Returns: RawBill containing the last record for the specified bill_id in the RawDB
    """
    return (
        session.query(RawBill)
        .filter(RawBill.id == bill_id)
        .order_by(RawBill.timestamp.desc())
        .first()
    )


def mark_raw_bill_processed(session: Session, bill_id: str) -> bool:
    """
    Utility funtion to update the processed attribute in the RawDB

    Args:
        - session (Session): Raw DB Session from Open Peru DB
        - bill_id (str): unique identifier from the bill
    """
    max_ts = (
        session.query(func.max(RawBill.timestamp))
        .filter(RawBill.id == bill_id)
        .scalar()
    )
    if max_ts is None:
        return False

    updated = (
        session.query(RawBill)
        .filter(RawBill.id == bill_id, RawBill.timestamp == max_ts)
        .update({RawBill.processed: True}, synchronize_session=False)
    )
    session.commit()
    return updated == 1

########################################
# Bill CRUD Operations
########################################



########################################
# BillCommittees CRUD Operations
########################################

# TODO: Needs Committees on the Clean DB

########################################
# BillCongresistas CRUD Operations
########################################

# TODO: Needs Congresistas on the Clean DB

########################################
# BillStep CRUD Operations
########################################

