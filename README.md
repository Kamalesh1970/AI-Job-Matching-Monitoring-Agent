# AI Job-Matching & Monitoring Agent (Phase 1)

A reliable, modular Phase 1 job ingestion pipeline for automated job discovery using the Adzuna API, SQLite database, data normalization, exact deduplication, and fingerprint generation.

Designed for a B.Tech Artificial Intelligence & Data Science student in India seeking relevant AI, ML, Data Science, and Python Developer positions.

---

## 1. Project Purpose

The long-term goal of the AI Job-Matching & Monitoring Agent is to automate the discovery, deduplication, semantic matching/ranking, resume tailoring, and notification of relevant AI/ML job opportunities.

Phase 1 establishes a production-grade, highly testable ingestion foundation built specifically for the **Adzuna API**.

---

## 2. Phase 1 Scope

### Included in Phase 1:
- Configurable environment management using `python-dotenv`
- Adzuna API client with search keywords, pagination, and error handling
- Abstract job source interface (`BaseJobSource`) for future multi-source expansion
- Standardized internal `Job` data model
- Normalization layer for raw job data (HTML stripping, location/company normalization, salary handling)
- SQLite database persistence with `first_seen_at` and `last_seen_at` tracking
- Level 1 exact deduplication (`source` + `source_job_id`)
- Level 2 cross-source deduplication foundation (SHA-256 fingerprinting based on normalized company, title, location)
- Formatted console output with discovery list and execution summary
- Isolated error handling (keyword request failure does not abort pipeline execution)
- Comprehensive `pytest` unit & integration test suite (100% mocked external HTTP calls)

### Explicitly Out of Scope in Phase 1:
- Resume parsing or embeddings
- Semantic matching or LLM calls
- Resume tailoring
- Telegram, Gmail, or email notifications
- Web scraping (LinkedIn, Indeed, Naukri, Internshala, etc.)
- APScheduler or cron scheduling
- Cloud deployment (OCI, AWS, etc.)
- FastAPI or web user interfaces
- Autonomous application submission

---

## 3. Ingestion Architecture

```
[Adzuna API]
     │
     ▼
[AdzunaJobSource (BaseJobSource)]
     │
     ▼
[Normalization Layer] ──► [SHA-256 Fingerprint Generator]
     │
     ▼
[SQLite Storage & Deduplication Engine (data/jobs.db)]
     ├── Exact Match Check (source + source_job_id)
     ├── Insert New Job ──► Record first_seen_at & last_seen_at
     └── Update Existing Job ──► Update last_seen_at ONLY
     │
     ▼
[Console Output & Execution Summary]
```

---

## 4. Project Structure

```
ai-job-matching-agent/
│
├── app/
│   ├── __init__.py
│   ├── config.py              # Environment configuration & validation
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py        # SQLite schema initialization and operations
│   │   └── models.py          # Internal normalized Job model
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseJobSource abstract class
│   │   └── adzuna.py          # Adzuna API client implementation
│   ├── services/
│   │   ├── __init__.py
│   │   ├── normalization.py   # Raw response to Job model transformation
│   │   └── deduplication.py   # Level 2 fingerprint generation
│   └── main.py                # Main CLI entrypoint
│
├── tests/
│   ├── __init__.py
│   ├── test_config.py         # Configuration tests
│   ├── test_adzuna.py         # Adzuna API client tests (mocked HTTP)
│   ├── test_normalization.py  # Normalization & HTML cleanup tests
│   ├── test_deduplication.py  # Fingerprint & deduplication tests
│   ├── test_database.py       # SQLite database operations & timestamp tests
│   └── test_pipeline.py      # End-to-end pipeline & error isolation tests
│
├── data/
│   └── .gitkeep               # Directory holder for runtime jobs.db
│
├── .env                       # Local secrets (git-ignored)
├── .env.example               # Template environment configuration
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python dependencies
└── README.md                  # Project documentation
```

---

## 5. Prerequisites

- Python 3.9+
- Adzuna API Developer Account (`app_id` and `app_key`)

---

## 6. Setup & Installation

### Step 1: Clone or Navigate to the Repository

```bash
cd "AI Job-Matching & Monitoring Agent"
```

### Step 2: Create and Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 7. Configuration (.env)

Copy `.env.example` to create your local `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and fill in your Adzuna API credentials:

```ini
ADZUNA_APP_ID=your_adzuna_app_id_here
ADZUNA_APP_KEY=your_adzuna_app_key_here
ADZUNA_COUNTRY=in
ADZUNA_RESULTS_PER_PAGE=20
ADZUNA_MAX_PAGES=2
```

> **Note**: The pipeline will fail immediately with a descriptive error message if `ADZUNA_APP_ID` or `ADZUNA_APP_KEY` is missing or empty.

---

## 8. Running the Application

To run the job ingestion pipeline:

```bash
python3 -m app.main
```

### Example Console Output

```
==================================================
NEW JOBS DISCOVERED
==================================================

[1]
Title: Machine Learning Engineer
Company: AI Labs Pvt Ltd
Location: Bengaluru, India
Salary: ₹8,00,000 - ₹14,00,000
Source: Adzuna
URL: https://www.adzuna.in/land/ad/...
--------------------------------------------------

Fetch summary
------------------------------
Search keywords: 10
Jobs fetched: 47
New jobs: 31
Existing jobs: 16
Failed requests: 0
------------------------------
```

---

## 9. Running Tests

The test suite uses `pytest` and does **not** rely on live external API requests. All network calls are mocked.

Run all tests:

```bash
pytest -v
```

---

## 10. Database Location & Schema

SQLite database path: `data/jobs.db`

### Key Timestamps
- `first_seen_at`: ISO timestamp recorded when the pipeline first discovers a job.
- `last_seen_at`: ISO timestamp recorded whenever the pipeline re-observes the job on subsequent runs.

---

## 11. Deduplication Strategy

1. **Level 1 (Exact Deduplication)**: Composite UNIQUE constraint on `(source, source_job_id)`. Prevents duplicate rows when the same job appears under multiple search keywords.
2. **Level 2 (Cross-Source Groundwork)**: SHA-256 fingerprint generated from normalized `company + title + location`. Prepared for Phase 2 when additional sources are added.

---

## 12. Error Handling & Resilience

- **Keyword Error Isolation**: If an API request fails for a specific search keyword (e.g. network timeout, 500 error), the error is logged and the pipeline immediately proceeds to the next keyword.
- **Log Sanitation**: Credentials (`ADZUNA_APP_KEY`) are never printed in application logs.

---

## 13. Future Phases

- **Phase 2**: Multi-source fetchers (Jooble, RemoteOK, Arbeitnow), cross-source deduplication using fingerprints.
- **Phase 3**: Vector embeddings (sentence-transformers / Gemini API) & hybrid semantic matching against student resume / target roles.
- **Phase 4**: Automated resume tailoring & Telegram / Email notification bot.
# AI-Job-Matching-Monitoring-Agent
