from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class RawBill(Base):
    """
    Represents a raw scraped bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        timestamp (datetime): timestamp of the scraping task
        general (str): Main bill info
        committees (str) Information about committees
        congresistas (str) Information about authors and proponents
        steps (str) Information about bill steps
    """

    __tablename__ = "raw_bills"
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, primary_key=True)
    general = Column(String, nullable=True)
    committees = Column(String, nullable=True)
    congresistas = Column(String, nullable=True)
    steps = Column(String, nullable=True)


class RawBillDocuments(Base):
    """
    Raw documents url and text content extracted by scrape_project_bills.py

    Attributes:
        id (str): Unique identifier for raw document.
        timestamp (datetime): timestamp of the scraping task
        bill_id (str): Unique identifier for the membership relationship.
        step_date (datetime): date of the event related to the document
        seguimiento_id (str): Event to which the document is related to.
        archivo_id (str): id related to the document
        url (str): complete document's url.
        text (str): extracted text from the pdf
    """

    __tablename__ = "raw_bill_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    bill_id = Column(String, nullable=False)
    step_date = Column(DateTime, nullable=False)
    seguimiento_id = Column(String, nullable=False)
    archivo_id = Column(String, nullable=False)
    url = Column(String, nullable=False)
    text = Column(String, nullable=False)


class RawCommittee(Base):
    """
    Represents a raw scraped committee in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for raw committee.
        timestamp (datetime): timestamp of the scraping task
        legislative_year (int): Legislative year
        committee_type (str): Type of committee in the parliament
        raw_html (str): Html text
    """

    __tablename__ = "raw_committees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    legislative_year = Column(Integer, nullable=False)
    committee_type = Column(String, nullable=False)
    raw_html = Column(String, nullable=False)


class RawCongresista(Base):
    """
    Represents a raw scraped information of congresistas

    Attributes:
        id (str): Unique identifier for raw congresista.
        timestamp: Time stamp of the scrape process
        leg_period (str): Legislative period related to the congresista
        url (str): Congresista's website url
        profile_content (str): Html text from the website's profile tab
        memberships_content (str): API response to memberships of the congresista in json format

    """

    __tablename__ = "raw_congresistas"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    leg_period = Column(String, nullable=False)
    url = Column(String, nullable=False)
    profile_content = Column(String, nullable=False)
    memberships_content = Column(String, nullable=True)

class RawMotion(Base):
    """
    Represents a raw scraped motion in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the motion.
        timestamp (datetime): timestamp of the scraping task
        general (str): Main motion info
        congresistas (str) Information about authors and proponents
        steps (str) Information about motion steps
    """

    __tablename__ = "raw_motions"
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, primary_key=True)
    general = Column(String, nullable=True)
    congresistas = Column(String, nullable=True)
    steps = Column(String, nullable=True)