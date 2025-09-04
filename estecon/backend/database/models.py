from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base
Base = declarative_base()

class Vote(Base):
    '''
    Represents a vote in a parliament session.
    
    Attributes:
        vote_event_id (str): Unique identifier for the vote event.
        voter_id (str): Unique identifier for the voter.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada_id (str): The political group of the voter.
    '''
    __tablename__ = 'votes'

    id = Column(Integer, primary_key=True, autoincrement=True)

class VoteEvent(Base):
    '''
    Represents a vote event in a parliament session.

    Attributes:
        org_id (int): The org_id or parliament where the vote took place.
        leg_period (str): The legislative period during which the vote occurred.
        bill_id (str): Unique identifier for the bill associated with the vote.
        date (str): The date of the vote event.
    '''
    __tablename__ = 'vote_events'

    id = Column(Integer, primary_key=True, autoincrement=True)

class VoteCounts(Base):
    '''
    Represents the counts of votes in a vote event.

    Attributes:
        org_id (int): The org_id or parliament where the vote took place.
        vote_event_id (str): Unique identifier for the vote event.
        option (str): The voter's choice, e.g., 'yes', 'no', 'abstain'.
        bancada (str): The political group of the voter.
        count (int): Number of votes for the option.
    '''
    __tablename__ = 'vote_counts'

    id = Column(Integer, primary_key=True, autoincrement=True)

class Attendance(Base):
    '''
    Represents attendance of a congressperson at an event.

    Attributes:
        org_id (int): The org_id or parliament where the event took place.
        event_id (str): Unique identifier for the event.
        attendee_id (str): Unique identifier for the congressperson.
        status (str): Attendance status, e.g., 'present', 'absent'.
    '''
    __tablename__ = 'attendance'

    id = Column(Integer, primary_key=True, autoincrement=True)

class Bill(Base):
    '''
    Represents a bill in the peruvian parliament.

    Attributes:
        id (str): Unique identifier for the bill.
        leg_period (str): Legislative period of the bill.
        legislature (str): Legislature where the bill was presented.
        presentation_date (datetime): Date when the bill was presented.
        title (str): Title of the bill.
        summary (str): Summary of the bill.
        observations (str): Observations on the bill.
        complete_text (str): Complete text of the bill.
        status (str): Current status of the bill.
        proponent (str): Type of proponent of the bill
        author_id (str): Unique identifier for the author of the bill.
        bancada_id (str): Unique identifier for the political group associated with the bill.
        bill_approved (bool): Boolean indicating if the bill has been published        
    '''
    __tablename__ = 'bills'

    id = Column(Integer, primary_key=True, autoincrement=True)


class BillCongresistas(Base):
    '''
    Represents a relation between a bill and parliament members based on their 
    role during the presentation of the bill.
    
    Attributes:
        bill_id (str): A unique identifier for the bill.
        person_id (str): A unique identifier for the person.
        role_type (str): The type of role that the person has in the bill (e.g. author, coauthor, adherente, etc) 
    '''
    __tablename__ = "bills_congresistas"

    id = Column(Integer, primary_key=True, autoincrement=True)

class BillStep(Base):
    '''
    Represents a bill step record with details about the actions taken on a bill.

    Attributes:
        id (int): A unique identifier for each step record.
        bill_id (str): The identifier of the bill associated with this step.
        step_type (str): The type of step record (e.g. "Vote", "Assigned to Committee", "Presented", etc.)
        step_date (datetime): The date and time when the step occured.
        step_detail (str): The details on the step
        step_url (str): The url associated to the step
    '''
    __tablename__ = "bill_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)


class BillCommittees(Base):
    '''
    Represents the relation between bills and a committee

    Attributes:
        bill_id (str): The identifier of the bill.
        committee_id (str): The identifier of the committee.
    '''
    __tablename__ = "bill_committees"

    id = Column(Integer, primary_key=True, autoincrement=True)

    
class Committee(Base):
    '''
    Represents a committee in the peruvian parliament.

    Attributes:
        leg_period (str): Legislative period of the committee.
        leg_year (str): Year period of the committee
        org_id (int): The org_id or parliament where the committee belongs.
        id (int): A unique identifier for the committee.
        name (str): Name of the committee
    '''
    __tablename__ = 'committees'

    id = Column(Integer, primary_key=True, autoincrement=True)


