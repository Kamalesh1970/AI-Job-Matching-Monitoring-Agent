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
| **Jooble** | `jooble` | REST API | `POST https://jooble.org/api/{api_key}` | `JOOBLE_API_KEY` | Free Tier (API Key) | `REQUIRES_USER_SETUP` |
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
- **Smoke Test Outcome**: **SUCCESS** (250 jobs fetched).
- **Limitations**: Focuses primarily on European and remote positions.

### 2.2 RemoteOK
- **Source Identifier**: `remoteok`
- **Class**: `RemoteOKJobSource` ([`app/sources/remoteok.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/remoteok.py))
- **Access Endpoint**: `https://remoteok.com/api` (HTTP GET)
- **Header Requirements**: `User-Agent` header required (e.g., `Mozilla/5.0 ... AIJobAgent/1.0`).
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_REMOTEOK_ENABLED=true` (Default: `true`)
- **Rate Limits**: None explicitly enforced for personal query volumes.
- **Status**: `IMPLEMENTED`
- **Smoke Test Outcome**: **SUCCESS** (99 jobs fetched).
- **Limitations**: Array element 0 is a legal disclaimer block which is automatically filtered by `RemoteOKJobSource`.

### 2.3 Jobicy
- **Source Identifier**: `jobicy`
- **Class**: `JobicyJobSource` ([`app/sources/jobicy.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/jobicy.py))
- **Access Endpoint**: `https://jobicy.com/api/v2/remote-jobs` (HTTP GET)
- **Parameters**: `count` (1–50), optional `tag` or `geo`.
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_JOBICY_ENABLED=true` (Default: `true`)
- **Rate Limits**: Standard web service rate limits.
- **Status**: `IMPLEMENTED`
- **Smoke Test Outcome**: **SUCCESS** (50 jobs fetched).
- **Limitations**: Concentrates on remote technical and creative roles.

### 2.4 Himalayas
- **Source Identifier**: `himalayas`
- **Class**: `HimalayasJobSource` ([`app/sources/himalayas.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/himalayas.py))
- **Access Endpoint**: `https://himalayas.app/jobs/api` (HTTP GET)
- **Parameters**: `limit` (default 50), `offset`.
- **Authentication**: None required.
- **Environment Variables**:
  - `SOURCE_HIMALAYAS_ENABLED=true` (Default: `true`)
- **Rate Limits**: None explicitly enforced for personal query volumes.
- **Status**: `IMPLEMENTED`
- **Smoke Test Outcome**: **SUCCESS** (20 jobs fetched).
- **Limitations**: Global remote job board dataset.

