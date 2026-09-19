# Phase 10.1 — Priority Job Platform Access & Capability Audit

This document presents the official Phase 10.1 audit for priority job platforms, evaluating access mechanisms, public API availability, authentication constraints, rate limits, anti-bot policies, and recommended integration paths.

---

## 1. Executive Summary & Platform Capability Matrix

| Platform | Recommended Access Method | Authentication | Free/Paid | Rate Limits | Anti-Bot & Automation Status | Implementation Status | Manual Setup Required |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **LinkedIn** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota (250 units/sec) | Direct web scraping blocked; Email ingestion authorized | `IMPLEMENTED` (Phase 6) | User Gmail OAuth grant |
| **Indeed** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota (250 units/sec) | Direct web scraping blocked; Email ingestion authorized | `IMPLEMENTED` (Phase 6) | User Gmail OAuth grant |
| **Internshala** | Public Web Search Adapter | None | Free Public | Rate-limiting jitter (2–5s delay) | Conservative personal-scale request pacing | `IMPLEMENTED` (Phase 5) | None |
| **Naukri** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota | Cloudflare / Akamai protected; Direct web scraping prohibited | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |
| **Glassdoor** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota | Cloudflare Turnstile protected; API retired | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |
| **Unstop** | Native Gmail Job-Alert Email / Public Page | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota / Page delay | Web pages accessible; Email alerts cleaner | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |
| **foundit** (Monster) | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota | Anti-bot session protection; Direct web scraping restricted | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |
| **Cutshort** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota | Authenticated SPA / Login required | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |
| **Hirist** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota | Direct scraping restricted | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |
| **Wellfound** | Native Gmail Job-Alert Email | Gmail OAuth 2.0 (`gmail.readonly`) | Free | Gmail API quota | DataDome / Cloudflare protected; Public API retired | `IMPLEMENTABLE_EMAIL` | User job alert & Gmail OAuth |

---

## 2. Detailed Platform Analysis

### 2.1 Naukri (Naukri.com)
- **Official Public API**: None available for individual job seekers (B2B recruiter enterprise APIs require corporate licensing).
- **Web Scraping Restrictions**: Protected by Cloudflare and Akamai bot defense. Direct HTTP scraping violates Naukri Terms of Service.
- **Native Job-Alert Email**: **Available & High Quality**. Naukri dispatches structured email alerts from `naukrialerts@naukri.com` containing job title, company name, key skills, location, experience, and direct application links.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` via Phase 6 `GmailAlertEmailSource`.

### 2.2 Glassdoor
- **Official Public API**: Public developer API retired. Glassdoor restricts API access strictly to enterprise partners.
- **Web Scraping Restrictions**: Heavily protected by Cloudflare Turnstile and bot management. Unauthenticated scraping triggers CAPTCHAs.
- **Native Job-Alert Email**: **Available**. Glassdoor sends daily job recommendation emails from `noreply@glassdoor.com` / `alerts@glassdoor.com` with job title, company, rating, location, and apply link.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` via Phase 6 `GmailAlertEmailSource`.

### 2.3 Unstop (formerly Dare2Compete)
- **Official Public API**: None published for public candidate ingestion.
- **Web Scraping Restrictions**: Public job listings exist on `https://unstop.com/jobs`.
- **Native Job-Alert Email**: **Available**. Unstop sends periodic job and internship digests from `noreply@unstop.com`.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` (Primary) / `IMPLEMENTABLE_PUBLIC_PAGE` (Secondary).

### 2.4 foundit (formerly Monster India)
- **Official Public API**: None available for job seekers.
- **Web Scraping Restrictions**: Session/login constraints and anti-bot systems restrict raw scraping.
- **Native Job-Alert Email**: **Available**. foundit sends structured job notifications from `jobalerts@foundit.in` or `jobalerts@monsterindia.com` containing job title, company, skills, location, and job links.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` via Phase 6 `GmailAlertEmailSource`.

