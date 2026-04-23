# Data Model

This document describes the data entities, relationships, and storage layers in OpenCongress/Congreso Abierto. It serves as a reference for contributors working with the database models, processing pipelines, or API layer.

## Overview

Congreso Abierto maintains two separate database layers:

- **Raw layer**: stores data as close to the source as possible. Each record maps to a scraped page, downloaded PDF, or extracted text from an specific page. Raw data is append-only and never modified after ingestion, which make it possible to keep track to changes in contents.
- **Processed layer**: stores cleaned, validated, and normalized entities ready for analysis and frontend consumption. This is the layer the frontend and future enhancements will query.

Both layers use currently SQLite and are modeled with SQLAlchemy ORM. Pydantic schemas enforce validation before records enter the processed layer.

## Data Sources

All data originates from publicly available information published by the Peruvian Congress (Congreso de la República):

| Source | Format | Content | Example |
|--------|--------|---------|---------|
| Congreso Website and internal API | HTML / Internal API | Bills, Motions, Committees, Congressmembers, etc | [Web Page example](https://www3.congreso.gob.pe/pagina/congresistas)<br> [API example](https://api.congreso.gob.pe/spley-portal-service/expediente/ICnrsvoH7U-3Sjp2uTAa2A/mCfgvwjVo-nSQEGbcovENg) |
| Documents related to Bills/Motions | Scanned PDF | Attendance and votes, bills/motions content, letters | [Attendance and Votes PDF example](https://api.congreso.gob.pe/spley-portal-service//archivo/NjYzMA==/pdf) <br> [Bill content example](https://api.congreso.gob.pe/spley-portal-service/archivo/OTQ=/pdf)|
| Live sessions streamings | Video / YouTube API | Plenary and Committee Sessions | [Plenary session video example](https://www.youtube.com/watch?v=sSmMGJ3nkHg&list=PLfVIxRaemgNrCGUfo6DrFjZmtFKgIq72Z&index=2&t=6288s) |

## Core Entities

This section includes the details on each core entity for the data model. All the core entities refers to cleaned, validated, and normalized entities ready for analysis and frontend consumption.

### Attendance

Records attendance at vote events. Unique on `(event_id, attendee_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| event_id | Integer | PK, FK → vote_events.id | |
| attendee_id | Integer | FK → congresistas.id | |
| status | Enum(AttendanceStatus) | | Present, absent, licencia |

### Bancada

Represents a parliamentary group (grupo parlamentario or bancada).

| Column | Type | Key | Description |
|---|---|---|---|
| bancada_id | Integer | PK | Auto-increment |
| leg_year | Enum(LegislativeYear) | | Legislative year |
| bancada_name | String | | Group name |

### BancadaMembership

Tracks which congresista belongs to which bancada per legislative year.

| Column | Type | Key | Description |
|---|---|---|---|
| leg_year | Enum(LegislativeYear) | | Legislative year |
| person_id | Integer | FK → congresistas.id | |
| bancada_id | Integer | FK → bancadas.bancada_id | |

### Bill

Represents a bill (proyecto de ley).

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | PK | Bill identifier (e.g., "00123/2024-CR") |
| leg_period | Enum(LegPeriod) | | Legislative period |
| legislature | Enum(Legislature) | | Legislature |
| presentation_date | DateTime | | Date filed |
| title | String | | Bill title |
| summary | String | | Bill summary |
| observations | String | | Observations |
| complete_text | String | | Full text |
| status | String | | Current status |
| proponent | Enum(Proponents) | | Proponent type |
| author_id | Integer | FK → congresistas.id | Primary author |
| bancada_id | Integer | FK → bancadas.bancada_id | Associated bancada |
| bill_approved | Boolean | | Whether the bill has been approved/published |

### BillCommittees

Junction table linking bills to committees. Unique on `(bill_id, committee_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | FK → bills.id | |
| committee_id | Integer | FK → organizations.org_id | |

### BillCongresistas

Junction table linking bills to congresistas with their role. Composite PK on `(bill_id, person_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | PK, FK → bills.id | |
| person_id | Integer | PK, FK → congresistas.id | |
| role_type | Enum(RoleTypeBill) | | Role: author, coauthor, adherente, etc. |

### BillDocument

Stores extracted text from PDF documents linked to specific bill steps. Unique on `(bill_id, step_id, archivo_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | FK → bills.id | |
| step_id | Integer | FK → bill_steps.id | |
| archivo_id | Integer | PK | File identifier |
| url | String | | Document URL |
| text | String | | Extracted text |
| vote_doc | Boolean | | Whether this document is a vote record |


### BillStep

Tracks the procedural history of a bill.

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | FK → bills.id | |
| step_id | Integer | PK | |
| step_type | Enum(BillStepType) | | Step type (e.g., vote, assigned to committee, presented) |
| step_date | DateTime | | Date the step occurred |
| step_detail | String | | Details of the step |

### BillText

Stores the content body of the bill in different steps of the legislative process.

| Column | Type | Key | Description |
|---|---|---|---|
| archivo_id | Integer | PK, FK → bill_documents.archivo_id | Same file as in `bill_documents` |
| bill_id | String | PK, FK → bills.id | Bill |
| version_id | Integer | PK | |
| step_date | DateTime | | Event date (from raw document) |
| seguimiento_id | String | | Event identifier |
| text | String (nullable) | | Body slice, or null if no heading matched |



### Congresista

Represents a member of the peruvian parliament

| Column | Type | Key | Description |
|---|---|---|---|
| congresista_id | Integer | PK | Auto-increment |
| nombre | String | UQ | Full name |
| leg_period | Enum(LegPeriod) | UQ | Legislative period |
| party_name | String | | Political party name |
| current_bancada | String | | Current parliamentary group name |
| votes_in_election | Integer | | Votes received in election |
| dist_electoral | String | | Electoral district |
| condicion | String | | Status (e.g., active, inactive) |
| website | String | | Official website URL |
| photo_url | String | | Official photo URL |


### Ley

Represents an enacted law (ley).

| Column | Type | Key | Description |
|---|---|---|---|
| ley_id | String | PK | Law identifier |
| title | String | | Law title |
| bill_id | String | | Bill that originated this law |


### Membership

Tracks a person's role in an organization during a time period.

| Column | Type | Key | Description |
|---|---|---|---|
| person_id | Integer | FK → congresistas.id | |
| org_id | Integer | FK → organizations.org_id | |
| role | Enum(RoleOrganization) | | Role (e.g., vocero, miembro, presidente) |
| start_date | DateTime | | Start of membership |
| end_date | DateTime | | End of membership |

### Motion

Represents a motion (moción).

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK | Motion identifier |
| leg_period | Enum(LegPeriod) | | Legislative period |
| legislature | Enum(Legislature) | | Legislature |
| presentation_date | DateTime | | Date filed |
| motion_type | Enum(MotionType) | | Type of motion |
| summary | String | | Summary |
| observations | String | | Observations |
| complete_text | String | | Full text |
| status | String | | Current status |
| author_id | Integer | FK → congresistas.id | Primary author |
| motion_approved | Boolean | | Whether the motion has been approved |

### MotionCongresistas

Junction table linking motions to congresistas. Composite PK on `(motion_id, person_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK, FK → motions.motion_id | |
| person_id | Integer | PK, FK → congresistas.congresista_id | |
| role_type | Enum(RoleTypeBill) | | Role: author, coauthor, adherente, etc. |


### MotionDocument

Stores extracted text from PDF documents linked to specific motion steps. Unique on `(motion_id, step_id, archivo_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK, FK → motions.id | |
| step_id | Integer | PK, FK → motion_steps.step_id | |
| archivo_id | Integer | PK | File identifier |
| url | String | | Document URL |
| text | String | | Extracted text |
| vote_doc | Boolean | | Whether this document is a vote record |


### MotionStep

Tracks the procedural history of a motion.

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK, FK → motions.id | |
| step_id | Integer | PK | |
| step_type | Enum(MotionStepType) | | Step type |
| step_date | DateTime | | Date the step occurred |
| step_detail | String | | Details of the step |

### Organization

Represents legislative organizations: committees, Junta de Portavoces, Consejo Directivo, Mesa Directiva, Comisión Permanente. Uniqueness on `(leg_period, leg_year, org_name, org_type)`.

| Column | Type | Key | Description |
|---|---|---|---|
| org_id | Integer | PK | Auto-increment |
| leg_period | Enum(LegPeriod) | UQ | Legislative period |
| leg_year | Enum(LegislativeYear) | UQ | Legislative year |
| org_name | String | UQ | Organization name |
| org_type | Enum(TypeOrganization) | UQ | Organization type |
| comm_type | Enum(TypeCommittee) | | Committee subtype, if applicable |
| org_link | String | | Website URL |


### VoteEvent

Represents a vote event in a plenary session. Unique on `(leg_period, bill_or_motion, bill_motion_id, date)`.

| Column | Type | Key | Description |
|---|---|---|---|
| vote_event_id | Integer | PK | Auto-increment |
| leg_period | Enum(LegPeriod) | UQ | Legislative period |
| bill_or_motion | String | UQ | Whether this vote is on a bill or motion |
| bill_motion_id | String | UQ | Identifier for the bill or motion voted on |
| date | DateTime | UQ | Date of the vote |
| result | Enum(VoteResult) | | Outcome: aprobado, rechazado, etc. |
| majority_type | Enum(MajorityType) | | Type of majority required |

### Vote

Records how each congresista voted. Unique on `(vote_event_id, voter_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| vote_event_id | String | PK, FK → vote_events.vote_event_id | |
| voter_id | Integer | FK → congresistas.id | |
| option | Enum(VoteOption) | | Vote cast: yes, no, abstain |
| bancada_id | Integer | FK → bancadas.bancada_id | Voter's bancada at time of vote |

### VoteCounts

Pre-aggregated vote counts by bancada. Composite PK on `(vote_event_id, option, bancada_id)`.

| Column | Type | Key | Description |
|---|---|---|---|
| vote_event_id | String | PK, FK → vote_events.id | |
| option | Enum(VoteOption) | PK | Vote option |
| bancada_id | Integer | PK, FK → bancadas.bancada_id | |
| count | Integer | | Number of votes |

## Raw Database - Raw Layer

This section includes the details on each raw entity for the raw data model. All the raw entities refers to the raw data as were fetched from the original source.

### Common Metadata Columns

Every table in the Raw Layer includes:

| Column | Type | Description |
|---|---|---|
| timestamp | DateTime | When the scraping task ran for the record |
| last_update | Boolean | Whether this row is the most recent scrape for its entity |
| changed | Boolean | Whether this scrape differs from the previous one |
| processed | Boolean | Whether this row has been processed into the processed layer |

### ScraperRun 
Stores the metadata on the scrapers jobs for future analysis and future pipeline automations.

These records are stored on the table `scraper_runs` with the following columns:

| Column | Type | Key | Description |
|--------|------|-----|-------------|
| run_id | int | PK | Unique identifier of the scraper run (auto-increment) |
| scraper_name | String | | Name of the scraper file that ran |
| start_time | DateTime | | Time when the scraper started running |
| end_time | DateTime | | Time when the scraper stop running |
| summary | String | | Summary statistics of the run (e.g. {'scraped': 100, 'skipped': 10, 'errors': 10}) |


### RawBancada 
Stores scraped results from the Congress website endpoint for the list of bancadas (political groups).

- Original source: The bancadas' list [web page](https://www3.congreso.gob.pe/pagina/grupos-parlamentarios).

These records are stored on the table `raw_bancadas` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| legislative_period | String | | Legislative period |
| raw_html | String | | Full HTML content |

### RawBill 

Stores scraped results from the Internal API for Bills (Proyectos de Ley) from the Congress website. 

- Original source: A web page with this structure: https://wb2server.congreso.gob.pe/spley-portal/#/expediente/2021/14326
- Internal API: A JSON endpoint visible in the browser network activity. [See example](https://api.congreso.gob.pe/spley-portal-service/expediente/ICnrsvoH7U-3Sjp2uTAa2A/eZnTrOVGU68ZlxU_zj9XrA). 

These records are stored on the table `raw_bills` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Bill identifier (e.g., "2021_1234") |
| general | String | | Main bill info (HTML/text) |
| committees | String | | Committee assignment info |
| congresistas | String | | Author and proponent info |
| steps | String | | Legislative step info |

### RawBillDocument 

Stores metadata from PDF documents linked to bills. These documents were extracted from the `RawBill.steps` column.

- Original source: A PDF document like this: https://api.congreso.gob.pe/spley-portal-service//archivo/NjYzMA==/pdf

These records are stored on the table `raw_bill_documents` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | PK | Reference to the bill |
| step_id | Integer | PK | Event identifier |
| archivo_id | Integer | PK | Document file identifier |
| step_date | DateTime |  | Date of the related event |
| url | String | | Document URL |
| s3_key | String | | Key that maps the location of the document on the AWS S3 Bucket |
| local_path | String | | Local path where the document is located. |

### RawBillPage

Stores metadata from each page of the documents linked to bills. These pages were extracted from the `RawBillDocument.url`, `RawBillDocument.s3_key` or `RawBillDocument.local_path`.

These records are stored on the table `raw_bill_pages` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| bill_id | String | PK | Reference to the bill |
| step_id | Integer | PK | Event identifier |
| archivo_id | Integer | PK | Document file identifier |
| page_num | Integer | PK | Page of the document |
| text | String |  | Text content of the page |
| ocr_model | String |  | Model used to extract this page |

### RawCommittee 

Stores scraped results from the Congress website endpoint for the list of committees.

- Original source: The committees' list [web page](https://www3.congreso.gob.pe/pagina/comisiones-ordinarias).

These records are stored on the table `raw_committees` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| legislative_year | Integer | | Legislative year |
| committee_type | String | | Type of committee |
| raw_html | String | | Full HTML content |

### RawCongresista 

Stores scraped results from the Congress website endpoint for the list of congressmembers. 

- Original source: The congressmembers' list [web page](https://www3.congreso.gob.pe/pagina/congresistas) and each congressmember's [membership page](https://www3.congreso.gob.pe/congresistas2021/GrimanezaAcuna/sobrecongresista/cargos/)
- Internal API: A JSON endpoint visible in the browser network activity. [See example](for each congressmember https://wb2server.congreso.gob.pe/vll/cargos/api/2021/16751831). 

These records are stored on the table `raw_congresistas` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| leg_period | String | | Legislative period |
| website | String | | Congressperson's website URL |
| profile_content | String | | HTML from the profile tab |
| memberships_content | String | | API response for memberships (JSON) |

### RawLey 
Stores scraped results from the Congress website endpoint for the historic Laws that have being approved.

- Original source: Internal API from the Congress website with the following structure https://api.congreso.gob.pe/adlp-visor-service/expediente/ley?numley=31555

These records are stored on the table `raw_leyes` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| data | String | | Raw XML data for the law |

### RawMotion 
Stores scraped results from the Internal API for Motions (Mociones) from the Congress website. 

- Original source: A web page with this structure: https://wb2server.congreso.gob.pe/smociones-portal/#/expediente/2021/21804
- Internal API: A JSON endpoint visible in the browser network activity. [See example](https://api.congreso.gob.pe/smociones-portal-service/mocion/2021/21804). 

These records are stored on the table `raw_motions` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | String | PK | Motion identifier |
| general | String | | Main motion info |
| congresistas | String | | Author and proponent info |
| steps | String | | Motion steps info |

### RawMotionDocument 

Stores metadata from PDF documents linked to motions. These documents were extracted from the `RawMotion.steps` column.
These records are stored on the table `raw_motion_documents` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK | Reference to the motion |
| step_id | Integer | PK | Event identifier |
| archivo_id | Integer | PK | Document file identifier |
| step_date | DateTime |  | Date of the related event |
| url | String | | Document URL |
| s3_key | String | | Key that maps the location of the document on the AWS S3 Bucket |
| local_path | String | | Local path where the document is located. |

### RawMotionPage

Stores metadata from each page of the documents linked to motions. These pages were extracted from the `RawMotionDocument.url`, `RawMotionDocument.s3_key` or `RawMotionDocument.local_path`.

These records are stored on the table `raw_motion_pages` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| motion_id | String | PK | Reference to the motion |
| step_id | Integer | PK | Event identifier |
| archivo_id | Integer | PK | Document file identifier |
| page_num | Integer | PK | Page of the document |
| text | String |  | Text content of the page |
| ocr_model | String |  | Model used to extract this page |

### RawOrganization 
Stores scraped results from the Congress website endpoint for the organizational bodies such as Junta de Portavoces, Consejo Directivo, Mesa Directiva, and Comisión Permanente.

- Original source: Web pages for the [Junta de Portavoces](https://www3.congreso.gob.pe/pagina/junta-de-portavoces), [Consejo Directivo](https://www3.congreso.gob.pe/pagina/consejodirectivo), [Mesa Directiva](https://www3.congreso.gob.pe/pagina/mesa-directiva) and [Comisión Permanente](https://www3.congreso.gob.pe/pagina/comision-permanente).

These records are stored on the table `raw_organizations` with the following columns:

| Column | Type | Key | Description |
|---|---|---|---|
| id | Integer | PK | Auto-increment |
| legislative_year | Integer | | Legislative year |
| type_org | String | | Organization type |
| org_link | String | | Organization website URL |
| raw_html | String | | Full HTML content |
