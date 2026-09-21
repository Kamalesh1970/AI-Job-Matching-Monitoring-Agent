import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { DashboardData } from '../types/api';
import { LoadingState, ErrorAlert } from '../components/States';
import { MatchCategoryBadge, ExperienceStatusBadge } from '../components/Badges';
import {
  Briefcase,
  Sparkles,
  Flame,
  Star,
  AlertTriangle,
  Building2,
  ExternalLink,
  Clock,
  ArrowRight,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getDashboard();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  if (loading) return <LoadingState message="Loading dashboard metrics..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadDashboard} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Metric Cards Banner */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <Briefcase className="w-4 h-4 text-sky-400" />
            <span className="text-xs font-semibold uppercase">Total Jobs</span>
          </div>
          <p className="text-2xl font-bold text-slate-100">{data.total_jobs}</p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <Sparkles className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-semibold uppercase">AI Jobs</span>
          </div>
          <p className="text-2xl font-bold text-indigo-400">{data.ai_relevant_jobs}</p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <Flame className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-semibold uppercase">Strong Matches</span>
          </div>
          <p className="text-2xl font-bold text-emerald-400">{data.strong_matches}</p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <Star className="w-4 h-4 text-amber-400" />
            <span className="text-xs font-semibold uppercase">Potential Matches</span>
          </div>
          <p className="text-2xl font-bold text-amber-400">{data.potential_matches}</p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <Briefcase className="w-4 h-4 text-sky-400" />
            <span className="text-xs font-semibold uppercase">Low Matches</span>
          </div>
          <p className="text-2xl font-bold text-sky-400">{data.low_matches}</p>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="flex items-center gap-2 text-slate-400 mb-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            <span className="text-xs font-semibold uppercase font-sans">Experience Gaps</span>
          </div>
          <p className="text-2xl font-bold text-amber-500">{data.experience_gaps}</p>
        </div>
      </div>

      {/* Main Grid Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Matching Jobs List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-sky-400" />
              Top AI Career Matches
            </h3>
            <Link
              to="/jobs"
              className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
            >
              View All Jobs <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-3">
            {data.top_matching_jobs.map(({ job, match }) => {
              if (!job) return null;
              return (
                <div
                  key={job.id}
                  className="p-4 bg-slate-900/90 border border-slate-800 hover:border-slate-700 rounded-xl transition flex flex-col md:flex-row md:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Link
                        to={`/jobs/${job.id}`}
                        className="text-base font-bold text-slate-100 hover:text-sky-400 transition"
                      >
                        {job.title}
                      </Link>
                      {match && <MatchCategoryBadge category={match.match_category} />}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-slate-400">
                      <span className="flex items-center gap-1 font-medium text-slate-300">
                        <Building2 className="w-3.5 h-3.5 text-slate-500" />
                        {job.company || 'Not Specified'}
                      </span>
                      <span>{job.location || 'Location Unspecified'}</span>
                      <span className="text-slate-500">• {job.source}</span>
                    </div>

                    {match && (
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
                        <ExperienceStatusBadge status={match.experience_match} />
                        {match.role_family && (
                          <span className="px-2 py-0.5 rounded text-[11px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                            {match.role_family}
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    {match && (
                      <div className="text-right">
                        <p className="text-xl font-extrabold text-sky-400">{match.final_score.toFixed(1)}%</p>
                        <p className="text-[10px] text-slate-400 font-medium">Match Score</p>
                      </div>
                    )}

                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition"
                      title="View Original Listing"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Sidebar: Distribution & Last Execution */}
        <div className="space-y-6">
          {/* Source Distribution */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
            <h4 className="text-sm font-bold text-slate-200 uppercase tracking-wider text-xs">
              Job Sources Distribution
            </h4>
            <div className="space-y-2">
              {Object.entries(data.source_distribution).map(([source, count]) => {
                const pct = Math.round((count / data.total_jobs) * 100) || 0;
                return (
                  <div key={source} className="space-y-1">
                    <div className="flex justify-between text-xs font-medium">
                      <span className="text-slate-300">{source}</span>
                      <span className="text-slate-400">{count} ({pct}%)</span>
                    </div>
                    <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-sky-500 h-full rounded-full"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Last Pipeline Status */}
          {data.last_pipeline_run && (
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1 font-semibold uppercase">
                  <Clock className="w-3.5 h-3.5 text-emerald-400" />
                  Last Monitoring Cycle
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
                  {data.last_pipeline_run.status}
                </span>
              </div>
              <p className="text-xs text-slate-300">
                Fetched <span className="font-bold text-white">{data.last_pipeline_run.jobs_fetched}</span> jobs (
                <span className="text-emerald-400 font-bold">{data.last_pipeline_run.new_jobs} new</span>)
              </p>
              <p className="text-[11px] text-slate-400">
                Finished: {data.last_pipeline_run.finished_at ? new Date(data.last_pipeline_run.finished_at).toLocaleString() : 'N/A'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
