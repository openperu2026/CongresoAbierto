from loguru import logger
from sqlalchemy.orm import Session
from backend.database.models import Organization
from backend.database.raw_models import RawOrganization, RawCommittee
from backend.process.schema import Organization as OrgSchema

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

def bulk_load_organizations(
    db: Session, orgs_lst: list[OrgSchema]
) -> list[Organization]:
    """Bulk load organizations for fast ingestion."""
    try:
        logger.info(f"Bulk loading {len(orgs_lst)} organizations")

        existing_orgs_map = {
            (o.leg_period, o.leg_year, o.org_name, o.org_type): o
            for o in db.query(Organization).filter(
                 Organization.org_name.in_([c.org_name for c in orgs_lst])
            ).all()
        }

        to_insert = []
        to_update = []

        for org in orgs_lst:
            org_dict = org.model_dump(by_alias=False)
            key = (org.leg_period, org.leg_year, org.org_name, org.org_type)
            exist_org = existing_orgs_map.get(key)

            if exist_org is None:
                to_insert.append(Organization(**org_dict))
            else:
                updated = False
                for field, value in org_dict.items():
                    if getattr(exist_org, field) != value:
                        setattr(exist_org, field, value)
                        updated = True
                if updated:
                    to_update.append(exist_org)

        if to_insert:
            db.bulk_save_objects(to_insert, return_defaults=True)
        if to_update:
            db.add_all(to_update)

        db.commit()
        logger.info(f"{len(to_insert)} new, {len(to_update)} updated organizations")
        return to_insert + to_update

    except Exception as e:
        db.rollback()
        logger.error(f"Bulk load organizations failed: {e}")