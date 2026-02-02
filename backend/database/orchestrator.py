from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend import find_leg_period
from backend.config import settings
from backend.database import models as db_models
from backend.database.crud import (
    pipeline_bills as crud_bills,
    pipeline_core as crud_core,
    pipeline_motions as crud_motions,
)
from backend.database.raw_models import (
    RawBase,
    RawBancada,
    RawBill,
    RawCommittee,
    RawCongresista,
    RawMotion,
    RawOrganization,
)
from backend.process.bancadas import process_bancada
from backend.process.bills import (
    get_committees,
    process_bill,
    process_bill_document,
    process_bill_steps,
)
from backend.process.congresistas import process_memberships, process_profile_content
from backend.process.motions import (
    process_motion,
    process_motion_document,
    process_motion_steps,
)
from backend.process.organizations import (
    process_committee,
    process_org,
    process_org_membership,
)
from backend.scrapers.bancadas import RawBancadaScraper
from backend.scrapers.bills import RawBillScraper
from backend.scrapers.bills_documents import RawBillDocumentScraper
from backend.scrapers.committees import RawCommitteeScraper
from backend.scrapers.congresistas import RawCongresistasScraper
from backend.scrapers.motions import RawMotionScraper
from backend.scrapers.motions_documents import RawMotionDocumentScraper
from backend.scrapers.organizations import RawOrganizationScraper


@dataclass
class StageStats:
    processed: int = 0
    skipped: int = 0
    errors: int = 0


