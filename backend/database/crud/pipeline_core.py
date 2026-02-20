from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import find_leg_period
from backend.database import models as db_models
from backend.process import schema


def find_congresista(
    db: Session, name: str, leg_period, website: str | None = None
) -> db_models.Congresista | None:
    if website:
        by_web = (
            db.query(db_models.Congresista)
            .filter(db_models.Congresista.website == website)
            .first()
        )
        if by_web is not None:
            return by_web
    return (
        db.query(db_models.Congresista)
        .filter(
            db_models.Congresista.nombre == name,
            db_models.Congresista.leg_period == leg_period,
        )
        .first()
    )


def find_organization(
    db: Session, org_name: str, leg_period, leg_year: int | str
) -> db_models.Organization | None:
    return (
        db.query(db_models.Organization)
        .filter(
            db_models.Organization.org_name == org_name,
            db_models.Organization.leg_period == find_leg_period(str(leg_year)),
            db_models.Organization.leg_year == str(leg_year),
        )
        .first()
    )


def upsert_congresista(
    db: Session, schema: schema.Congresista
) -> db_models.Congresista:
    existing = find_congresista(db, schema.nombre, schema.leg_period, schema.website)
    payload = schema.model_dump()

    if existing is None:
        obj = db_models.Congresista(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing


def upsert_organization(
    db: Session, schema: schema.Organization
) -> db_models.Organization:
    existing = (
        db.query(db_models.Organization)
        .filter(
            db_models.Organization.leg_period == schema.leg_period,
            db_models.Organization.leg_year == schema.leg_year,
            db_models.Organization.org_name == schema.org_name,
            db_models.Organization.org_type == schema.org_type,
        )
        .first()
    )
    payload = schema.model_dump()

    if existing is None:
        obj = db_models.Organization(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing


def upsert_membership(
    db: Session, *, person_id: int, org_id: int, role, start_date, end_date
) -> db_models.Membership:
    existing = (
        db.query(db_models.Membership)
        .filter(
            db_models.Membership.person_id == person_id,
            db_models.Membership.org_id == org_id,
            db_models.Membership.role == role,
            db_models.Membership.start_date == start_date,
            db_models.Membership.end_date == end_date,
        )
        .first()
    )
    if existing is not None:
        return existing

    obj = db_models.Membership(
        person_id=person_id,
        org_id=org_id,
        role=role,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(obj)
    db.flush()
    return obj


def upsert_bancada(db: Session, leg_year, bancada_name: str) -> db_models.Bancada:
    existing = (
        db.query(db_models.Bancada)
        .filter(
            db_models.Bancada.leg_year == leg_year,
            func.lower(db_models.Bancada.bancada_name) == bancada_name.lower(),
        )
        .first()
    )
    if existing is not None:
        return existing

    last_id = db.query(func.max(db_models.Bancada.bancada_id)).scalar() or 0
    obj = db_models.Bancada(
        leg_year=leg_year, bancada_id=last_id + 1, bancada_name=bancada_name
    )
    db.add(obj)
    db.flush()
    return obj


def upsert_bancada_membership(
    db: Session, *, leg_year, person_id: int, bancada_id: int
) -> db_models.BancadaMembership:
    existing = (
        db.query(db_models.BancadaMembership)
        .filter(
            db_models.BancadaMembership.leg_year == leg_year,
            db_models.BancadaMembership.person_id == person_id,
            db_models.BancadaMembership.bancada_id == bancada_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    last_id = db.query(func.max(db_models.BancadaMembership.id)).scalar() or 0
    obj = db_models.BancadaMembership(
        id=last_id + 1,
        leg_year=leg_year,
        person_id=person_id,
        bancada_id=bancada_id,
    )
    db.add(obj)
    db.flush()
    return obj


def upsert_ley(db: Session, schema: schema.Ley) -> db_models.Ley:

    payload = {
        "id": schema.id,
        "title": schema.title,
        "bill_id": schema.bill_id,
    }

    existing = db.get(db_models.Ley, schema.id)
    if existing is None:
        obj = db_models.Ley(**payload)
        db.add(obj)
        db.flush()
        return obj

    for key, value in payload.items():
        setattr(existing, key, value)
    db.flush()
    return existing
