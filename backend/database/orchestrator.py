import os
from pathlib import Path
from loguru import logger
from backend.config import settings, directories
from .session import get_db
from sqlalchemy.orm import Session

from .models import (
    Vote, Attendance, VoteEvent, VoteCounts,
    Bill, BillCommittees, BillCongresistas, BillStep, BillDocument,
    Bancada, BancadaMembership, Congresista, Organization,
    Membership, 
)