### 2.5 Jooble
- **Source Identifier**: `jooble`
- **Class**: `JoobleJobSource` ([`app/sources/jooble.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/jooble.py))
- **Access Endpoint**: `https://jooble.org/api/{api_key}` (HTTP POST)
- **Payload Format**: `{"keywords": "...", "location": "...", "page": 1}`
- **Authentication**: Free registration API key required.
- **Environment Variables**:
  - `SOURCE_JOOBLE_ENABLED=true`
  - `JOOBLE_API_KEY=your_key_here`
- **Rate Limits**: 500 requests/day on free tier.

### 2.6 Naukri Email Alert Source
- **Source Identifier**: `naukri_email`
- **Class**: `NaukriAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `NaukriEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_NAUKRI_ENABLED=true` (Default: `true`)
  - `GMAIL_NAUKRI_QUERY="from:naukri.com subject:job"`
- **ID Extraction**: `nk_<job_id>` from `naukri.com/job-listings-<id>` or `naukri.com/job-details-<id>`.
- **Status**: `IMPLEMENTED`

### 2.7 Glassdoor Email Alert Source
- **Source Identifier**: `glassdoor_email`
- **Class**: `GlassdoorAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `GlassdoorEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_GLASSDOOR_ENABLED=true` (Default: `true`)
  - `GMAIL_GLASSDOOR_QUERY="from:glassdoor.com subject:job"`
- **ID Extraction**: `gd_<job_id>` from `glassdoor.com/job-listing/...` or `jl=<id>`.
- **Status**: `IMPLEMENTED`

### 2.8 Unstop Email Alert Source
- **Source Identifier**: `unstop_email`
- **Class**: `UnstopAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `UnstopEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_UNSTOP_ENABLED=true` (Default: `true`)
  - `GMAIL_UNSTOP_QUERY="from:(unstop.com OR d2c.in) subject:job"`
- **ID Extraction**: `un_<job_id>` from `unstop.com/o/<id>` or `opportunityId=<id>`.
- **Status**: `IMPLEMENTED`

### 2.9 foundit Email Alert Source
- **Source Identifier**: `foundit_email`
- **Class**: `founditAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `founditEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_FOUNDIT_ENABLED=true` (Default: `true`)
  - `GMAIL_FOUNDIT_QUERY="from:(foundit.in OR monsterindia.com) subject:job"`
- **ID Extraction**: `fm_<job_id>` from `foundit.in/job/<id>` or `jobId=<id>`.
- **Status**: `IMPLEMENTED`

### 2.10 Cutshort Email Alert Source
- **Source Identifier**: `cutshort_email`
- **Class**: `CutshortAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `CutshortEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_CUTSHORT_ENABLED=true` (Default: `true`)
  - `GMAIL_CUTSHORT_QUERY="from:(cutshort.io OR cutshort.com) subject:job"`
- **ID Extraction**: `cs_<job_id>` from `cutshort.io/job/<id>` or `jobId=<id>`.
- **Status**: `IMPLEMENTED`

### 2.11 Hirist Email Alert Source
- **Source Identifier**: `hirist_email`
- **Class**: `HiristAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `HiristEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_HIRIST_ENABLED=true` (Default: `true`)
  - `GMAIL_HIRIST_QUERY="from:(hirist.com OR hirist.tech) subject:job"`
- **ID Extraction**: `hi_<job_id>` from `hirist.tech/j/<id>` or `jobId=<id>`.
- **Status**: `IMPLEMENTED`

### 2.12 Wellfound Email Alert Source
- **Source Identifier**: `wellfound_email`
- **Class**: `WellfoundAlertEmailSource` ([`app/sources/gmail/gmail_source.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/gmail_source.py))
- **Parser**: `WellfoundEmailParser` ([`app/sources/gmail/email_parser.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/email_parser.py))
- **Access Endpoint**: Gmail API `users.messages.list` & `users.messages.get` (Read-only OAuth 2.0)
- **Authentication**: `credentials.json` / `token.json` (`https://www.googleapis.com/auth/gmail.readonly`)
- **Environment Variables**:
  - `SOURCE_WELLFOUND_ENABLED=true` (Default: `true`)
  - `GMAIL_WELLFOUND_QUERY="from:(wellfound.com OR angel.co) newer_than:2d"`
- **ID Extraction**: `wf_<job_id>` from `wellfound.com/jobs/<id>`, `wellfound.com/l/<slug>`, or `jobId=<id>`.
- **Parser Behavior**: Decodes MIME structure (`text/plain`, `text/html`), normalizes whitespace, strips tracking parameters, extracts title, company, location, salary/equity info, and description. Does not execute JavaScript or fetch external resources.
- **Security & Scope**: No direct web scraping of Wellfound. No browser automation or CAPTCHA bypass. Operates strictly via read-only Gmail API (`gmail.readonly`).
- **Status**: `IMPLEMENTED`

---


## 3. Deduplication & Normalization

- **Level 1 Source Deduplication**: `(source, source_job_id)` is enforced at database level with unique SQLite constraints.
- **Level 2 Cross-Source Deduplication**: A 64-character SHA-256 fingerprint digest (`generate_fingerprint`) is computed from normalized `(company, title, location)`. Equivalent listings across different job sources (e.g. Arbeitnow vs RemoteOK) are deduplicated during pipeline matching (`DigestService`) while preserving source provenance.
