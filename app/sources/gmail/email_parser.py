"""
HTML and MIME Email Parsers for LinkedIn and Indeed Job Alert emails.
Extracts title, company, location, canonical URL, job ID, and snippet descriptions
without relying on single fragile CSS selectors.
"""

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.db.models import Job
from app.services.deduplication import generate_fingerprint
from app.services.normalization import strip_html
from app.sources.gmail.models import ParsedEmailData

logger = logging.getLogger(__name__)


def normalize_linkedin_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes LinkedIn job link and extracts source job ID.
    Example: 'https://www.linkedin.com/comm/jobs/view/3912345678/?refId=abc'
    -> ('https://www.linkedin.com/jobs/view/3912345678', 'li_3912345678')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)

    # Match /jobs/view/<id> or /comm/jobs/view/<id>
    match = re.search(r"/jobs/view/(\d+)", parsed.path)
    if match:
        job_id_num = match.group(1)
        canonical_url = f"https://www.linkedin.com/jobs/view/{job_id_num}"
        source_job_id = f"li_{job_id_num}"
        return canonical_url, source_job_id

    # Fallback clean URL stripping query params
    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.linkedin.com", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"li_{digest}"


def normalize_indeed_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes Indeed job link and extracts job key (jk) or SHA-256 fallback ID.
    Example: 'https://www.indeed.com/rc/clk?jk=1234567890abcdef&from=ja'
    -> ('https://www.indeed.com/viewjob?jk=1234567890abcdef', 'ind_1234567890abcdef')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)
    query_params = parse_qs(parsed.query)

    jk_list = query_params.get("jk")
    if jk_list and jk_list[0]:
        jk_val = jk_list[0].strip()
        canonical_url = f"https://www.indeed.com/viewjob?jk={jk_val}"
        source_job_id = f"ind_{jk_val}"
        return canonical_url, source_job_id

    match = re.search(r"/viewjob.*?jk=([a-zA-Z0-9]+)", url_clean)
    if match:
        jk_val = match.group(1)
        canonical_url = f"https://www.indeed.com/viewjob?jk={jk_val}"
        source_job_id = f"ind_{jk_val}"
        return canonical_url, source_job_id

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.indeed.com", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"ind_{digest}"


