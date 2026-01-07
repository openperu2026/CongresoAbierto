from sqlalchemy.orm import Session
from backend.database.models import Organization
from backend.database.raw_models import RawOrganization, RawCommittee

########################################
# Raw Committee CRUD Operations
########################################

def get_last_committees_by_year(
    session: Session,
    leg_year: str,
) -> list[RawCommittee]:

    return (
        session.query(RawCommittee)
        .filter(RawCommittee.legislative_year == leg_year,
                RawCommittee.last_update == True)
        .all()
    )

def mark_raw_committee_processed(session: Session, id: int) -> bool:
    """
    Utility funtion to update the processed attribute in the RawDB

    Args:
    """
    raw_committee = session.get(RawCommittee, id)
    if raw_committee is None:
        return False

    raw_committee.processed = True
    session.commit()
    return True

########################################
# Raw Organizations CRUD Operations
########################################

def get_last_organizations_by_year(
    session: Session,
    leg_year: str,
) -> list[RawOrganization]:

    return (
        session.query(RawOrganization)
        .filter(RawOrganization.legislative_year == leg_year,
                RawOrganization.last_update == True)
        .all()
    )

def mark_raw_organization_processed(session: Session, id: int) -> bool:
    """
    Utility funtion to update the processed attribute in the RawDB

    Args:
        - session (Session): Raw DB Session from Open Peru DB
        - id (int): unique identifier from the RawOrganization
    """
    raw_organization = session.get(RawOrganization, id)
    if raw_organization is None:
        return False

    raw_organization.processed = True
    session.commit()
    return True

########################################
# Organizations CRUD Operations
########################################

def get_organization_by_name_year(session: Session, org_name: str, year: str) -> Organization | None:
    
    return session.query(Organization).filter(Organization.org_name == org_name, Organization.leg_year == year).first()

def batch_create_action_history(
    db: Session, actions_data: List[ActionHistorySchema]
) -> List[ActionHistoryModel]:
    """Batch create multiple action history records."""
    logger.info(
        f"Batch creating or updating {len(actions_data)} action history records"
    )

    actions = []
    for action_data in actions_data:
        try:
            action = create_action_history(db, action_data)
            actions.append(action)
        except Exception as e:
            logger.error(
                f"Error processing action history for ticket {action_data.ticket_no}: {e}"
            )
            continue
    return actions

def bulk_load_action_histories(
    db: Session, actions_data: List[ActionHistorySchema]
) -> List[ActionHistoryModel]:
    """Bulk load action histories for fast ingestion."""
    try:
        logger.info(f"Bulk loading {len(actions_data)} action histories")

        existing_actions_map = {
            (a.ticket_no, a.action_taken_date): a
            for a in get_action_history_by_ticket(db, actions_data[0].ticket_no)
        }

        to_insert = []
        to_update = []

        for action in actions_data:
            a_dict = action.model_dump(by_alias=False)
            key = (action.ticket_no, action.action_taken_date)
            exist_action = existing_actions_map.get(key)

            if exist_action is None:
                to_insert.append(ActionHistoryModel(**a_dict))
            else:
                updated = False
                for field, value in a_dict.items():
                    if getattr(exist_action, field) != value:
                        setattr(exist_action, field, value)
                        updated = True
                if updated:
                    to_update.append(exist_action)

        if to_insert:
            db.bulk_save_objects(to_insert, return_defaults=True)
        if to_update:
            db.add_all(to_update)

        db.commit()
        logger.info(f"{len(to_insert)} new, {len(to_update)} updated action history")
        return to_insert + to_update

    except Exception as e:
        db.rollback()
        logger.error(f"Bulk load action histories failed: {e}")