class OpenPeruOrchestrator:
    """
    End-to-end ETL orchestrator:
      1) scrape raw tables
      2) process raw rows into Pydantic DTOs
      3) load SQLAlchemy models into the clean DB
    """

    def __init__(self, raw_db_url: str = settings.RAW_DB_URL, db_url: str = settings.DB_URL):
        self.raw_engine = create_engine(raw_db_url, pool_pre_ping=True)
        self.db_engine = create_engine(db_url, pool_pre_ping=True)
        self.RawSession = sessionmaker(bind=self.raw_engine, autocommit=False, autoflush=False)
        self.DBSession = sessionmaker(bind=self.db_engine, autocommit=False, autoflush=False)

        # Ensure schemas exist before the pipeline runs.
        RawBase.metadata.create_all(self.raw_engine)
        db_models.Base.metadata.create_all(self.db_engine)

    # -----------------------------
    # Public API
    # -----------------------------
    def _recent_raw_exists(self, raw_model, days: int = 7) -> bool:
        cutoff = datetime.now() - timedelta(days=days)
        with self.RawSession() as raw_db:
            last_ts = raw_db.query(func.max(raw_model.timestamp)).scalar()
            return bool(last_ts and last_ts >= cutoff)

    def run_scrapers(
        self,
        *,
        scrape_bills: bool = True,
        scrape_motions: bool = True,
        scrape_others: bool = True,
        only_current: bool = True,
        weekly_days: int = 7,
        others_days: int = 7,
        bill_year: int | None = None,
        bill_start: int | None = None,
        bill_end: int | None = None,
        motion_year: int | None = None,
        motion_start: int | None = None,
        motion_end: int | None = None,
        scrape_documents: bool = False,
    ) -> None:
        """
        Run raw scrapers. Bills/motions scraping requires explicit ranges.
        """
        if scrape_others:
            logger.info("Running reference scrapers (congresistas, bancadas, committees, organizations)")

            if self._recent_raw_exists(RawCongresista, days=others_days):
                logger.info(
                    f"Skipping congresistas scrape: latest raw scrape is within {others_days} days"
                )
            else:
                cong = RawCongresistasScraper()
                cong.get_dict_periodos()
                cong.extract_and_load_all(only_current=only_current)

            if self._recent_raw_exists(RawBancada, days=others_days):
                logger.info(
                    f"Skipping bancadas scrape: latest raw scrape is within {others_days} days"
                )
            else:
                banc = RawBancadaScraper()
                banc.get_raw_bancadas(only_current=only_current)
                banc.add_bancadas_to_db()

            if self._recent_raw_exists(RawCommittee, days=others_days):
                logger.info(
                    f"Skipping committees scrape: latest raw scrape is within {others_days} days"
                )
            else:
                comm = RawCommitteeScraper()
                comm.get_raw_committees(only_current=only_current)
                comm.add_committees_to_db()

            if self._recent_raw_exists(RawOrganization, days=others_days):
                logger.info(
                    f"Skipping organizations scrape: latest raw scrape is within {others_days} days"
                )
            else:
                org = RawOrganizationScraper()
                org.get_raw_organizations(only_current=only_current)
                org.add_organizations_to_db()

        if scrape_bills:
            if all(v is not None for v in [bill_year, bill_start, bill_end]):
                self._scrape_bill_range(int(bill_year), int(bill_start), int(bill_end))
            else:
                RawBillScraper().scrape_pending_weekly(max_age_days=weekly_days, flush_every=100)

        if scrape_motions:
            if all(v is not None for v in [motion_year, motion_start, motion_end]):
                self._scrape_motion_range(int(motion_year), int(motion_start), int(motion_end))
            else:
                RawMotionScraper().scrape_pending_weekly(max_age_days=weekly_days, flush_every=100)

        if scrape_documents and (scrape_bills or scrape_motions):
            self._scrape_pending_documents()

    def run_processing(
        self,
        *,
        process_bills: bool = True,
        process_motions: bool = True,
        process_others: bool = True,
        include_documents: bool = True,
        bills_limit: int | None = None,
        motions_limit: int | None = None,
    ) -> dict[str, StageStats]:
        """
        Process raw -> clean tables.
        """
        logger.info("Starting processing pipeline")
        summary: dict[str, StageStats] = {}

        if process_others:
            summary["congresistas"] = self._process_congresistas()
            summary["organizations"] = self._process_organizations()
            summary["bancadas"] = self._process_bancadas()
        if process_bills:
            summary["bills"] = self._process_bills(
                include_documents=include_documents,
                limit=bills_limit,
            )
        if process_motions:
            summary["motions"] = self._process_motions(
                include_documents=include_documents,
                limit=motions_limit,
            )

        return summary

    # -----------------------------
    # Scraping internals
    # -----------------------------
    def _scrape_bill_range(self, year: int, start: int, end: int, flush_every: int = 100) -> None:
        logger.info(f"Scraping bills in range {year}_{start}..{year}_{end}")
        scraper = RawBillScraper()
        for bill_number in range(start, end + 1):
            scraper.scrape_bill(str(year), str(bill_number))
            if len(scraper.raw_bills) >= flush_every:
                scraper.load_raw_bills()
        if scraper.raw_bills:
            scraper.load_raw_bills()

    def _scrape_motion_range(self, year: int, start: int, end: int, flush_every: int = 100) -> None:
        logger.info(f"Scraping motions in range {year}_{start}..{year}_{end}")
        scraper = RawMotionScraper()
        for motion_number in range(start, end + 1):
            scraper.scrape_motion(str(year), str(motion_number))
            if len(scraper.raw_motions) >= flush_every:
                scraper.load_raw_motions()
        if scraper.raw_motions:
            scraper.load_raw_motions()

    def _scrape_pending_documents(self) -> None:
        logger.info("Scraping pending bill and motion documents")

        bill_docs = RawBillDocumentScraper()
        for bill_id in bill_docs.get_bills_pending_documents():
            bill_docs.get_bill_documents(bill_id=bill_id, update=False, prioritize=True)
            bill_docs.load_raw_documents()

        motion_docs = RawMotionDocumentScraper()
        for motion_id in motion_docs.get_motions_pending_documents():
            motion_docs.get_motion_documents(motion_id=motion_id, update=False, prioritize=True)
            motion_docs.load_raw_documents()

    # -----------------------------
    # Processing internals
    # -----------------------------
    def _process_congresistas(self) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            rows = (
                raw_db.query(RawCongresista)
                .filter(RawCongresista.last_update.is_(True), RawCongresista.processed.is_(False))
                .all()
            )
            for raw_cong in rows:
                try:
                    # TODO: Remove this range to process all years
                    if raw_cong.leg_period not in ["2021-2026", "2016-2021"]:
                        raw_cong.processed = True
                        stats.skipped += 1
                        continue
                    cong_schema = process_profile_content(raw_cong)
                    pre = crud_core.find_congresista(
                        db,
                        name=cong_schema.nombre,
                        leg_period=cong_schema.leg_period,
                        website=cong_schema.website,
                    )
                    cong = crud_core.upsert_congresista(db, cong_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    if raw_cong.memberships_content:
                        memberships = process_memberships(raw_cong, cong_schema)
                        for ms in memberships:
                            org = crud_core.find_organization(
                                db=db,
                                org_name=ms.org_name,
                                leg_period=ms.leg_period,
                                leg_year=ms.start_date.year,
                            )
                            if org is None:
                                stats.skipped += 1
                                continue
                            crud_core.upsert_membership(
                                db=db,
                                person_id=cong.id,
                                org_id=org.org_id,
                                role=ms.role,
                                start_date=ms.start_date,
                                end_date=ms.end_date,
                            )

                    raw_cong.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawCongresista id={raw_cong.id}: {exc}")
                    db.rollback()
                    stats.errors += 1
            db.commit()
            raw_db.commit()
        logger.info(
            f"[congresistas] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_organizations(self) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            committees = (
                raw_db.query(RawCommittee)
                .filter(RawCommittee.last_update.is_(True), RawCommittee.processed.is_(False))
                .all()
            )
            for raw_comm in committees:
                try:
                    # TODO: Remove this range to process all years
                    if raw_comm.legislative_year not in range(2016, 2027):
                        raw_comm.processed = True
                        stats.skipped += 1
                        continue
                    for org_schema in process_committee(raw_comm):
                        pre = (
                            db.query(db_models.Organization)
                            .filter(
                                db_models.Organization.leg_period == org_schema.leg_period,
                                db_models.Organization.leg_year == org_schema.leg_year,
                                db_models.Organization.org_name == org_schema.org_name,
                                db_models.Organization.org_type == org_schema.org_type,
                            )
                            .first()
                        )
                        org = crud_core.upsert_organization(db, org_schema)
                        if pre is None:
                            clean_inserted += 1
                        else:
                            clean_updated += 1
                    raw_comm.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawCommittee id={raw_comm.id}: {exc}")
                    db.rollback()
                    stats.errors += 1

            organizations = (
                raw_db.query(RawOrganization)
                .filter(RawOrganization.last_update.is_(True), RawOrganization.processed.is_(False))
                .all()
            )
            for raw_org in organizations:
                try:
                    # TODO: Remove this range to process all years
                    if raw_org.legislative_year not in range(2016, 2027):
                        raw_org.processed = True
                        stats.skipped += 1
                        continue
                    org_schema = process_org(raw_org)
                    pre = (
                        db.query(db_models.Organization)
                        .filter(
                            db_models.Organization.leg_period == org_schema.leg_period,
                            db_models.Organization.leg_year == org_schema.leg_year,
                            db_models.Organization.org_name == org_schema.org_name,
                            db_models.Organization.org_type == org_schema.org_type,
                        )
                        .first()
                    )
                    org = crud_core.upsert_organization(db, org_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1
                    for ms in process_org_membership(raw_org, org_schema):
                        cong = crud_core.find_congresista(
                            db, name=ms.nombre, leg_period=ms.leg_period
                        )
                        if cong is None:
                            stats.skipped += 1
                            continue
                        crud_core.upsert_membership(
                            db=db,
                            person_id=cong.id,
                            org_id=org.org_id,
                            role=ms.role,
                            start_date=ms.start_date,
                            end_date=ms.end_date,
                        )
                    raw_org.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawOrganization id={raw_org.id}: {exc}")
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[organizations] raw_committees={len(committees)} raw_orgs={len(organizations)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_bancadas(self) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            rows = (
                raw_db.query(RawBancada)
                .filter(RawBancada.last_update.is_(True), RawBancada.processed.is_(False))
                .all()
            )
            for raw_bancada in rows:
                try:
                    bancadas, memberships = process_bancada(raw_bancada)

                    bancadas_index: dict[str, db_models.Bancada] = {}
                    for bancada in bancadas:
                        pre = (
                            db.query(db_models.Bancada)
                            .filter(
                                db_models.Bancada.leg_year == bancada.leg_year,
                                func.lower(db_models.Bancada.bancada_name)
                                == bancada.bancada_name.lower(),
                            )
                            .first()
                        )
                        model = crud_core.upsert_bancada(
                            db, bancada.leg_year, bancada.bancada_name
                        )
                        bancadas_index[bancada.bancada_name] = model
                        if pre is None:
                            clean_inserted += 1
                        else:
                            clean_updated += 1

                    for ms in memberships:
                        leg_year_value = (
                            ms.leg_year.value if hasattr(ms.leg_year, "value") else ms.leg_year
                        )
                        cong = crud_core.find_congresista(
                            db,
                            name=ms.cong_name,
                            leg_period=find_leg_period(str(leg_year_value)),
                            website=ms.website,
                        )
                        bancada = bancadas_index.get(ms.bancada_name)
                        if cong is None or bancada is None:
                            stats.skipped += 1
                            continue
                        crud_core.upsert_bancada_membership(
                            db=db,
                            leg_year=leg_year_value,
                            person_id=cong.id,
                            bancada_id=bancada.bancada_id,
                        )

                    raw_bancada.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawBancada id={raw_bancada.id}: {exc}")
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[bancadas] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_bills(self, *, include_documents: bool, limit: int | None) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            query = (
                raw_db.query(RawBill)
                .filter(RawBill.last_update.is_(True), RawBill.processed.is_(False))
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_bill in rows:
                try:
                    bill_schema, bill_congs = process_bill(raw_bill)
                    pre = db.get(db_models.Bill, bill_schema.id)
                    bill = crud_bills.upsert_bill(db, bill_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    for cong_rel in bill_congs:
                        cong = crud_core.find_congresista(
                            db, name=cong_rel.nombre, leg_period=cong_rel.leg_period
                        )
                        if cong is None:
                            stats.skipped += 1
                            continue
                        crud_bills.upsert_bill_congresista(
                            db, bill.id, cong.id, cong_rel.role_type
                        )

                    for comm in get_committees(raw_bill) or []:
                        org = crud_core.find_organization(
                            db=db,
                            org_name=comm.committee_name,
                            leg_period=bill_schema.leg_period,
                            leg_year=bill_schema.presentation_date.year,
                        )
                        if org is None:
                            stats.skipped += 1
                            continue
                        crud_bills.upsert_bill_committee(db, bill.id, org.org_id)

                    for step_schema in process_bill_steps(raw_bill) or []:
                        crud_bills.upsert_bill_step(
                            db,
                            step_schema.id,
                            bill.id,
                            step_schema.step_date,
                            step_schema.step_detail,
                        )

                    if include_documents:
                        for raw_doc in crud_bills.find_raw_bill_documents(
                            raw_db, bill.id
                        ):
                            doc = process_bill_document(raw_doc)
                            crud_bills.upsert_bill_document(
                                db,
                                doc.bill_id,
                                doc.step_id,
                                doc.archivo_id,
                                doc.url,
                                doc.text,
                                doc.vote_doc,
                            )
                            raw_doc.processed = True

                    raw_bill.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawBill id={raw_bill.id}: {exc}")
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[bills] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats

    def _process_motions(self, *, include_documents: bool, limit: int | None) -> StageStats:
        stats = StageStats()
        clean_inserted = 0
        clean_updated = 0
        with self.RawSession() as raw_db, self.DBSession() as db:
            query = (
                raw_db.query(RawMotion)
                .filter(RawMotion.last_update.is_(True), RawMotion.processed.is_(False))
            )
            if limit is not None:
                query = query.limit(limit)
            rows = query.all()

            for raw_motion in rows:
                try:
                    motion_schema, motion_congs = process_motion(raw_motion)
                    pre = db.get(db_models.Motion, motion_schema.id)
                    motion = crud_motions.upsert_motion(db, motion_schema)
                    if pre is None:
                        clean_inserted += 1
                    else:
                        clean_updated += 1

                    for cong_rel in motion_congs:
                        cong = crud_core.find_congresista(
                            db, name=cong_rel.nombre, leg_period=cong_rel.leg_period
                        )
                        if cong is None:
                            stats.skipped += 1
                            continue
                        crud_motions.upsert_motion_congresista(
                            db, motion.id, cong.id, cong_rel.role_type
                        )

                    for step_schema in process_motion_steps(raw_motion) or []:
                        crud_motions.upsert_motion_step(
                            db,
                            step_id=step_schema.id,
                            motion_id=motion.id,
                            step_date=step_schema.step_date,
                            step_detail=step_schema.step_detail,
                        )

                    if include_documents:
                        for raw_doc in crud_motions.find_raw_motion_documents(
                            raw_db, motion.id
                        ):
                            doc = process_motion_document(raw_doc)
                            crud_motions.upsert_motion_document(
                                db,
                                motion_id=doc.motion_id,
                                step_id=doc.step_id,
                                archivo_id=doc.archivo_id,
                                url=doc.url,
                                text=doc.text,
                                vote_doc=doc.vote_doc,
                            )
                            raw_doc.processed = True

                    raw_motion.processed = True
                    stats.processed += 1
                except Exception as exc:
                    logger.exception(f"Error processing RawMotion id={raw_motion.id}: {exc}")
                    db.rollback()
                    stats.errors += 1

            db.commit()
            raw_db.commit()
        logger.info(
            f"[motions] raw_total={len(rows)} processed={stats.processed} skipped={stats.skipped} errors={stats.errors} clean_inserted={clean_inserted} clean_updated={clean_updated}"
        )
        return stats


def _print_summary(summary: dict[str, StageStats]) -> None:
    total_processed = 0
    total_skipped = 0
    total_errors = 0
    for stage, stats in summary.items():
        logger.info(
            f"{stage}: processed={stats.processed}, skipped={stats.skipped}, errors={stats.errors}"
        )
        total_processed += stats.processed
        total_skipped += stats.skipped
        total_errors += stats.errors
    logger.info(
        f"total: processed={total_processed}, skipped={total_skipped}, errors={total_errors}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenPeru ETL Orchestrator")
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Run scrapers before processing",
    )
    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="Do not run raw->clean processing",
    )
    parser.add_argument(
        "--only-current",
        action="store_true",
        help="Scrape only current period where supported",
    )
    parser.add_argument(
        "--weekly-days",
        type=int,
        default=7,
        help="Refresh stale non-approved bills/motions older than this many days",
    )
    parser.add_argument(
        "--others-days",
        type=int,
        default=7,
        help="Skip congresistas/bancadas/committees/organizations scrape when latest raw scrape is within this many days",
    )
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--only-bills",
        action="store_true",
        help="Run only bills scraping/processing",
    )
    target_group.add_argument(
        "--only-motions",
        action="store_true",
        help="Run only motions scraping/processing",
    )
    target_group.add_argument(
        "--only-others",
        action="store_true",
        help="Run only non-bill/non-motion entities (congresistas, bancadas, organizations)",
    )
    parser.add_argument("--bill-year", type=int)
    parser.add_argument("--bill-start", type=int)
    parser.add_argument("--bill-end", type=int)
    parser.add_argument("--motion-year", type=int)
    parser.add_argument("--motion-start", type=int)
    parser.add_argument("--motion-end", type=int)
    parser.add_argument(
        "--scrape-documents",
        action="store_true",
        help="Scrape pending bill/motion documents",
    )
    parser.add_argument(
        "--no-documents",
        action="store_true",
        help="Skip loading documents in processing stage",
    )
    parser.add_argument(
        "--process-bills-limit",
        type=int,
        help="Limit the number of bill raw rows processed",
    )
    parser.add_argument(
        "--process-motions-limit",
        type=int,
        help="Limit the number of motion raw rows processed",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    orchestrator = OpenPeruOrchestrator()
    run_bills = True
    run_motions = True
    run_others = True

    if args.only_bills:
        run_motions = False
        run_others = False
    elif args.only_motions:
        run_bills = False
        run_others = False
    elif args.only_others:
        run_bills = False
        run_motions = False

    if args.scrape:
        orchestrator.run_scrapers(
            scrape_bills=run_bills,
            scrape_motions=run_motions,
            scrape_others=run_others,
            only_current=args.only_current,
            weekly_days=args.weekly_days,
            others_days=args.others_days,
            bill_year=args.bill_year,
            bill_start=args.bill_start,
            bill_end=args.bill_end,
            motion_year=args.motion_year,
            motion_start=args.motion_start,
            motion_end=args.motion_end,
            scrape_documents=args.scrape_documents,
        )

    if not args.skip_processing:
        summary = orchestrator.run_processing(
            process_bills=run_bills,
            process_motions=run_motions,
            process_others=run_others,
            include_documents=not args.no_documents,
            bills_limit=args.process_bills_limit,
            motions_limit=args.process_motions_limit,
        )
        _print_summary(summary)


if __name__ == "__main__":
    main()