class LinkedInEmailParser:
    """
    Parser for LinkedIn job alert emails (HTML and plain-text).
    """

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses a LinkedIn job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("LinkedIn email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        # Find all job links
        job_links = soup.find_all("a", href=re.compile(r"/jobs/view/|linkedin\.com/comm/jobs/view/|linkedin\.com/jobs/view/"))
        
        seen_urls = set()

        for link in job_links:
            try:
                raw_url = link.get("href", "").strip()
                title = strip_html(link.get_text(strip=True))

                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower():
                    # Fallback to link parent/sibling for title
                    container = link.find_parent(["td", "tr", "div", "li"])
                    if container:
                        title_elem = container.find(["h3", "h4", "strong", "b", "a"])
                        if title_elem:
                            title = strip_html(title_elem.get_text(strip=True))

                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_linkedin_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                # Extract company, location, snippet from container box
                company = ""
                location = ""
                description = title

                container = link.find_parent(["td", "tr", "div", "table", "li"])
                if container:
                    container_text = container.get_text(" ", strip=True)

                    # Look for company link or span
                    comp_elem = (
                        container.find("a", href=re.compile(r"linkedin\.com/company/"))
                        or container.select_one(".company-name")
                        or container.select_one(".job-card-container__company-name")
                    )
                    if comp_elem:
                        company = strip_html(comp_elem.get_text(strip=True))

                    # Look for location span or text
                    loc_elem = container.select_one(".job-card-container__metadata-item") or container.select_one(".location")
                    if loc_elem:
                        location = strip_html(loc_elem.get_text(strip=True))

                    # Extract description snippet
                    desc_elem = container.select_one(".job-card-snippet") or container.select_one(".snippet")
                    if desc_elem:
                        description = strip_html(desc_elem.get_text(strip=True))
                    elif container_text:
                        description = container_text[:300]

                # If company or location missing, attempt parsing lines from container text
                if container and (not company or not location):
                    lines = [line.strip() for line in container.get_text("\n", strip=True).split("\n") if line.strip()]
                    if len(lines) >= 2 and not company:
                        for l in lines:
                            if l != title and len(l) < 50 and not company:
                                company = l
                            elif company and l != title and l != company and len(l) < 50 and not location:
                                location = l
                                break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="LinkedIn Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual LinkedIn job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


class IndeedEmailParser:
    """
    Parser for Indeed job alert emails (HTML and plain-text).
    """

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses an Indeed job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("Indeed email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        # Indeed job links typically contain /rc/clk, /viewjob, /pagead/clk, or jk=
        job_links = soup.find_all("a", href=re.compile(r"indeed\.com/rc/clk|indeed\.com/viewjob|indeed\.com/pagead/clk|jk="))
        
        seen_urls = set()

        for link in job_links:
            try:
                raw_url = link.get("href", "").strip()
                title = strip_html(link.get_text(strip=True))

                if not title or len(title) < 2 or "view job" in title.lower() or "apply now" in title.lower():
                    container = link.find_parent(["td", "tr", "div", "li"])
                    if container:
                        title_elem = container.find(["h2", "h3", "h4", "strong", "b", "a"])
                        if title_elem:
                            title = strip_html(title_elem.get_text(strip=True))

                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_indeed_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                container = link.find_parent(["td", "tr", "div", "table", "li"])
                if container:
                    container_text = container.get_text(" ", strip=True)

                    comp_elem = (
                        container.select_one(".companyName")
                        or container.select_one(".company")
                        or container.select_one("span.company")
                    )
                    if comp_elem:
                        company = strip_html(comp_elem.get_text(strip=True))

                    loc_elem = (
                        container.select_one(".companyLocation")
                        or container.select_one(".location")
                        or container.select_one("span.location")
                    )
                    if loc_elem:
                        location = strip_html(loc_elem.get_text(strip=True))

                    snippet_elem = (
                        container.select_one(".jobSnippet")
                        or container.select_one(".snippet")
                        or container.select_one(".summary")
                    )
                    if snippet_elem:
                        description = strip_html(snippet_elem.get_text(strip=True))
                    elif container_text:
                        description = container_text[:300]

                if container and (not company or not location):
                    lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                    for l in lines:
                        if l != title and len(l) < 60:
                            if not company:
                                company = l
                            elif not location and l != company:
                                location = l
                                break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="Indeed Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual Indeed job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


def normalize_naukri_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes Naukri job link and extracts source job ID.
    Example: 'https://www.naukri.com/job-listings-ai-engineer-company-chennai-120923001234?src=jobsearch'
    -> ('https://www.naukri.com/job-listings-ai-engineer-company-chennai-120923001234', 'nk_120923001234')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)

    query_params = parse_qs(parsed.query)
    job_id_param = query_params.get("jobId") or query_params.get("job_id") or query_params.get("id")
    if job_id_param and job_id_param[0]:
        job_id_num = job_id_param[0].strip()
        canonical_url = f"https://www.naukri.com/job-listings-{job_id_num}"
        return canonical_url, f"nk_{job_id_num}"

    match = re.search(r"-(\d{6,})", parsed.path)
    if match:
        job_id_num = match.group(1)
        clean_path = parsed.path.rstrip("/")
        canonical_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.naukri.com", clean_path, "", "", ""))
        return canonical_url, f"nk_{job_id_num}"

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.naukri.com", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"nk_{digest}"


def normalize_glassdoor_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes Glassdoor job link and extracts source job ID.
    Example: 'https://www.glassdoor.com/job-listing/senior-ml-engineer-JV_IC1147401.htm?jl=1008899776'
    -> ('https://www.glassdoor.com/job-listing/?jl=1008899776', 'gd_1008899776')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)
    query_params = parse_qs(parsed.query)

    jl_val = query_params.get("jl") or query_params.get("jobListingId")
    if jl_val and jl_val[0]:
        job_id_num = jl_val[0].strip()
        canonical_url = f"https://www.glassdoor.com/job-listing/?jl={job_id_num}"
        return canonical_url, f"gd_{job_id_num}"

    match = re.search(r"jobListingId=(\d+)|jl=(\d+)", url_clean)
    if match:
        job_id_num = match.group(1) or match.group(2)
        canonical_url = f"https://www.glassdoor.com/job-listing/?jl={job_id_num}"
        return canonical_url, f"gd_{job_id_num}"

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.glassdoor.com", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"gd_{digest}"


