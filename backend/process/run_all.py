from typing import Literal

from backend.process.bills.pipeline import run as run_bills
from backend.process.motions.pipeline import run as run_motions
from backend.process.congresistas.pipeline import run as run_congresistas
from backend.process.attendance_votes.pipeline import run as run_attendance_votes
from backend.process.organizations.pipeline import run as run_organizations

Domain = Literal[
    "bills",
    "motions",
    "congresistas",
    "attendance_votes",
    "organizations",
    "all",
]

def run(domain: Domain = "all") -> None:
    if domain in ("bills", "all"):
        run_bills()
    if domain in ("motions", "all"):
        run_motions()
    if domain in ("congresistas", "all"):
        run_congresistas()
    if domain in ("attendance_votes", "all"):
        run_attendance_votes()
    if domain in ("organizations", "all"):
        run_organizations()

if __name__ == "__main__":
    # simple CLI for manual runs: python -m backend.process.run_all bills
    import sys

    domain_arg: Domain = "all"
    if len(sys.argv) > 1:
        domain_arg = sys.argv[1]  # type: ignore[assignment]

    run(domain_arg)