class Congresista(Base):
    '''
    Represents a member of the peruvian parliament

    Attributes:
        id (str): Unique identifier for the person.
        nombre (str): Name of the person.
        leg_period (str): Legislative period.
        party_id (str): Unique identifier for the party.
        votes_in_election (int): Number of votes obtain in elections
        dist_electoral (str): Electoral district.
        condicion (str): Condition of the congressperson, e.g., 'active', 'inactive'.
        website (str): Official website of the congressperson.
    '''
    __tablename__ = 'congresistas'

    id = Column(Integer, primary_key=True, autoincrement=True)


class Party(Base):
    '''
    Represent a Political Party in the peruvian government

    Attributes:
        leg_period (str): Legislative period.
        party_id (int): Unique identifier for the party
        party_name (str): Name of the party
    '''
    __tablename__ = "partidos"

    id = Column(Integer, primary_key=True, autoincrement=True)


class Bancada(Base):
    '''
    Represent a Bancada in the peruvian government

    Attributes:
        leg_year (str): Year period of the bancada
        bancada_id (int): Unique identifier for the bancada
        bancada_name (str): Name of the bancada
    '''
    __tablename__ = "bancadas"

    id = Column(Integer, primary_key=True, autoincrement=True)

class Organization(Base):
    '''
    Represents a legislative organization, such as a parliament or congress.

    Attributes:
        leg_period (str): Legislative period.
        leg_year (str): Legislative year.
        org_id (int): Unique identifier for the organization.
        org_name (str): Name of the organization.
        org_type (str): Type of organization (e.g. bancada, partido, committee, etc)

    '''
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)


class Membership(Base):
    '''
    Represents a person's role in an organization during a specific time period.
    
    Attributes:
        id (int): Unique identifier for the membership relationship.
        role (str): Role of the person in the organization (e.g. vocero, miembro, presidente, etc)
        person_id (int): Identifier for the person
        org_id (int): Identifier for the organization
        start_date (datetime): Date of the beginning of the membership
        end_date (datetime): Date of the end of the membership
    '''

    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)


class BancadaMembership(Base):
    '''
    Represents a person's membership in a bancada during a specific time period.
    
    Attributes:
        id (int): Unique identifier for the membership relationship.
        leg_year (str): Year period of the membership
        person_id (int): Identifier for the person
        bancada_id (int): Identifier for the bancada
    '''
    __tablename__ = "bancada_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)

class RawBills(Base):
    '''
    Raw data extracted by scrape_project_bills.py that contains bill's information
    from the web https://wb2server.congreso.gob.pe/spley-portal-service/expediente.
     
    Attributes:
        bill_id (int): Unique bill identifiesr.
        timestamp (datetime): Timestamp from the request.
        general (str): Raw content on 'general' key
        comisiones (str): Raw content on 'comisiones' key
        seguimientos (str): Raw content on 'seguimientos' key
        acumulados (str): Raw content on 'acumulados' key
        documentosAnexos (str): Raw content on 'documentosAnexos' key
        fases (str): Raw content on 'fases' key
        firmantes (str): Raw content on 'firmantes' key
        secciones (str): Raw content on 'secciones' key
        archivos (str): Raw content on 'archivos' key
    '''
    __tablename__ = "raw_bills"

class RawBillDocuments(Base):
    '''
    Raw documents url and text content extracted by scrape_project_bills.py
     
    Attributes:
        bill_id (str): Unique identifier for the membership relationship.
        seguimientoPleyId (str): Event to which the document is related to.
        url (str): complete document's url.
        text (str): extracted text from the pdf
    '''
    __tablename__ = "raw_bill_documents"

class RawCongresistas(Base):
    '''
    Raw data extracted by scrape_congresistas.py
    
    Attributes:
        TODO
    '''
    __tablename__ = "raw_congresistas"

class RawCommittees(Base):
    '''
    Raw data extracted by scrape_committees.py
    
    Attributes:
        TODO
    '''
    __tablename__ = "raw_committees"

class RawMemberships(Base):
    '''
    Raw data extracted by scrape_membership.py
    
    Attributes:
        TODO
    '''
    __tablename__ = "raw_memberships"


class RawBancadas(Base):
    '''
    Raw data extracted by scrape_bancadas.py
    
    Attributes:
        TODO
    '''
    __tablename__ = "raw_bancadas"