class NaukriEmailParser:
    """
    Parser for Naukri job alert emails (HTML and plain-text).
    """

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses a Naukri job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("Naukri email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        job_links = soup.find_all("a", href=re.compile(r"naukri\.com/job-listings|naukri\.com/job-details|naukri\.com/.*?-\d+"))
        
        # Fallback if plain-text email without <a> tags
        raw_urls: List[Tuple[str, str]] = []
        if job_links:
            for link in job_links:
                raw_href = link.get("href", "").strip()
                t_text = re.sub(r"\s+", " ", strip_html(link.get_text(strip=True)))
                if raw_href:
                    raw_urls.append((raw_href, t_text))
        else:
            # Extract URLs from plain text
            text_links = re.findall(r"https?://[^\s\"'>]*naukri\.com[^\s\"'>]*", html)
            for url_match in text_links:
                raw_urls.append((url_match, ""))

        seen_urls = set()

        for raw_url, link_text in raw_urls:
            try:
                # Filter out non-job URLs (e.g. login, unsubscribe, company landing without job id)
                if not re.search(r"job-listings|job-details|naukri\.com/.*?-\d{6,}|jobId=|job_id=", raw_url, re.I):
                    continue

                title = link_text
                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower():
                    # Try extracting title from subject or URL slug
                    if ":" in email_data.subject:
                        title = email_data.subject.split(":")[-1].strip()
                    elif "-" in raw_url:
                        slug_parts = urlparse(raw_url).path.split("/")[-1].split("-")
                        title_words = [p.capitalize() for p in slug_parts if p and not p.isdigit() and p != "job" and p != "listings"]
                        title = " ".join(title_words[:4]) if title_words else "Software Developer"
                    else:
                        title = "Naukri Position"

                title = re.sub(r"\s+", " ", title).strip()
                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_naukri_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                # Search for container box in HTML
                link = soup.find("a", href=raw_url)
                if link:
                    container = link.find_parent(["td", "tr", "div", "table", "li", "body", "html"]) or link.parent
                    if container:
                        container_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True))

                        comp_elem = (
                            container.select_one(".comp-name")
                            or container.select_one(".company")
                            or container.find("a", href=re.compile(r"naukri\.com/.*?company"))
                        )
                        if comp_elem:
                            company = re.sub(r"\s+", " ", strip_html(comp_elem.get_text(strip=True)))

                        loc_elem = (
                            container.select_one(".loc")
                            or container.select_one(".location")
                        )
                        if loc_elem:
                            location = re.sub(r"\s+", " ", strip_html(loc_elem.get_text(strip=True)))

                        snippet_elem = (
                            container.select_one(".desc")
                            or container.select_one(".snippet")
                        )
                        if snippet_elem:
                            description = re.sub(r"\s+", " ", strip_html(snippet_elem.get_text(strip=True)))
                        elif container_text:
                            description = container_text[:300]

                        if (not company or not location):
                            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                            for l in lines:
                                if l != title and len(l) < 60:
                                    if not company:
                                        company = re.sub(r"\s+", " ", l)
                                    elif not location and l != company:
                                        location = re.sub(r"\s+", " ", l)
                                        break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="Naukri Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual Naukri job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


class GlassdoorEmailParser:
    """
    Parser for Glassdoor job alert emails (HTML and plain-text).
    """

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses a Glassdoor job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("Glassdoor email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        job_links = soup.find_all("a", href=re.compile(r"glassdoor\.com/job-listing|glassdoor\.com/partner/jobListing|jl="))
        
        raw_urls: List[Tuple[str, str]] = []
        if job_links:
            for link in job_links:
                raw_href = link.get("href", "").strip()
                t_text = re.sub(r"\s+", " ", strip_html(link.get_text(strip=True)))
                if raw_href:
                    raw_urls.append((raw_href, t_text))
        else:
            text_links = re.findall(r"https?://[^\s\"'>]*glassdoor\.com[^\s\"'>]*", html)
            for url_match in text_links:
                raw_urls.append((url_match, ""))

        seen_urls = set()

        for raw_url, link_text in raw_urls:
            try:
                # Filter out non-job URLs (e.g. login, unsubscribe, profile pages)
                if not re.search(r"glassdoor\.com/job-listing|glassdoor\.com/partner/jobListing|jl=|\bjobListingId=", raw_url, re.I):
                    continue

                title = link_text
                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower():
                    if ":" in email_data.subject:
                        title = email_data.subject.split(":")[-1].strip()
                    elif "-" in raw_url:
                        slug_parts = urlparse(raw_url).path.split("/")[-1].split("-")
                        title_words = [p.capitalize() for p in slug_parts if p and not p.isdigit() and p != "job" and p != "listing"]
                        title = " ".join(title_words[:4]) if title_words else "Glassdoor Position"
                    else:
                        title = "Glassdoor Position"

                title = re.sub(r"\s+", " ", title).strip()
                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_glassdoor_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                link = soup.find("a", href=raw_url)
                if link:
                    container = link.find_parent(["td", "tr", "div", "table", "li", "body", "html"]) or link.parent
                    if container:
                        container_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True))

                        comp_elem = (
                            container.select_one(".employer")
                            or container.select_one(".company")
                            or container.select_one(".employer-name")
                        )
                        if comp_elem:
                            company = re.sub(r"\s+", " ", strip_html(comp_elem.get_text(strip=True)))

                        loc_elem = (
                            container.select_one(".location")
                            or container.select_one(".loc")
                        )
                        if loc_elem:
                            location = re.sub(r"\s+", " ", strip_html(loc_elem.get_text(strip=True)))

                        snippet_elem = (
                            container.select_one(".snippet")
                            or container.select_one(".description")
                        )
                        if snippet_elem:
                            description = re.sub(r"\s+", " ", strip_html(snippet_elem.get_text(strip=True)))
                        elif container_text:
                            description = container_text[:300]

                        if (not company or not location):
                            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                            for l in lines:
                                if l != title and len(l) < 60:
                                    if not company:
                                        company = re.sub(r"\s+", " ", l)
                                    elif not location and l != company:
                                        location = re.sub(r"\s+", " ", l)
                                        break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="Glassdoor Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual Glassdoor job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


