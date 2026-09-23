# Multi-Source Job Intelligence Architecture & Source Capability Matrix

This document provides official developer documentation for all job sources integrated into the AI Job-Matching & Monitoring Agent, covering access mechanisms, authentication requirements, configuration parameters, rate limits, status classifications, and limitations.

---

## 1. Integrated Sources Summary & Status Matrix

| Source Name | Identifier | Source Type | Access Mechanism | Authentication | Free Access | Implementation Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Adzuna** | `adzuna` | REST API | `GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}` | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Free Tier (API Key) | `IMPLEMENTED` |
| **Internshala** | `internshala` | Web Search | `GET https://internshala.com/internships/{keyword}-internships` | None | Free Public Web | `IMPLEMENTED` |
| **LinkedIn Email** | `linkedin_alert_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Indeed Email** | `indeed_alert_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Arbeitnow** | `arbeitnow` | REST API | `GET https://www.arbeitnow.com/api/job-board-api` | None | Free Public API | `IMPLEMENTED` |
| **RemoteOK** | `remoteok` | REST API | `GET https://remoteok.com/api` (User-Agent header required) | None | Free Public API | `IMPLEMENTED` |
| **Jobicy** | `jobicy` | REST API | `GET https://jobicy.com/api/v2/remote-jobs` | None | Free Public API | `IMPLEMENTED` |
| **Himalayas** | `himalayas` | REST API | `GET https://himalayas.app/jobs/api` | None | Free Public API | `IMPLEMENTED` |
| **Jooble** | `jooble` | REST API | `POST https://jooble.org/api/{api_key}` | `JOOBLE_API_KEY` | Free Tier (API Key) | `IMPLEMENTED` |
| **JSearch** | `jsearch` | REST API | `GET https://jsearch.p.rapidapi.com/search` | `JSEARCH_API_KEY`, `JSEARCH_RAPIDAPI_HOST` | RapidAPI Free Tier | `IMPLEMENTED` |
| **SerpApi (Google Jobs)** | `serpapi` | REST API | `GET https://serpapi.com/search?engine=google_jobs` | `SERPAPI_KEY` | Free Tier (100 searches/mo) | `IMPLEMENTED` |
| **Active Jobs DB** | `active_jobs_db` | REST API | `GET https://active-jobs-db.p.rapidapi.com/active-ats-promoted-jobs` | `ACTIVE_JOBS_DB_API_KEY`, `ACTIVE_JOBS_DB_RAPIDAPI_HOST` | RapidAPI Free Tier | `IMPLEMENTED` |
| **Naukri Email** | `naukri_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Glassdoor Email** | `glassdoor_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Unstop Email** | `unstop_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **foundit Email** | `foundit_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Cutshort Email** | `cutshort_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Hirist Email** | `hirist_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |
| **Wellfound Email** | `wellfound_email` | Gmail API | Read-Only Gmail OAuth 2.0 (`gmail.readonly`) | `credentials.json` / `token.json` | Free | `IMPLEMENTED` |

---

## 2. Source Details & Specifications

