# Extract Votes DS - Vote Extraction Module

## Overview
`extract_votes_DS.py` is a parliamentary vote extraction and reconciliation system. It processes congressional voting documents (OCR-scanned or text) to extract vote records and match them against a database of congresspeople, filling in vote information for each member.

## Workflow Overview

The module follows this pipeline:
1. **Text Normalization** - Clean OCR text and standardize formatting
2. **Type Detection** - Identify if document contains VOTACION or ASISTENCIA
3. **Block Location** - Find and extract header and vote table sections
4. **Vote Parsing** - Extract individual vote records from the table
5. **Constancia Extraction** - Extract additional votes from "DEJA CONSTANCIA" sections
6. **Data Formatting** - Prepare congressman database and filter by voting date
7. **Matching** - Match extracted votes to congresspeople using name similarity
8. **Result Compilation** - Return final reconciled vote list

---

## Core Functions

### Text Processing Functions

#### `normalize_text(text: str) -> str`
Normalizes OCR text for consistent regex parsing.

**Steps:**
- Unicode normalization (NFKC format)
- Standardize pipe spacing (`|` characters)
- Replace multiple spaces/tabs with single space
- Remove excessive blank lines
- Convert to UPPERCASE
- Remove accents using NFC normalization
- Remove special characters (+, -, =)

**Example:**
```python
normalize_text("Juan, PéREZ")  
# Returns: "JUAN, PEREZ"
```

#### `read_txt(path: str) -> str`
Simple file reader that loads text with UTF-8 encoding and ignores read errors.

---

### Document Detection (Type & Structure)

#### `get_type(text: str) -> str | None`
Detects document type by searching for keywords.

**Returns:**
- `"VOTACION"` - if "VOTACIÓN:" is found
- `"ASISTENCIA"` - if "ASISTENCIA:" is found  
- `None` - if neither is found

**Example:**
```python
get_type("VOTACION: Ley 31751")  # Returns: "VOTACION"
```

#### `locate_blocks(text_clean: str, doc_type: str) -> Dict[str, object]`
Locates header and table sections of the document.

**For VOTACION documents:**
- Finds anchor line starting with "VOTACION:"
- Finds table start with bancada marker (e.g., `| AP |`)
- Splits text into `header_block` (metadata) and `table_block` (votes)

**Returns:**
```python
{
    "header_block": "VOTACION: ... ASUNTO: ...",
    "table_block": "| AP | JUAN, DIEGO | SI ...",
    "warnings": []  # Any parsing issues
}
```

---

### Metadata Extraction

#### `get_fecha(text: str) -> tuple | None`
Extracts voting date from header text.

**Looks for:** patterns like `Fecha: 15/06/2023` or `Eccha: 15/06/2023`

**Returns:** `(year, month, day)` tuple or `None`

**Example:**
```python
get_fecha("Fecha: 15/06/2023")  # Returns: (2023, 6, 15)
```

#### `get_title(text: str) -> str`
Extracts the legislative bill or topic from "ASUNTO:" field.

**Example:**
```python
get_title("ASUNTO: LEY 31751 - REFORMA")  # Returns: "LEY 31751 - REFORMA"
```

---

### Vote Parsing

#### `parse_vote_table(table_text: str) -> Dict[str, Any]`
Extracts vote records from table block using regex patterns.

**Expected table format:**
```
| BANCADA | LASTNAME, FIRSTNAME | VOTE_TOKEN |
```

**Valid vote tokens:**
- `SI` - Yes
- `NO` - No
- `AUS` / `AIS` / `US` - Absent
- `ABST` - Abstention
- `PRE` - (Present)
- `SINRRES` / `LP` / `LE` / etc. - Other
- `*` - Star votes

**Returns:**
```python
{
    "resultados": [
        {"nombre_completo": "JUAN, DIEGO", "voto": "SI"},
        {"nombre_completo": "MARIA, ROSA", "voto": "NO"}
    ],
    "stats": {"records_out": 2}
}
```

#### `extraction_first_second(resultados: list) -> list`
Splits full names into separate `nombre` and `apellido` fields.