def normalize_unstop_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes Unstop (formerly Dare2Compete / d2c.in) job/opportunity link and extracts source job ID.
    Example: 'https://unstop.com/o/senior-ai-engineer-123456?ref=email'
    -> ('https://unstop.com/o/123456', 'un_123456')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)

    query_params = parse_qs(parsed.query)
    job_id_param = query_params.get("opportunityId") or query_params.get("opportunity_id") or query_params.get("id") or query_params.get("jobId")
    if job_id_param and job_id_param[0]:
        job_id_num = job_id_param[0].strip()
        canonical_url = f"https://unstop.com/o/{job_id_num}"
        return canonical_url, f"un_{job_id_num}"

    match = re.search(r"-(\d{4,})", parsed.path) or re.search(r"/(?:o|p|jobs|internships|opportunity|opportunities)/(?:view/)?(\d{4,})", parsed.path)
    if match:
        job_id_num = match.group(1)
        canonical_url = f"https://unstop.com/o/{job_id_num}"
        return canonical_url, f"un_{job_id_num}"

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "unstop.com", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"un_{digest}"


def normalize_foundit_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes foundit (formerly Monster India) job link and extracts source job ID.
    Example: 'https://www.foundit.in/job/software-engineer-company-bangalore-12345678?ref=alert'
    -> ('https://www.foundit.in/job/12345678', 'fm_12345678')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)

    query_params = parse_qs(parsed.query)
    job_id_param = query_params.get("jobId") or query_params.get("job_id") or query_params.get("id") or query_params.get("job_reference")
    if job_id_param and job_id_param[0]:
        job_id_num = job_id_param[0].strip()
        canonical_url = f"https://www.foundit.in/job/{job_id_num}"
        return canonical_url, f"fm_{job_id_num}"

    match = re.search(r"-(\d{5,})", parsed.path) or re.search(r"/job/(?:.*-)?(\d{5,})", parsed.path)
    if match:
        job_id_num = match.group(1)
        canonical_url = f"https://www.foundit.in/job/{job_id_num}"
        return canonical_url, f"fm_{job_id_num}"

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.foundit.in", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"fm_{digest}"