### 2.1 Arbeitnow
- **Source Identifier**: `arbeitnow`
- **Class**: `ArbeitnowJobSource` ([`app/sources/arbeitnow.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/arbeitnow.py))
- **Access Endpoint**: `https://www.arbeitnow.com/api/job-board-api` (HTTP GET)
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_ARBEITNOW_ENABLED=true` (Default: `true`)
- **Rate Limits**: None explicitly enforced for reasonable query volumes (~100 req/min).
- **Status**: `IMPLEMENTED`
- **Limitations**: Focuses primarily on European and remote positions.

### 2.2 RemoteOK
- **Source Identifier**: `remoteok`
- **Class**: `RemoteOKJobSource` ([`app/sources/remoteok.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/remoteok.py))
- **Access Endpoint**: `https://remoteok.com/api` (HTTP GET)
- **Header Requirements**: `User-Agent` header required.
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_REMOTEOK_ENABLED=true` (Default: `true`)
- **Rate Limits**: None explicitly enforced for personal query volumes.
- **Status**: `IMPLEMENTED`

### 2.3 Jobicy
- **Source Identifier**: `jobicy`
- **Class**: `JobicyJobSource` ([`app/sources/jobicy.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/jobicy.py))
- **Access Endpoint**: `https://jobicy.com/api/v2/remote-jobs` (HTTP GET)
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_JOBICY_ENABLED=true` (Default: `true`)
- **Status**: `IMPLEMENTED`

### 2.4 Himalayas
- **Source Identifier**: `himalayas`
- **Class**: `HimalayasJobSource` ([`app/sources/himalayas.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/himalayas.py))
- **Access Endpoint**: `https://himalayas.app/jobs/api` (HTTP GET)
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_HIMALAYAS_ENABLED=true` (Default: `true`)
- **Status**: `IMPLEMENTED`

### 2.5 Jooble
- **Source Identifier**: `jooble`
- **Class**: `JoobleJobSource` ([`app/sources/jooble.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/jooble.py))
- **Access Endpoint**: `https://jooble.org/api/{api_key}` (HTTP POST)
- **Payload Format**: `{"keywords": "...", "location": "...", "page": 1}`
- **Authentication**: Free registration API key required.
- **Environment Variables**:
  - `SOURCE_JOOBLE_ENABLED=true` (Default: `true`)
  - `JOOBLE_API_KEY=your_key_here`
- **Rate Limits**: 500 requests/day on free tier.
- **Status**: `IMPLEMENTED`

