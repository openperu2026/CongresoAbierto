from loguru import logger
from sqlalchemy import func, and_, select
from sqlalchemy.orm import Session

from backend.database.raw_models import RawCongresista
from backend.database.models import Congresista, Membership, Organization
from backend.process.schema import Congresista as CongresistaSchema, Membership as MembershipSchema

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

########################################
# Congresistas CRUD Operations
########################################

def get_cong_by_web_name(session: Session, name: str, leg_period: str, web: str | None = None) -> Congresista:

    cong = session.query(Congresista).filter(Congresista.website == web).first()

    if cong:
        return cong
    
    return session.query(Congresista).filter(Congresista.nombre == name, Congresista.leg_period == leg_period).first()

#TODO: ALL THIS FUNCTION
def bulk_load_congresistas(
    db: Session, congs_lst: list[CongresistaSchema]
) -> list[Congresista]:
    """Bulk load congresistas for fast ingestion."""
    try:
        logger.info(f"Bulk loading {len(congs_lst)} congresistas")

        existing_congs_map = {
            (c.website): c
            for c in db.query(Congresista).filter(
                 Congresista.website.in_([c.website for c in congs_lst])
            ).all()
        }

        to_insert = []
        to_update = []

        for cong in congs_lst:
            cong_dict = cong.model_dump(by_alias=False)
            key = (cong.website)
            exist_cong = existing_congs_map.get(key)

            if exist_cong is None:
                to_insert.append(Congresista(**cong_dict))
            else:
                updated = False
                for field, value in cong_dict.items():
                    if getattr(exist_cong, field) != value:
                        setattr(exist_cong, field, value)
                        updated = True
                if updated:
                    to_update.append(exist_cong)

        if to_insert:
            db.bulk_save_objects(to_insert, return_defaults=True)
        if to_update:
            db.add_all(to_update)

        db.commit()
        logger.info(f"{len(to_insert)} new, {len(to_update)} updated congresistas")
        return to_insert + to_update

    except Exception as e:
        db.rollback()
        logger.error(f"Bulk load congresistas failed: {e}")

########################################
# Membership CRUD Operations
########################################

def get_membership_by_name(db: Session, cong_name: str, org_name: str, leg_period: str):
    """Query membership objects by names and leg_period"""
    cong = (
        select(Congresista.id, Congresista.nombre, Congresista.leg_period)
        .where(
            Congresista.nombre == cong_name,
            Congresista.leg_period == leg_period,
        )
        .cte("cong")
    )

    org = (
        select(Organization.org_id, Organization.org_name, Organization.leg_period)
        .where(
            Organization.org_name == org_name,
            Organization.leg_period == leg_period,
        )
        .cte("org")
    )

    stmt = (
        select(Membership)
        .join(cong, cong.c.id == Membership.person_id)
        .join(org, org.c.org_id == Membership.org_id)
    )

    return db.execute(stmt).first()

def bulk_load_membership(
    db: Session, membership_lst: list[MembershipSchema]
) -> list[Membership]:
    """Bulk load membership for fast ingestion."""

    try:
        logger.info(f"Bulk loading {len(membership_lst)} memberships")

        to_insert: list[Membership] = []
        to_update: list[Membership] = []

        for ms in membership_lst:
            # Reuse your existing query logic
            existing_memberships = get_membership_by_name(
                db=db,
                cong_name=ms.nombre,
                org_name=ms.org_name,
                leg_period=ms.leg_period,
            )

            ms_dict = ms.model_dump(by_alias=False, exclude_unset=True)

            if not existing_memberships:
                # No membership found → insert
                to_insert.append(Membership(**ms_dict))
                continue

            # Usually should be 1, but handle multiple defensively
            for existing in existing_memberships:
                updated = False
                for field, value in ms_dict.items():
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        updated = True

                if updated:
                    to_update.append(existing)

        if to_insert:
            db.bulk_save_objects(to_insert, return_defaults=True)
        if to_update:
            db.add_all(to_update)

        db.commit()
        logger.info(f"{len(to_insert)} new, {len(to_update)} updated memberships")
        return to_insert + to_update

    except Exception as e:
        db.rollback()
        logger.error(f"Bulk load memberships failed: {e}")
        raise