class UnstopEmailParser:
    """
    Parser for Unstop (Dare2Compete) job and opportunity alert emails (HTML and plain-text).
    """

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses an Unstop job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("Unstop email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        job_links = soup.find_all("a", href=re.compile(r"unstop\.com/(?:o|p|jobs|internships|opportunity)|d2c\.in/"))

        raw_urls: List[Tuple[str, str]] = []
        if job_links:
            for link in job_links:
                raw_href = link.get("href", "").strip()
                t_text = re.sub(r"\s+", " ", strip_html(link.get_text(strip=True)))
                if raw_href:
                    raw_urls.append((raw_href, t_text))
        else:
            text_links = re.findall(r"https?://[^\s\"'>]*(?:unstop\.com|d2c\.in)[^\s\"'>]*", html)
            for url_match in text_links:
                raw_urls.append((url_match, ""))

        seen_urls = set()

        for raw_url, link_text in raw_urls:
            try:
                if not re.search(r"unstop\.com/(?:o|p|jobs|internships|opportunity|d2c\.in)|opportunityId=|-(\d{4,})", raw_url, re.I):
                    continue
                if re.search(r"/login|/auth|/privacy|/settings|/about|/contact", raw_url, re.I):
                    continue

                title = link_text
                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower() or "register" in title.lower():
                    if ":" in email_data.subject:
                        title = email_data.subject.split(":")[-1].strip()
                    elif "-" in raw_url:
                        slug_parts = urlparse(raw_url).path.split("/")[-1].split("-")
                        title_words = [p.capitalize() for p in slug_parts if p and not p.isdigit() and p not in ("o", "p", "jobs", "internships", "opportunity")]
                        title = " ".join(title_words[:4]) if title_words else "Unstop Opportunity"
                    else:
                        title = "Unstop Opportunity"

                title = re.sub(r"\s+", " ", title).strip()
                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_unstop_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                link = soup.find("a", href=raw_url)
                if link:
                    container = link.find_parent(["td", "tr", "div", "table", "li", "body", "html"]) or link.parent
                    if container:
                        container_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True))

                        comp_elem = (
                            container.select_one(".organization")
                            or container.select_one(".company")
                            or container.select_one(".org-name")
                            or container.select_one(".company-name")
                        )
                        if comp_elem:
                            company = re.sub(r"\s+", " ", strip_html(comp_elem.get_text(strip=True)))

                        loc_elem = (
                            container.select_one(".location")
                            or container.select_one(".loc")
                            or container.select_one(".city")
                        )
                        if loc_elem:
                            location = re.sub(r"\s+", " ", strip_html(loc_elem.get_text(strip=True)))

                        snippet_elem = (
                            container.select_one(".snippet")
                            or container.select_one(".description")
                            or container.select_one(".summary")
                        )
                        if snippet_elem:
                            description = re.sub(r"\s+", " ", strip_html(snippet_elem.get_text(strip=True)))
                        elif container_text:
                            description = container_text[:300]

                        if (not company or not location):
                            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                            for l in lines:
                                if l != title and len(l) < 60:
                                    if not company:
                                        company = re.sub(r"\s+", " ", l)
                                    elif not location and l != company:
                                        location = re.sub(r"\s+", " ", l)
                                        break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="Unstop Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual Unstop job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


class founditEmailParser:
    """
    Parser for foundit (formerly Monster India) job alert emails (HTML and plain-text).
    """

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses a foundit job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("foundit email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        job_links = soup.find_all("a", href=re.compile(r"foundit\.in/job|monsterindia\.com/job|jobId=|job_details"))

        raw_urls: List[Tuple[str, str]] = []
        if job_links:
            for link in job_links:
                raw_href = link.get("href", "").strip()
                t_text = re.sub(r"\s+", " ", strip_html(link.get_text(strip=True)))
                if raw_href:
                    raw_urls.append((raw_href, t_text))
        else:
            text_links = re.findall(r"https?://[^\s\"'>]*(?:foundit\.in|monsterindia\.com)[^\s\"'>]*", html)
            for url_match in text_links:
                raw_urls.append((url_match, ""))

        seen_urls = set()

        for raw_url, link_text in raw_urls:
            try:
                if not re.search(r"foundit\.in/job|monsterindia\.com/job|jobId=|\bjob_id=|-(\d{5,})", raw_url, re.I):
                    continue
                if re.search(r"/login|/privacy|/terms|/unsubscribe|/seeker/profile", raw_url, re.I):
                    continue

                title = link_text
                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower():
                    if ":" in email_data.subject:
                        title = email_data.subject.split(":")[-1].strip()
                    elif "-" in raw_url:
                        slug_parts = urlparse(raw_url).path.split("/")[-1].split("-")
                        title_words = [p.capitalize() for p in slug_parts if p and not p.isdigit() and p not in ("job", "details", "seeker")]
                        title = " ".join(title_words[:4]) if title_words else "foundit Position"
                    else:
                        title = "foundit Position"

                title = re.sub(r"\s+", " ", title).strip()
                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_foundit_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                link = soup.find("a", href=raw_url)
                if link:
                    container = link.find_parent(["td", "tr", "div", "table", "li", "body", "html"]) or link.parent
                    if container:
                        container_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True))

                        comp_elem = (
                            container.select_one(".company")
                            or container.select_one(".employer")
                            or container.select_one(".company-name")
                            or container.select_one(".employer-name")
                        )
                        if comp_elem:
                            company = re.sub(r"\s+", " ", strip_html(comp_elem.get_text(strip=True)))

                        loc_elem = (
                            container.select_one(".location")
                            or container.select_one(".loc")
                            or container.select_one(".city")
                        )
                        if loc_elem:
                            location = re.sub(r"\s+", " ", strip_html(loc_elem.get_text(strip=True)))

                        snippet_elem = (
                            container.select_one(".snippet")
                            or container.select_one(".description")
                            or container.select_one(".job-desc")
                        )
                        if snippet_elem:
                            description = re.sub(r"\s+", " ", strip_html(snippet_elem.get_text(strip=True)))
                        elif container_text:
                            description = container_text[:300]

                        if (not company or not location):
                            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                            for l in lines:
                                if l != title and len(l) < 60:
                                    if not company:
                                        company = re.sub(r"\s+", " ", l)
                                    elif not location and l != company:
                                        location = re.sub(r"\s+", " ", l)
                                        break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="foundit Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual foundit job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