### 2.6 JSearch (RapidAPI)
- **Source Identifier**: `jsearch`
- **Class**: `JSearchJobSource` ([`app/sources/jsearch.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/jsearch.py))
- **Access Endpoint**: `https://jsearch.p.rapidapi.com/search` (HTTP GET)
- **Headers**:
  - `X-RapidAPI-Key`: `JSEARCH_API_KEY`
  - `X-RapidAPI-Host`: `JSEARCH_RAPIDAPI_HOST` (Default: `jsearch.p.rapidapi.com`)
- **Parameters**: `query={keyword} in {location}`, `page=1`, `num_pages=1`
- **Authentication**: RapidAPI API Key.
- **Environment Variables**:
  - `SOURCE_JSEARCH_ENABLED=true` (Default: `true`)
  - `JSEARCH_API_KEY=your_rapidapi_key`
  - `JSEARCH_RAPIDAPI_HOST=jsearch.p.rapidapi.com`
- **Rate Limits**: Subject to RapidAPI subscription plan rate limits.
- **Status**: `IMPLEMENTED`

### 2.7 SerpApi (Google Jobs Engine)
- **Source Identifier**: `serpapi`
- **Class**: `SerpApiJobSource` ([`app/sources/serpapi.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/serpapi.py))
- **Access Endpoint**: `https://serpapi.com/search?engine=google_jobs` (HTTP GET)
- **Parameters**: `engine=google_jobs`, `q={keyword}`, `location={location}`, `api_key={key}`, `output=json`
- **Authentication**: SerpApi API key (`SERPAPI_KEY`).
- **Environment Variables**:
  - `SOURCE_SERPAPI_ENABLED=true` (Default: `true`)
  - `SERPAPI_KEY=your_serpapi_key`
- **Rate Limits**: 100 free searches per month on developer plan.
- **Status**: `IMPLEMENTED`

### 2.8 Active Jobs DB (RapidAPI)
- **Source Identifier**: `active_jobs_db`
- **Class**: `ActiveJobsDBJobSource` ([`app/sources/active_jobs_db.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/active_jobs_db.py))
- **Access Endpoint**: `https://active-jobs-db.p.rapidapi.com/active-ats-promoted-jobs` (HTTP GET)
- **Headers**:
  - `X-RapidAPI-Key`: `ACTIVE_JOBS_DB_API_KEY`
  - `X-RapidAPI-Host`: `ACTIVE_JOBS_DB_RAPIDAPI_HOST` (Default: `active-jobs-db.p.rapidapi.com`)
- **Parameters**: `title_filter={keyword}`, `location_filter={location}`, `limit=20`, `offset=0`
- **Authentication**: RapidAPI API Key (`ACTIVE_JOBS_DB_API_KEY`).
- **Environment Variables**:
  - `SOURCE_ACTIVE_JOBS_DB_ENABLED=false` (Default: `false`)
  - `ACTIVE_JOBS_DB_API_KEY=your_rapidapi_key`
  - `ACTIVE_JOBS_DB_RAPIDAPI_HOST=active-jobs-db.p.rapidapi.com`
- **Rate Limits**: Subject to RapidAPI tier request and job limits.
- **Status**: `IMPLEMENTED`

### 2.9 LinkedIn Jobs API (Authorized API Only)
- **Source Identifier**: N/A (Configuration placeholder only; no registry source added)
- **Provider**: Official LinkedIn API / Talent Solutions (Partner Access Required)
- **Authentication**: OAuth 2.0 / Client Credentials (`LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN`)
- **Environment Variables**:
  - `SOURCE_LINKEDIN_API_ENABLED=false` (Default: `false`)
  - `LINKEDIN_CLIENT_ID=`
  - `LINKEDIN_CLIENT_SECRET=`
  - `LINKEDIN_ACCESS_TOKEN=`
- **Status**: `DISABLED_PENDING_CREDENTIALS`
- **Operational Note**: Direct web scraping or CAPTCHA bypass is strictly prohibited. LinkedIn job alerts ingested via Gmail API (`linkedin_alert_email`) remain fully supported and operational independently.

### 2.10 Indeed Jobs API (Authorized API Only)
- **Source Identifier**: N/A (Configuration placeholder only; no registry source added)
- **Provider**: Official Indeed Partner API / OAuth
- **Authentication**: OAuth 2.0 / Authorized Credentials (`INDEED_CLIENT_ID`, `INDEED_CLIENT_SECRET`, `INDEED_ACCESS_TOKEN`)
- **Environment Variables**:
  - `SOURCE_INDEED_API_ENABLED=false` (Default: `false`)
  - `INDEED_CLIENT_ID=`
  - `INDEED_CLIENT_SECRET=`
  - `INDEED_ACCESS_TOKEN=`
- **Status**: `DISABLED_PENDING_CREDENTIALS`
- **Operational Note**: Direct web scraping or anti-bot bypass is strictly prohibited. Indeed job alerts ingested via Gmail API (`indeed_alert_email`) remain fully supported and operational independently.

### 2.11 Email Alert Sources (Naukri, Glassdoor, Unstop, foundit, Cutshort, Hirist, Wellfound, LinkedIn, Indeed)
- **Access Mechanism**: Read-Only Gmail API (`gmail.readonly`) parsing structured HTML/text alert emails.
- **Authentication**: `credentials.json` and `token.json` OAuth 2.0 flow.
- **Environment Variables**:
  - `SOURCE_GMAIL_ENABLED=true`
  - Individual query variables (`GMAIL_NAUKRI_QUERY`, `GMAIL_LINKEDIN_QUERY`, etc.).
- **Status**: `IMPLEMENTED`

---

## 3. Deduplication & Normalization

- **Level 1 Source Deduplication**: `(source, source_job_id)` is enforced at database level with unique SQLite constraints.
- **Level 2 Cross-Source Deduplication**: A 64-character SHA-256 fingerprint digest (`generate_fingerprint`) is computed from normalized `(company, title, location)`. Equivalent listings across different job sources (e.g. Jooble vs JSearch vs SerpApi) are deduplicated during pipeline execution while preserving source provenance.

