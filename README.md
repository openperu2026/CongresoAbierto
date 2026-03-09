# OpenPeru

OpenPeru is an open‑source civic technology project that transforms fragmented and unstructured legislative information from the Peruvian Congress into structured, machine‑readable data. Its goal is to lower the cost of understanding how Congress works—who proposes laws, how representatives vote, how parties and committees behave—and to make political accountability feasible for citizens, journalists, researchers, and civil society organizations.

Rather than creating new political information, OpenPeru unlocks the value of data that already exists but is currently difficult to access, search, and analyze.

---

## Why This Matters: Unlocking the Value of Legislative Data

Peru has experienced more than a decade of political instability, characterized by weak political parties, high legislative turnover, and repeated executive–legislative conflicts. In this context, democratic accountability depends critically on transparency: the ability of citizens and organizations to monitor legislative behavior and evaluate representatives based on evidence.

Although the Peruvian Congress publishes large volumes of information—bills, motions, voting records, committee reports, and debate transcripts—this information is dispersed across multiple portals and frequently released as PDFs or inconsistently structured web pages. These formats impose high search, interpretation, and processing costs. As a result, most legislative data has high *intrinsic* value but very low *realized* value: few actors can actually use it.

OpenPeru addresses this gap by reducing the friction between documents and data. By converting congressional documents into standardized datasets and exposing them through a unified data model, the project increases the *post value* of political information. Tasks that were previously infeasible—systematic vote analysis, party‑level accountability, longitudinal tracking of legislators—become accessible and scalable.

In short, OpenPeru is about transforming formal transparency into effective accountability.

---

## What OpenPeru Provides

At its current stage, OpenPeru focuses on the legislative core of Congress and integrates data across multiple dimensions:

- **Bills and motions**: proposals, authorship, legislative status, and procedural steps
- **Voting records and attendance**: individual‑level and aggregate vote outcomes
- **Congress members (congresistas)**: identities, party affiliations, and memberships over time
- **Political organizations**: parties, parliamentary groups, and committees
- **Legislative processes**: structured representations of how initiatives evolve

All information is stored in relational databases designed for analysis, reuse, and future API access.

---

## Technical Overview

OpenPeru follows a layered data‑engineering architecture that separates data acquisition, storage, processing, and validation. This design keeps raw information reproducible while enabling clean analytical outputs.

### 1. Data Acquisition (Scrapers)

Legislative data is collected directly from official Congress websites using custom scrapers. These handle:

- HTML pages with inconsistent structure
- PDF documents containing votes, attendance, and official records
- Pagination, historical archives, and idiosyncratic naming conventions

Scrapers are designed to be idempotent and resilient to partial failures, producing *raw* records without interpretation.

### 2. Raw Data Layer

All scraped content is stored in a **raw database** that closely mirrors the source documents. This layer:

- Preserves original values and timestamps
- Allows re‑processing when parsing logic improves
- Serves as a reproducible audit trail

Raw models live in `backend/database/raw_models.py` and are tested independently.

### 3. Processing and Standardization

The processing layer transforms raw records into clean, structured entities:

- Normalizes names, dates, and identifiers
- Maps legislative states into standardized enums
- Resolves relationships between legislators, parties, committees, and votes

This step converts documents into data with clear semantics. Validation schemas ensure internal consistency.

### 4. Processed Data Layer

Cleaned outputs are stored in a **processed database**, optimized for querying and analysis. This layer is what downstream users, dashboards, or APIs would consume.

### 5. Testing and Reliability

The project includes extensive automated tests covering:

- Scrapers (HTML/PDF parsing logic)
- Raw and processed database models
- Processing and transformation functions

This ensures changes in Congress websites or data formats are detected early.

---

## Tools and Technologies

- **Python** as the core language
- **SQLAlchemy** for database modeling and persistence
- **SQLite** for raw and processed storage (with a design compatible with future scaling)
- **Pydantic‑style schemas** for validation and consistency checks
- **Selenium and HTTP‑based scraping utilities** for dynamic and static sources
- **Pytest** for automated testing
- **Structured logging** for scraper and pipeline diagnostics

The architecture is intentionally modular to support future extensions such as APIs, dashboards, and machine‑learning pipelines.

---

## Repository Structure (High Level)

- `backend/scrapers/` – Data collection from Congress sources
- `backend/database/` – Raw and processed database models, sessions, and orchestration
- `backend/process/` – Data cleaning, normalization, and schema logic
- `tests/` – Unit and integration tests
- `data/` – Local raw and processed databases (development)

Each major submodule includes its own README with more detailed documentation.

---

## Developer Documentation

Detailed instructions on how to set up, run, and test the OpenPeru pipeline are available in the backend documentation.

Please refer to:

- `backend/README.md` – How to run the pipeline locally, CLI options, database initialization, and testing

This top-level README intentionally focuses on the project’s purpose, data model, and overall architecture.

---

## Project Status and Roadmap

OpenPeru is under active development. Current priorities include:

- Expanding coverage of voting and attendance records
- Improving historical consistency across legislative periods
- Exposing a public data API
- Building analytical summaries and visualizations

Contributions and feedback are welcome.

---

## License

This project is released under an open-source license. See the `LICENSE` file for details.

---

## Acknowledgements

OpenPeru builds on ideas from the civic‑tech and open‑data community and is inspired by projects such as OpenStates and other legislative transparency platforms.