def normalize_cutshort_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes Cutshort job link and extracts source job ID.
    Example: 'https://cutshort.io/job/Senior-AI-Engineer-Company-1234567?ref=email'
    -> ('https://cutshort.io/job/1234567', 'cs_1234567')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)

    query_params = parse_qs(parsed.query)
    job_id_param = query_params.get("jobId") or query_params.get("job_id") or query_params.get("id")
    if job_id_param and job_id_param[0]:
        job_id_num = job_id_param[0].strip()
        canonical_url = f"https://cutshort.io/job/{job_id_num}"
        return canonical_url, f"cs_{job_id_num}"

    match = re.search(r"-(\d{4,})", parsed.path) or re.search(r"/job/(?:.*-)?(\d{4,})", parsed.path)
    if match:
        job_id_num = match.group(1)
        canonical_url = f"https://cutshort.io/job/{job_id_num}"
        return canonical_url, f"cs_{job_id_num}"

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "cutshort.io", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"cs_{digest}"


def normalize_hirist_url(raw_url: str) -> Tuple[str, str]:
    """
    Normalizes Hirist job link and extracts source job ID.
    Example: 'https://www.hirist.tech/j/backend-developer-company-bangalore-998877.html?ref=alert'
    -> ('https://www.hirist.tech/j/998877', 'hi_998877')
    """
    if not raw_url:
        return "", ""

    url_clean = raw_url.strip()
    parsed = urlparse(url_clean)

    query_params = parse_qs(parsed.query)
    job_id_param = query_params.get("jobId") or query_params.get("job_id") or query_params.get("id")
    if job_id_param and job_id_param[0]:
        job_id_num = job_id_param[0].strip()
        canonical_url = f"https://www.hirist.tech/j/{job_id_num}"
        return canonical_url, f"hi_{job_id_num}"

    match = re.search(r"-(\d{4,})\.html", parsed.path) or re.search(r"-(\d{4,})", parsed.path) or re.search(r"/j/(?:.*-)?(\d{4,})", parsed.path)
    if match:
        job_id_num = match.group(1)
        canonical_url = f"https://www.hirist.tech/j/{job_id_num}"
        return canonical_url, f"hi_{job_id_num}"

    clean_url = urlunparse((parsed.scheme or "https", parsed.netloc or "www.hirist.tech", parsed.path, "", "", ""))
    digest = hashlib.sha256(clean_url.encode("utf-8")).hexdigest()[:16]
    return clean_url, f"hi_{digest}"