**Transforms:**
- Input: `{"nombre_completo": "PEREZ, JUAN"}`
- Output: `{"apellido": "PEREZ", "nombre": "JUAN", "nombre_completo": "PEREZ JUAN"}`

---

### "Deja Constancia" Block Handling

Parliamentary documents often contain exceptions at the end (known as "DEJA CONSTANCIA" sections).

#### `find_below_block(text: str) -> str`
Locates the "DEJA CONSTANCIA" section of text.

**Example:**
```
"DEJA CONSTANCIA DE QUE LOS VOTOS A FAVOR SON: ..."
```

#### `clean_vote_block(text: str) -> str`
Cleans exception blocks by:
- Removing newlines
- Removing content between `**`
- Removing symbols (`&`, `|`)
- Removing numbers
- Removing "FALLECIDOS (F)" markers
- Normalizing spaces

#### `extract_constancias(text: str) -> List[Dict[str, str]]`
Extracts individual votes from "DEJA CONSTANCIA" sections.

**Identifies three vote sections:**
- `VOTO A FAVOR DE` → vote = "SI"
- `VOTO EN CONTRA DE` → vote = "NO"  
- `VOTO EN ABSTENCION` → vote = "ABST"

**Splits names using:** commas, semicolons, "Y" (and)

**Example:**
```python
text = "VOTO A FAVOR: JUAN, DIEGO; MARIA, ROSA"
extract_constancias(text)
# Returns:
# [
#   {"nombre_completo": "JUAN, DIEGO", "voto": "SI"},
#   {"nombre_completo": "MARIA, ROSA", "voto": "SI"}
# ]
```

---

### Congressman Database Preparation

#### `format_jsn(congresistas: list) -> list`
Prepares the congressman database from JSON.

**Input:** Raw JSON list with fields: `id`, `nombre`, `apellido`, `party_name`, `bancada`, `en_ejercicio`, `periodo`

**Output:** Formatted list with:
- Normalized names (uppercase, no accents)
- `nombre_completo`: "APELLIDO NOMBRE" format
- `voto`: initially `None` (to be filled)
- Keep all original fields

#### `define_enejercicio(congresistas_raw: list, fecha: tuple) -> list`
Filters congresspeople by their service period on the voting date.

**Logic:**
- For each congressman, check if `fecha` falls within their `periodo` (inicio/fin dates)
- Keep only those who were in office on that date
- Set `en_ejercicio = True` for matched records

**Example:**
```python
# Only includes congresspeople who were serving on 15/06/2023
define_enejercicio(reps, (2023, 6, 15))
```

#### `define_bancada(congresistas_raw: list, fecha: tuple) -> list`
Updates congressman political party/faction based on the voting date.

**Logic:**
- Looks at `bancada` list (which has date periods for party changes)
- Finds which party member belonged to on the voting date

---

### Vote Matching Functions

The matching system uses **Jaro-Winkler similarity** (0.0-1.0 score) to match extracted names to congressman database.

#### `matching_lists(lst_congres: list, lst_results: list, threshold=0.90) -> list`
Primary full-name matching pass.

**Algorithm:**
1. For each congressman without a vote yet
2. Find the best Jaro-Winkler match in results (highest score)
3. If score ≥ threshold, assign the vote
4. Prevents one-to-one matching (each result used only once)

**Parameters:**
- `threshold`: minimum similarity score (default 0.90 = 90% match)

**Example:**
```python
# "JUAN PEREZ" in records matches "JUAN PEREZ" in congressman list
jws("JUAN PEREZ", "JUAN PEREZ")  # Score: 1.0 (exact match)
jws("JUAN PEREZ", "JUAN PEROL")  # Score: ~0.95 (one character diff)
```

#### `matching_last_name(lst_congres: list, lst_attendance: list, text_below=False) -> list`
Secondary last-name only matching.

**Algorithm:**
1. Normalize last names
2. Sort both lists by last name
3. Find first matching last name with similarity ≥ 0.95
4. Assign vote if found

**Parameters:**
- `text_below`: If `False`, only match those without votes yet. If `True`, force match everyone.

