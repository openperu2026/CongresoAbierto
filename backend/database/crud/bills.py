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
    raw_bills = session.query(RawBill).distinct(RawBill.id).all()
    return [raw_bill.id for raw_bill in raw_bills]


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
    raw_bill = session.get(RawBill, bill_id)
    if raw_bill:
        raw_bill.processed = True
        session.add(raw_bill)
        session.commit()
        return True
    return False

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