class CutshortEmailParser:
    """
    Parser for Cutshort job alert emails (HTML and plain-text).
    """

    @staticmethod
    def is_cutshort_email(email_data: ParsedEmailData) -> bool:
        """
        Classifies whether an email is a Cutshort job alert using multiple signals:
        - Sender domain/address (cutshort.io, cutshort.com)
        - Subject patterns ('cutshort', 'matching role', 'job alert')
        - Platform branding / body structure ('cutshort.io/job', 'cutshort.com/job')
        """
        sender = (email_data.sender or "").lower()
        subject = (email_data.subject or "").lower()
        body = (email_data.plain_text or email_data.html_content or "").lower()

        if any(d in sender for d in ("cutshort.io", "cutshort.com", "cutshort")):
            return True
        if "cutshort" in subject:
            return True
        if "cutshort" in body:
            return True
        return False

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses a Cutshort job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("Cutshort email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        job_links = soup.find_all("a", href=re.compile(r"cutshort\.io/job|cutshort\.com/job|jobId="))

        raw_urls: List[Tuple[str, str]] = []
        if job_links:
            for link in job_links:
                raw_href = link.get("href", "").strip()
                t_text = re.sub(r"\s+", " ", strip_html(link.get_text(strip=True)))
                if raw_href:
                    raw_urls.append((raw_href, t_text))
        else:
            text_links = re.findall(r"https?://[^\s\"'>]*(?:cutshort\.io|cutshort\.com)[^\s\"'>]*", html)
            for url_match in text_links:
                raw_urls.append((url_match, ""))

        seen_urls = set()

        for raw_url, link_text in raw_urls:
            try:
                if not re.search(r"cutshort\.(?:io|com)/job|jobId=|-(\d{4,})", raw_url, re.I):
                    continue
                if re.search(r"/login|/privacy|/settings|/profile|/auth", raw_url, re.I):
                    continue

                title = link_text
                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower():
                    if ":" in email_data.subject:
                        title = email_data.subject.split(":")[-1].strip()
                    elif "-" in raw_url:
                        slug_parts = urlparse(raw_url).path.split("/")[-1].split("-")
                        title_words = [p.capitalize() for p in slug_parts if p and not p.isdigit() and p not in ("job", "jobs")]
                        title = " ".join(title_words[:4]) if title_words else "Cutshort Position"
                    else:
                        title = "Cutshort Position"

                title = re.sub(r"\s+", " ", title).strip()
                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_cutshort_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                link = soup.find("a", href=raw_url)
                if link:
                    container = link.find_parent(["td", "tr", "div", "table", "li", "body", "html"]) or link.parent
                    if container:
                        container_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True))

                        comp_elem = (
                            container.select_one(".company")
                            or container.select_one(".company-name")
                            or container.select_one(".employer")
                        )
                        if comp_elem:
                            company = re.sub(r"\s+", " ", strip_html(comp_elem.get_text(strip=True)))

                        loc_elem = (
                            container.select_one(".location")
                            or container.select_one(".loc")
                            or container.select_one(".city")
                        )
                        if loc_elem:
                            location = re.sub(r"\s+", " ", strip_html(loc_elem.get_text(strip=True)))

                        snippet_elem = (
                            container.select_one(".snippet")
                            or container.select_one(".description")
                            or container.select_one(".summary")
                        )
                        if snippet_elem:
                            description = re.sub(r"\s+", " ", strip_html(snippet_elem.get_text(strip=True)))
                        elif container_text:
                            description = container_text[:300]

                        if (not company or not location):
                            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                            for l in lines:
                                if l != title and len(l) < 60:
                                    if not company:
                                        company = re.sub(r"\s+", " ", l)
                                    elif not location and l != company:
                                        location = re.sub(r"\s+", " ", l)
                                        break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="Cutshort Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual Cutshort job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