### Helper/Exception Functions

#### `run_exceptions(lst_attendance: list) -> list`
Applies manual corrections for known OCR errors or special cases.

**Current fixes:**
- `"ECHAIZ DE NUNEZ IZAGA"` → `"ECHAIZ RAMOS VDA DE NUNEZ"`

#### `run_brothers(lst_attendance: list) -> list`
Applies special rules for handling similarly-named individuals.

**Current fixes:**
- `"HECTOR ACUNA PERALTA"` → `"SEGUNDO HECTOR ACUNA PERALTA"`

---

## Main Entry Point

#### `transformation_final(texto: str, congresistas_raw: list) -> list`
**The complete pipeline function.**

**Input:**
- `texto`: Raw document text (OCR output or plain text)
- `congresistas_raw`: List of congresspeople from JSON database

**Process:**
1. Normalize text
2. Detect document type (VOTACION/ASISTENCIA)
3. Locate header and table blocks
4. Extract date and title from header
5. Parse vote table
6. Extract and clean exception votes ("DEJA CONSTANCIA")
7. Format congressman database
8. Filter to active members on voting date
9. Update party affiliations for voting date
10. **Apply four-pass matching:**
    - Pass 1: Full name matching (`matching_lists`)
    - Pass 2: Last name matching on unmatched votes (`matching_last_name`)
    - Pass 3: Last name matching on exception votes with force flag
    - Pass 4: Full name matching on exception votes

**Output:**
```python
[
    {
        "id": "12345",
        "nombre": "JUAN",
        "apellido": "PEREZ",
        "nombre_completo": "PEREZ JUAN",
        "partido": "APRISTA",
        "bancada": "FRENTE AMPLIO",
        "en_ejercicio": True,
        "voto": "SI",  # Filled by matching
        "periodo": {"inicio": "01/01/2021", "fin": "31/12/2026"}
    },
    # ... more records
]
```

---

## Usage Example

```python
from backend.process import extract_votes_DS as ev
import json

# Load data
votes_text = open("voting_document.txt").read()
with open("congresistas_database.json") as f:
    congresistas = json.load(f)

# Extract and match votes
results = ev.transformation_final(votes_text, congresistas)

# Access results
for rep in results:
    print(f"{rep['nombre_completo']}: {rep['voto']}")
```

---

## Regex Patterns

| Pattern | Matches | Example |
|---------|---------|---------|
| `DOBLE_RE` | Full vote table row | `JUAN, DIEGO \| SI` |
| `VOTE_RE` | Vote tokens | `SI`, `NO`, `AUS`, `ABST`, `*` |
| `FAVOR_HDR` | "Votes in favor" header | `VOTO A FAVOR DE CONGRESISTAS` |
| `CONTRA_HDR` | "Votes against" header | `VOTO EN CONTRA DE CONGRESISTAS` |
| `ABST_HDR` | "Abstention votes" header | `VOTO EN ABSTENCION DEL CONGRESISTA` |

---

## Data Requirements

### Input: `congresistas_raw` JSON Structure
```json
{
    "id": "string",
    "nombre": "string",
    "apellido": "string", 
    "party_name": "string",
    "bancada": [
        {
            "name": "string",
            "periodo": {
                "inicio": "DD/MM/YYYY",
                "fin": "DD/MM/YYYY"
            }
        }
    ],
    "en_ejercicio": boolean,
    "periodo": {
        "inicio": "DD/MM/YYYY",
        "fin": "DD/MM/YYYY"
    }
}
```

---

## Error Handling

- **OCR errors:** Normalized through `normalize_text()` and exception functions
- **Missing dates:** Falls back to raw text; `_parse_fecha()` returns `None` on failure
- **Non-matching names:** Left with `voto: None` after all matching passes
- **Type detection failure:** Returns generic processing (no special handling)

---

## Performance Notes

- Jaro-Winkler similarity is O(n×m) where n=congresspeople, m=vote records
- Four-pass matching ensures high accuracy but trades speed for completeness
- One-to-one matching constraint prevents duplicates but may miss some votes
