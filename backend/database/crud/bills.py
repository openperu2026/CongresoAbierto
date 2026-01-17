from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.database.raw_models import RawBill, RawBillDocument

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
# RawBillDocuments CRUD Operations
########################################

def get_documents_by_id(session: Session, bill_id: str, seguimiento_id: str) -> list[RawBillDocument]:
    """
    Gets all the RawBillDocuments from the DB by querying for bill and step

    Args:
        session (Session): Raw DB Session from Open Peru DB
        bill_id (str): unique identifier for the bill
        seguimiento_id (str): unique identifier for the step

    Returns:
        list[RawBillDocument]: list of RawBillDocuments associated with the bill and step
    """
    return session.query(RawBillDocument).filter(
        RawBillDocument.bill_id == bill_id, 
        RawBillDocument.seguimiento_id == seguimiento_id,
        RawBillDocument.last_update == True).all()

def mark_raw_bill_document_processed(session: Session, bill_id: str, seguimiento_id: str, archivo_id: str) -> bool:
    """
    Utility funtion to update the processed attribute in the RawDB

    Args:
        - session (Session): Raw DB Session from Open Peru DB
        - bill_id (str): unique identifier from the bill
        - seguimiento_id (str): unique identifier for the step
        - archivo_id (str): unique identifier for the file
    """
    max_ts = (
        session.query(func.max(RawBillDocument.timestamp))
        .filter(
            RawBillDocument.bill_id == bill_id,
            RawBillDocument.seguimiento_id == seguimiento_id,
            RawBillDocument.archivo_id == archivo_id
            )
        .scalar()
    )
    if max_ts is None:
        return False

    updated = (
        session.query(RawBillDocument)
        .filter(
            RawBillDocument.bill_id == bill_id,
            RawBillDocument.seguimiento_id == seguimiento_id,
            RawBillDocument.archivo_id == archivo_id,        
            RawBillDocument.timestamp == max_ts
            )
        .update({RawBillDocument.processed: True}, synchronize_session=False)
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

