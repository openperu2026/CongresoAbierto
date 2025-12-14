from backend.database.session import get_raw_session
from backend.database.crud.raw_bills import get_bills_ids, get_bill_last, mark_raw_bill_processed
from backend.database.raw_models import RawBill

def extract_raw_bills(limit: int | None = None) -> list[RawBill]:
    """Pull raw bills that need processing from the raw DB."""
    with get_raw_session() as session:
        yield from iter_raw_bills_to_process(session, limit=limit)