### 2.5 Cutshort
- **Official Public API**: None.
- **Web Scraping Restrictions**: Dynamic SPA requiring user session authentication; direct web collection prohibited.
- **Native Job-Alert Email**: **Available**. Cutshort sends job recommendation digests from `notifications@cutshort.io` or `alerts@cutshort.io` containing job role, company, salary range, and application links.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` via Phase 6 `GmailAlertEmailSource`.

### 2.6 Hirist
- **Official Public API**: None published.
- **Web Scraping Restrictions**: Direct automated collection on search pages is restricted.
- **Native Job-Alert Email**: **Available**. Hirist sends daily tech job alerts from `jobalerts@hirist.com` containing title, company, experience, location, and job URL.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` via Phase 6 `GmailAlertEmailSource`.

### 2.7 Wellfound (formerly AngelList Talent)
- **Official Public API**: Public API retired; enterprise access only.
- **Web Scraping Restrictions**: DataDome and Cloudflare bot detection block automated scrapers.
- **Native Job-Alert Email**: **Available**. Wellfound sends curated startup job alerts from `talent@wellfound.com` or `notifications@wellfound.com` with job role, startup name, location, salary/equity range, and apply link.
- **Recommended Ingestion Method**: `IMPLEMENTABLE_EMAIL` via Phase 6 `GmailAlertEmailSource`.

---

## 3. Integration Architecture Strategy

To add support for Phase 10 target platforms without creating duplicate code abstractions:

1. **Leverage Phase 6 Gmail Architecture**:
   - Extend `GmailAlertEmailSource` ([`app/sources/gmail/base.py`](file:///home/kamalesh/AI%20Job-Matching%20%26%20Monitoring%20Agent/app/sources/gmail/base.py)) by creating lightweight query-specific subclasses or parsers for Naukri, Glassdoor, foundit, Cutshort, Hirist, and Wellfound.
   - Example Gmail search queries:
     - Naukri: `from:(naukri.com) newer_than:2d`
     - Glassdoor: `from:(glassdoor.com) newer_than:2d`
     - foundit: `from:(foundit.in OR monsterindia.com) newer_than:2d`
     - Cutshort: `from:(cutshort.io) newer_than:2d`
     - Hirist: `from:(hirist.com) newer_than:2d`
     - Wellfound: `from:(wellfound.com) newer_than:2d`

2. **Zero Abstraction Bloat**:
   - Every new source inherits from `BaseJobSource` and registers in `JobSourceRegistry`.
   - All parsed jobs are normalized into the single `Job` model with SHA-256 content fingerprinting.
   - Each source is independently toggleable via environment variables (`SOURCE_NAUKRI_ENABLED`, `SOURCE_GLASSDOOR_ENABLED`, etc.).

---

## 4. Platform Categorization Summary

- **Platforms Ready for Implementation (via Gmail Alert Ingestion)**:
  1. Naukri (`IMPLEMENTABLE_EMAIL`)
  2. Glassdoor (`IMPLEMENTABLE_EMAIL`)
  3. foundit (`IMPLEMENTABLE_EMAIL`)
  4. Cutshort (`IMPLEMENTABLE_EMAIL`)
  5. Hirist (`IMPLEMENTABLE_EMAIL`)
  6. Wellfound (`IMPLEMENTABLE_EMAIL`)
  7. Unstop (`IMPLEMENTABLE_EMAIL`)

- **Platforms Requiring Gmail Alerts**:
  All 7 audited platforms require Gmail alert email ingestion (`gmail.readonly` OAuth) to bypass CAPTCHA, Cloudflare, and login restrictions legitimately and safely.

- **Platforms That Should NOT Be Directly Automated via Web Scraping**:
  - Naukri, Glassdoor, Cutshort, Wellfound, foundit, Hirist (Direct web scraping is blocked, risks IP ban, and violates Terms of Service).
