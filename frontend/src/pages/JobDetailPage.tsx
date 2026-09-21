import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import { JobDetailResponse } from '../types/api';
import { LoadingState, ErrorAlert } from '../components/States';
import { MatchCategoryBadge, ExperienceStatusBadge } from '../components/Badges';
import {
  ArrowLeft,
  Building2,
  MapPin,
  Calendar,
  ExternalLink,
  Sparkles,
  CheckCircle2,
  XCircle,
  Briefcase,
  UserCheck,
} from 'lucide-react';

export const JobDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<JobDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.getJobDetail(Number(id));
      setData(res);
    } catch (err: any) {
      setError(err.message || `Failed to load details for job #${id}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [id]);

  if (loading) return <LoadingState message="Fetching detailed job breakdown..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadDetail} />;
  if (!data) return null;

  const { job, match, candidate_profile } = data;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Navigation & Header */}
      <div className="flex items-center justify-between">
        <Link
          to="/jobs"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400 hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Jobs Listing
        </Link>
        <a
          href={job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold rounded-lg transition shadow-lg shadow-sky-600/20"
        >
          View Job / Apply Manually <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      {/* Main Job Card Banner */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-extrabold text-slate-100">{job.title}</h1>
              {match && <MatchCategoryBadge category={match.match_category} />}
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-300 flex-wrap">
              <span className="flex items-center gap-1 font-semibold text-slate-200">
                <Building2 className="w-4 h-4 text-slate-400" />
                {job.company || 'Company Unspecified'}
              </span>
              <span className="flex items-center gap-1 text-slate-300">
                <MapPin className="w-4 h-4 text-slate-400" />
                {job.location || 'Location Unspecified'}
              </span>
              <span className="flex items-center gap-1 text-slate-400">
                <Calendar className="w-4 h-4 text-slate-500" />
                Fetched: {new Date(job.fetched_at).toLocaleDateString()}
              </span>
            </div>

            {match && (
              <div className="flex items-center gap-2 flex-wrap pt-2">
                <ExperienceStatusBadge status={match.experience_match} />
                {match.role_family && (
                  <span className="px-2.5 py-1 rounded-md text-xs font-semibold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
                    Role Family: {match.role_family}
                  </span>
                )}
                {match.canonical_role && (
                  <span className="px-2.5 py-1 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
                    Canonical: {match.canonical_role}
                  </span>
                )}
              </div>
            )}
          </div>

          {match && (
            <div className="p-4 bg-slate-800/80 border border-slate-700/80 rounded-xl text-center shrink-0 min-w-[140px]">
              <p className="text-3xl font-black text-sky-400">{match.final_score.toFixed(1)}%</p>
              <p className="text-xs text-slate-400 font-semibold uppercase mt-1">Overall Match</p>
            </div>
          )}
        </div>

        {/* Source metadata */}
        <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <span>Source: <strong className="text-slate-200">{job.source}</strong></span>
          <span>Source ID: <code className="text-slate-300">{job.source_job_id}</code></span>
        </div>
      </div>

      {/* Multi-Dimensional Match Breakdown */}
      {match && (
        <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
          <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-sky-400" />
            Matching Score Breakdown
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="p-3 bg-slate-800/50 border border-slate-800 rounded-xl text-center">
              <p className="text-xs text-slate-400 font-medium">Role Similarity</p>
              <p className="text-lg font-bold text-sky-400">{match.role_score.toFixed(1)}%</p>
            </div>
            <div className="p-3 bg-slate-800/50 border border-slate-800 rounded-xl text-center">
              <p className="text-xs text-slate-400 font-medium">Experience Score</p>
              <p className="text-lg font-bold text-indigo-400">{match.experience_score.toFixed(1)}%</p>
            </div>
            <div className="p-3 bg-slate-800/50 border border-slate-800 rounded-xl text-center">
              <p className="text-xs text-slate-400 font-medium">Education Match</p>
              <p className="text-lg font-bold text-emerald-400">{match.education_score.toFixed(1)}%</p>
            </div>
            <div className="p-3 bg-slate-800/50 border border-slate-800 rounded-xl text-center">
              <p className="text-xs text-slate-400 font-medium">Location Match</p>
              <p className="text-lg font-bold text-amber-400">{match.location_score.toFixed(1)}%</p>
            </div>
            <div className="p-3 bg-slate-800/50 border border-slate-800 rounded-xl text-center">
              <p className="text-xs text-slate-400 font-medium">Seniority Score</p>
              <p className="text-lg font-bold text-purple-400">{match.seniority_score.toFixed(1)}%</p>
            </div>
          </div>
        </div>
      )}

      {/* Skills Analysis */}
      {match && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
            <h4 className="text-sm font-bold text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4" />
              Matched Skills ({match.matched_skills.length})
            </h4>
            <div className="flex flex-wrap gap-2">
              {match.matched_skills.length > 0 ? (
                match.matched_skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
                  >
                    {skill}
                  </span>
                ))
              ) : (
                <p className="text-xs text-slate-500 italic">No specific skills matched.</p>
              )}
            </div>
          </div>

          <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
            <h4 className="text-sm font-bold text-amber-400 flex items-center gap-2">
              <XCircle className="w-4 h-4" />
              Skill Gaps ({match.skill_gaps.length})
            </h4>
            <div className="flex flex-wrap gap-2">
              {match.skill_gaps.length > 0 ? (
                match.skill_gaps.map((skill) => (
                  <span
                    key={skill}
                    className="px-2.5 py-1 rounded-md text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20"
                  >
                    {skill}
                  </span>
                ))
              ) : (
                <p className="text-xs text-slate-500 italic">No skill gaps identified.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Candidate Profile Comparison */}
      <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
        <h4 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-sky-400" />
          Candidate Experience Comparison
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-slate-800/40 rounded-xl">
            <span className="text-slate-400">Candidate Status:</span>
            <p className="font-semibold text-slate-200 mt-0.5">{candidate_profile.status}</p>
          </div>
          <div className="p-3 bg-slate-800/40 rounded-xl">
            <span className="text-slate-400">Experience Level:</span>
            <p className="font-semibold text-slate-200 mt-0.5">{candidate_profile.experience_level} ({candidate_profile.years_experience} yrs)</p>
          </div>
          <div className="p-3 bg-slate-800/40 rounded-xl">
            <span className="text-slate-400">Evaluated Experience Status:</span>
            <p className="font-semibold text-amber-400 mt-0.5">{match?.experience_match || 'UNKNOWN'}</p>
          </div>
        </div>
      </div>

      {/* Job Description Text */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
        <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-slate-400" />
          Full Job Description
        </h3>
        <div className="prose prose-invert max-w-none text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
          {job.description || 'No detailed description text available.'}
        </div>
      </div>
    </div>
  );
};
