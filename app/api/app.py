"""
FastAPI application exposing read-only and state update APIs for the Career Intelligence Web UI.
Consumes existing database models, matching logic, and system configurations.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import load_config, Config
from app.db.database import (
    get_connection,
    get_all_jobs,
    get_jobs_map,
    get_recent_jobs,
    get_stored_matches,
    get_last_pipeline_run,
    get_tailored_resume_by_id,
    get_tailored_resumes_by_job,
    update_tailored_resume_status,
)
from app.db.models import Job, MatchResult
from app.services.career_taxonomy import AI_ROLE_TAXONOMY
from app.services.skill_extractor import extract_skills


def create_app() -> FastAPI:
    """Factory function creating the FastAPI application."""
    app = FastAPI(
        title="AI Career Intelligence API",
        description="FastAPI backend for AI Job-Matching & Monitoring Agent Web UI",
        version="1.0.0",
    )

    # Enable CORS for frontend integration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db():
        config = load_config()
        return get_connection(config.db_path)

    # ----------------------------------------------------
    # Dashboard API
    # ----------------------------------------------------
    @app.get("/api/dashboard")
    def get_dashboard_data():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            stored_jobs = get_all_jobs(conn)
            stored_matches = get_stored_matches(conn)
            last_run = get_last_pipeline_run(conn)

            total_jobs = len(stored_jobs)
            ai_relevant_jobs = sum(1 for m in stored_matches if m.match_category != "NOT_RELEVANT")
            strong_matches = sum(1 for m in stored_matches if m.match_category == "STRONG_MATCH")
            potential_matches = sum(1 for m in stored_matches if m.match_category == "POTENTIAL_MATCH")
            low_matches = sum(1 for m in stored_matches if m.match_category == "LOW_MATCH")
            experience_gaps = sum(
                1 for m in stored_matches if m.experience_match in ("EXPERIENCE_GAP", "NOT_ELIGIBLE")
            )

            # Distribution calculations
            source_dist: Dict[str, int] = {}
            for j in stored_jobs:
                source_dist[j.source] = source_dist.get(j.source, 0) + 1

            match_cat_dist: Dict[str, int] = {}
            exp_match_dist: Dict[str, int] = {}
            for m in stored_matches:
                cat = m.match_category or "NOT_RELEVANT"
                match_cat_dist[cat] = match_cat_dist.get(cat, 0) + 1
                exp_status = m.experience_match or "UNKNOWN"
                exp_match_dist[exp_status] = exp_match_dist.get(exp_status, 0) + 1

            # Top matching jobs
            top_matches = sorted(stored_matches, key=lambda x: x.final_score, reverse=True)[:10]
            jobs_map = {j.id: j for j in stored_jobs if j.id is not None}
            
            top_matching_jobs = []
            for m in top_matches:
                j = jobs_map.get(m.job_id)
                top_matching_jobs.append({
                    "match": m.to_dict(),
                    "job": j.to_dict() if j else None,
                })

            # Recent jobs
            recent_jobs_raw = get_recent_jobs(conn, limit=10)
            recent_jobs = [j.to_dict() for j in recent_jobs_raw]

            return {
                "total_jobs": total_jobs,
                "ai_relevant_jobs": ai_relevant_jobs,
                "strong_matches": strong_matches,
                "potential_matches": potential_matches,
                "low_matches": low_matches,
                "experience_gaps": experience_gaps,
                "source_distribution": source_dist,
                "match_category_distribution": match_cat_dist,
                "experience_status_distribution": exp_match_dist,
                "top_matching_jobs": top_matching_jobs,
                "recent_jobs": recent_jobs,
                "last_pipeline_run": last_run,
            }
        finally:
            conn.close()

    # ----------------------------------------------------
    # Jobs API
    # ----------------------------------------------------
    @app.get("/api/jobs")
    def get_jobs_list(
        search: Optional[str] = None,
        role_family: Optional[str] = None,
        match_category: Optional[str] = None,
        experience_match: Optional[str] = None,
        location: Optional[str] = None,
        source: Optional[str] = None,
        company: Optional[str] = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            stored_jobs = get_all_jobs(conn)
            stored_matches = get_stored_matches(conn)
            matches_map = {m.job_id: m for m in stored_matches if m.job_id is not None}

            combined_results = []
            for job in stored_jobs:
                match = matches_map.get(job.id)
                combined_results.append({
                    "job": job.to_dict(),
                    "match": match.to_dict() if match else None,
                })

            # Apply filters
            filtered = []
            for item in combined_results:
                j = item["job"]
                m = item["match"]

                if search:
                    s_lower = search.lower()
                    title_match = s_lower in (j.get("title") or "").lower()
                    company_match = s_lower in (j.get("company") or "").lower()
                    desc_match = s_lower in (j.get("description") or "").lower()
                    if not (title_match or company_match or desc_match):
                        continue

                if role_family:
                    if not m or m.get("role_family") != role_family:
                        continue

                if match_category:
                    if not m or m.get("match_category") != match_category:
                        continue

                if experience_match:
                    if not m or m.get("experience_match") != experience_match:
                        continue

                if location:
                    loc_val = (j.get("location") or "").lower()
                    if location.lower() not in loc_val:
                        continue

                if source:
                    if j.get("source") != source:
                        continue

                if company:
                    comp_val = (j.get("company") or "").lower()
                    if company.lower() not in comp_val:
                        continue

                filtered.append(item)

            total_count = len(filtered)
            paginated = filtered[offset : offset + limit]

            # Facets for filter dropdowns
            all_sources = sorted(list({j.source for j in stored_jobs if j.source}))
            all_role_families = sorted(list({m.role_family for m in stored_matches if m.role_family}))
            all_companies = sorted(list({j.company for j in stored_jobs if j.company}))[:50]

            return {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "jobs": paginated,
                "facets": {
                    "sources": all_sources,
                    "role_families": all_role_families,
                    "companies": all_companies,
                    "match_categories": ["STRONG_MATCH", "POTENTIAL_MATCH", "LOW_MATCH", "NOT_RELEVANT"],
                    "experience_matches": ["MATCH", "POSSIBLE_MATCH", "EXPERIENCE_GAP", "NOT_ELIGIBLE"],
                },
            }
        finally:
            conn.close()

    @app.get("/api/jobs/{job_id}")
    def get_job_detail(job_id: int):
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            jobs_map = get_jobs_map(conn)
            job = jobs_map.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail=f"Job #{job_id} not found")

            stored_matches = get_stored_matches(conn)
            match = next((m for m in stored_matches if m.job_id == job_id), None)
            tailored_drafts = get_tailored_resumes_by_job(conn, job_id)

            return {
                "job": job.to_dict(),
                "match": match.to_dict() if match else None,
                "tailored_drafts": tailored_drafts,
                "candidate_profile": {
                    "experience_level": config.candidate_experience_level,
                    "years_experience": config.candidate_years_experience,
                    "status": config.candidate_status,
                },
            }
        finally:
            conn.close()

    # ----------------------------------------------------
    # Companies API
    # ----------------------------------------------------
    @app.get("/api/companies")
    def get_companies_list():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            stored_jobs = get_all_jobs(conn)
            companies_map: Dict[str, Dict[str, Any]] = {}

            for job in stored_jobs:
                c_name = job.company or "Not Specified"
                if c_name not in companies_map:
                    companies_map[c_name] = {
                        "name": c_name,
                        "location": job.location or "Various",
                        "associated_jobs_count": 0,
                        "sources": set(),
                        "latest_job_title": job.title,
                        "latest_job_date": job.fetched_at,
                    }
                comp = companies_map[c_name]
                comp["associated_jobs_count"] += 1
                if job.source:
                    comp["sources"].add(job.source)

            results = []
            for c_name, data in companies_map.items():
                results.append({
                    "name": data["name"],
                    "location": data["location"],
                    "associated_jobs_count": data["associated_jobs_count"],
                    "sources": sorted(list(data["sources"])),
                    "latest_job_title": data["latest_job_title"],
                    "latest_job_date": data["latest_job_date"],
                })

            results.sort(key=lambda x: x["associated_jobs_count"], reverse=True)
            return {"companies": results, "total": len(results)}
        finally:
            conn.close()

    # ----------------------------------------------------
    # Applications API
    # ----------------------------------------------------
    @app.get("/api/applications")
    def get_applications_list():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tr.*, j.title AS job_title, j.company AS job_company, j.source AS job_source, j.url AS job_url
                FROM tailored_resumes tr
                JOIN jobs j ON tr.job_id = j.id
                ORDER BY tr.created_at DESC
                """
            )
            rows = cursor.fetchall()
            applications = []
            for r in rows:
                d = dict(r)
                d["resume_content"] = json.loads(d["resume_content"]) if d["resume_content"] else None
                d["changes"] = json.loads(d["changes"]) if d["changes"] else []
                d["warnings"] = json.loads(d["warnings"]) if d["warnings"] else []
                d["validation_result"] = json.loads(d["validation_result"]) if d["validation_result"] else None
                applications.append(d)

            return {"applications": applications, "total": len(applications)}
        finally:
            conn.close()

    # ----------------------------------------------------
    # Gmail Intelligence API
    # ----------------------------------------------------
    @app.get("/api/gmail")
    def get_gmail_intelligence():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM jobs 
                WHERE source LIKE '%Gmail%' OR source IN ('LinkedIn', 'Indeed', 'Naukri', 'Glassdoor', 'Unstop', 'foundit', 'Cutshort', 'Hirist', 'Wellfound')
                ORDER BY fetched_at DESC
                """
            )
            rows = cursor.fetchall()
            gmail_events = []
            for row in rows:
                gmail_events.append({
                    "id": row["id"],
                    "sender": f"alerts@{row['source'].lower()}.com",
                    "company": row["company"] or "Unknown",
                    "subject": f"Job Alert: {row['title']}",
                    "category": "JOB_ALERT",
                    "received_date": row["fetched_at"] or row["created_at"],
                    "extracted_role": row["title"],
                    "source": row["source"],
                    "action_required": "Review Match & Apply",
                    "url": row["url"],
                })

            categories = [
                "JOB_ALERT", "APPLICATION_RECEIVED", "APPLICATION_UPDATE", "INTERVIEW_INVITATION",
                "INTERVIEW_RESCHEDULE", "ASSESSMENT", "OFFER", "REJECTION", "FORM_ACTION",
                "DOCUMENT_REQUEST", "JOINING_INFORMATION", "RECRUITER_MESSAGE", "OTHER_CAREER"
            ]

            return {
                "events": gmail_events,
                "total": len(gmail_events),
                "categories": categories,
                "gmail_enabled": config.gmail_enabled,
            }
        finally:
            conn.close()

    # ----------------------------------------------------
    # Interviews API
    # ----------------------------------------------------
    @app.get("/api/interviews")
    def get_interviews():
        # Backend does not yet persist interview invites, returning clear empty state
        return {"interviews": [], "total": 0, "status": "NO_INTERVIEWS_SCHEDULED"}

    # ----------------------------------------------------
    # Skills API
    # ----------------------------------------------------
    @app.get("/api/skills")
    def get_skills_analytics():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            stored_jobs = get_all_jobs(conn)
            stored_matches = get_stored_matches(conn)

            requested_skills_freq: Dict[str, int] = {}
            missing_skills_freq: Dict[str, int] = {}
            matched_skills_freq: Dict[str, int] = {}

            for job in stored_jobs:
                job_text = f"{job.title} {job.description}"
                extracted = extract_skills(job_text)
                for s in extracted:
                    requested_skills_freq[s] = requested_skills_freq.get(s, 0) + 1

            for m in stored_matches:
                for s in m.matched_skills:
                    matched_skills_freq[s] = matched_skills_freq.get(s, 0) + 1
                for s in (m.skill_gaps or m.missing_skills):
                    missing_skills_freq[s] = missing_skills_freq.get(s, 0) + 1

            top_requested = sorted(
                [{"skill": k, "count": v} for k, v in requested_skills_freq.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:20]

            top_missing = sorted(
                [{"skill": k, "count": v} for k, v in missing_skills_freq.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:20]

            top_matched = sorted(
                [{"skill": k, "count": v} for k, v in matched_skills_freq.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:20]

            candidate_skills = sorted(list(matched_skills_freq.keys()))

            return {
                "candidate_skills": candidate_skills,
                "frequently_requested_skills": top_requested,
                "top_missing_skills": top_missing,
                "top_matched_skills": top_matched,
            }
        finally:
            conn.close()

    # ----------------------------------------------------
    # Resume & Tailoring API
    # ----------------------------------------------------
    @app.get("/api/resumes")
    def get_resumes_list():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tr.*, j.title AS job_title, j.company AS job_company
                FROM tailored_resumes tr
                LEFT JOIN jobs j ON tr.job_id = j.id
                ORDER BY tr.created_at DESC
                """
            )
            rows = cursor.fetchall()
            drafts = []
            for r in rows:
                d = dict(r)
                d["resume_content"] = json.loads(d["resume_content"]) if d["resume_content"] else None
                d["changes"] = json.loads(d["changes"]) if d["changes"] else []
                d["warnings"] = json.loads(d["warnings"]) if d["warnings"] else []
                d["validation_result"] = json.loads(d["validation_result"]) if d["validation_result"] else None
                drafts.append(d)

            # Load base resume info
            base_resume_text = ""
            try:
                with open(config.resume_path, "r", encoding="utf-8") as f:
                    base_resume_text = f.read()
            except Exception:
                base_resume_text = "Base resume content unavailable."

            return {
                "base_resume_path": config.resume_path,
                "base_resume_snippet": base_resume_text[:500],
                "tailored_drafts": drafts,
                "total_drafts": len(drafts),
            }
        finally:
            conn.close()

    @app.get("/api/resumes/{draft_id}")
    def get_resume_detail(draft_id: int):
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            draft = get_tailored_resume_by_id(conn, draft_id)
            if not draft:
                raise HTTPException(status_code=404, detail=f"Resume draft #{draft_id} not found")
            return draft
        finally:
            conn.close()

    class StatusUpdatePayload(BaseModel):
        status: str

    @app.post("/api/resumes/{draft_id}/status")
    def update_resume_status(draft_id: int, payload: StatusUpdatePayload):
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            if payload.status not in ("APPROVED", "REJECTED", "DRAFT", "VALIDATED"):
                raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")
            
            success = update_tailored_resume_status(conn, draft_id, payload.status)
            if not success:
                raise HTTPException(status_code=404, detail=f"Draft #{draft_id} not found")
            return {"status": "SUCCESS", "draft_id": draft_id, "new_status": payload.status}
        finally:
            conn.close()

    # ----------------------------------------------------
    # Analytics API
    # ----------------------------------------------------
    @app.get("/api/analytics")
    def get_analytics_data():
        config = load_config()
        conn = get_connection(config.db_path)
        try:
            stored_jobs = get_all_jobs(conn)
            stored_matches = get_stored_matches(conn)

            match_cat_counts: Dict[str, int] = {}
            exp_status_counts: Dict[str, int] = {}
            source_counts: Dict[str, int] = {}
            role_family_counts: Dict[str, int] = {}
            jobs_by_date: Dict[str, int] = {}

            for m in stored_matches:
                cat = m.match_category or "NOT_RELEVANT"
                match_cat_counts[cat] = match_cat_counts.get(cat, 0) + 1

                exp = m.experience_match or "UNKNOWN"
                exp_status_counts[exp] = exp_status_counts.get(exp, 0) + 1

                rf = m.role_family or "General AI/ML"
                if cat != "NOT_RELEVANT":
                    role_family_counts[rf] = role_family_counts.get(rf, 0) + 1

            for j in stored_jobs:
                src = j.source or "Unknown"
                source_counts[src] = source_counts.get(src, 0) + 1
                
                date_str = (j.fetched_at or j.created_at or "")[:10]
                if date_str:
                    jobs_by_date[date_str] = jobs_by_date.get(date_str, 0) + 1

            match_cat_chart = [{"name": k, "value": v} for k, v in match_cat_counts.items()]
            exp_status_chart = [{"name": k, "value": v} for k, v in exp_status_counts.items()]
            source_chart = [{"name": k, "value": v} for k, v in source_counts.items()]
            role_family_chart = [{"name": k, "value": v} for k, v in role_family_counts.items()]
            
            jobs_time_chart = sorted(
                [{"date": k, "jobs": v} for k, v in jobs_by_date.items()],
                key=lambda x: x["date"],
            )

            return {
                "match_category_distribution": match_cat_chart,
                "experience_status_distribution": exp_status_chart,
                "jobs_by_source": source_chart,
                "jobs_by_role_family": role_family_chart,
                "jobs_over_time": jobs_time_chart,
            }
        finally:
            conn.close()

    # ----------------------------------------------------
    # Settings API
    # ----------------------------------------------------
    @app.get("/api/settings")
    def get_settings():
        config = load_config()
        # Expose safe system parameters without exposing secrets
        return {
            "candidate_status": config.candidate_status,
            "candidate_experience_level": config.candidate_experience_level,
            "candidate_years_experience": config.candidate_years_experience,
            "min_match_score": config.min_match_score,
            "preferred_locations": config.preferred_locations,
            "keywords": config.keywords,
            "enabled_sources": [
                "Adzuna", "Internshala", "LinkedIn", "Indeed", "Naukri",
                "Glassdoor", "Unstop", "foundit", "Cutshort", "Hirist", "Wellfound"
            ],
            "telegram_enabled": config.telegram_enabled,
            "gmail_enabled": config.gmail_enabled,
            "scheduler_enabled": config.scheduler_enabled,
            "scheduler_interval_minutes": config.scheduler_interval_minutes,
            "db_path": config.db_path,
        }

    return app


app = create_app()