class HiristEmailParser:
    """
    Parser for Hirist job alert emails (HTML and plain-text).
    """

    @staticmethod
    def is_hirist_email(email_data: ParsedEmailData) -> bool:
        """
        Classifies whether an email is a Hirist job alert using multiple signals:
        - Sender domain/address (hirist.tech, hirist.com)
        - Subject patterns ('hirist', 'job alert', 'jobs digest')
        - Platform branding / body structure ('hirist.tech/j/', 'hirist.com/j/')
        """
        sender = (email_data.sender or "").lower()
        subject = (email_data.subject or "").lower()
        body = (email_data.plain_text or email_data.html_content or "").lower()

        if any(d in sender for d in ("hirist.tech", "hirist.com", "hirist")):
            return True
        if "hirist" in subject:
            return True
        if "hirist" in body:
            return True
        return False

    @staticmethod
    def parse(email_data: ParsedEmailData) -> List[Job]:
        """
        Parses a Hirist job alert email and returns a list of normalized Job models.
        """
        html = email_data.html_content or email_data.plain_text
        if not html:
            logger.debug("Hirist email message ID '%s' has empty body.", email_data.message_id)
            return []

        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []

        job_links = soup.find_all("a", href=re.compile(r"hirist\.(?:tech|com)/(?:j/|job/)"))

        raw_urls: List[Tuple[str, str]] = []
        if job_links:
            for link in job_links:
                raw_href = link.get("href", "").strip()
                t_text = re.sub(r"\s+", " ", strip_html(link.get_text(strip=True)))
                if raw_href:
                    raw_urls.append((raw_href, t_text))
        else:
            text_links = re.findall(r"https?://[^\s\"'>]*(?:hirist\.tech|hirist\.com)[^\s\"'>]*", html)
            for url_match in text_links:
                raw_urls.append((url_match, ""))

        seen_urls = set()

        for raw_url, link_text in raw_urls:
            try:
                if not re.search(r"hirist\.(?:tech|com)/(?:j/|job/)|jobId=|-(\d{4,})", raw_url, re.I):
                    continue
                if re.search(r"/login|/privacy|/settings|/seeker", raw_url, re.I):
                    continue

                title = link_text
                if not title or len(title) < 2 or "view job" in title.lower() or "apply" in title.lower():
                    if ":" in email_data.subject:
                        title = email_data.subject.split(":")[-1].strip()
                    elif "-" in raw_url:
                        slug_parts = urlparse(raw_url).path.split("/")[-1].replace(".html", "").split("-")
                        title_words = [p.capitalize() for p in slug_parts if p and not p.isdigit() and p not in ("j", "job")]
                        title = " ".join(title_words[:4]) if title_words else "Hirist Position"
                    else:
                        title = "Hirist Position"

                title = re.sub(r"\s+", " ", title).strip()
                if not title or not raw_url:
                    continue

                canonical_url, source_job_id = normalize_hirist_url(raw_url)
                if not canonical_url or canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

                company = ""
                location = ""
                description = title

                link = soup.find("a", href=raw_url)
                if link:
                    container = link.find_parent(["td", "tr", "div", "table", "li", "body", "html"]) or link.parent
                    if container:
                        container_text = re.sub(r"\s+", " ", container.get_text(" ", strip=True))

                        comp_elem = (
                            container.select_one(".company")
                            or container.select_one(".company-name")
                            or container.select_one(".employer")
                        )
                        if comp_elem:
                            company = re.sub(r"\s+", " ", strip_html(comp_elem.get_text(strip=True)))

                        loc_elem = (
                            container.select_one(".location")
                            or container.select_one(".loc")
                            or container.select_one(".city")
                        )
                        if loc_elem:
                            location = re.sub(r"\s+", " ", strip_html(loc_elem.get_text(strip=True)))

                        snippet_elem = (
                            container.select_one(".snippet")
                            or container.select_one(".description")
                            or container.select_one(".summary")
                        )
                        if snippet_elem:
                            description = re.sub(r"\s+", " ", strip_html(snippet_elem.get_text(strip=True)))
                        elif container_text:
                            description = container_text[:300]

                        if (not company or not location):
                            lines = [l.strip() for l in container.get_text("\n", strip=True).split("\n") if l.strip()]
                            for l in lines:
                                if l != title and len(l) < 60:
                                    if not company:
                                        company = re.sub(r"\s+", " ", l)
                                    elif not location and l != company:
                                        location = re.sub(r"\s+", " ", l)
                                        break

                fingerprint = generate_fingerprint(company=company, title=title, location=location)

                job = Job(
                    source="Hirist Email Alert",
                    source_job_id=source_job_id,
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    url=canonical_url,
                    created_at=email_data.received_at or None,
                    fingerprint=fingerprint,
                )
                jobs.append(job)

            except Exception as e:
                logger.warning("Error parsing individual Hirist job link in email ID '%s': %s", email_data.message_id, str(e))
                continue

        return jobs


def classify_email(email_data: ParsedEmailData) -> Optional[str]:
    """
    Classifies a Gmail message into one of the supported email alert source types:
    'cutshort_email', 'hirist_email', 'naukri_email', 'glassdoor_email',
    'unstop_email', 'foundit_email', 'linkedin_email', 'indeed_email'.
    Returns None if unclassified.
    """
    if CutshortEmailParser.is_cutshort_email(email_data):
        return "cutshort_email"
    if HiristEmailParser.is_hirist_email(email_data):
        return "hirist_email"

    sender = (email_data.sender or "").lower()
    subject = (email_data.subject or "").lower()
    body = (email_data.plain_text or email_data.html_content or "").lower()

    if "naukri.com" in sender or "naukri" in subject or "naukri.com" in body:
        return "naukri_email"
    if "glassdoor.com" in sender or "glassdoor" in subject or "glassdoor.com" in body:
        return "glassdoor_email"
    if any(d in sender for d in ("unstop.com", "d2c.in")) or "unstop" in subject or "unstop.com" in body:
        return "unstop_email"
    if any(d in sender for d in ("foundit.in", "monsterindia.com")) or "foundit" in subject or "foundit.in" in body:
        return "foundit_email"
    if "linkedin.com" in sender or "linkedin" in subject or "linkedin.com" in body:
        return "linkedin_email"
    if "indeed.com" in sender or "indeed" in subject or "indeed.com" in body:
        return "indeed_email"

    return None

