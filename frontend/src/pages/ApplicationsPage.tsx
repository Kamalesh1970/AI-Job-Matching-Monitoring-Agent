import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ApplicationsResponse } from '../types/api';
import { LoadingState, ErrorAlert, EmptyState } from '../components/States';
import { FileCheck2, Building2, Calendar, ExternalLink, ShieldCheck, CheckCircle, XCircle } from 'lucide-react';

export const ApplicationsPage: React.FC = () => {
  const [data, setData] = useState<ApplicationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadApplications = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getApplications();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch application records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApplications();
  }, []);

  if (loading) return <LoadingState message="Fetching application pipeline records..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadApplications} />;
  if (!data || data.applications.length === 0) {
    return (
      <EmptyState
        title="No Application Records Found"
        description="Tailored resume drafts and manual application logs will appear here."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <FileCheck2 className="w-5 h-5 text-sky-400" />
            Application Tracker ({data.total})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Manual application preparation, resume tailoring drafts, and review statuses.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {data.applications.map((app) => (
          <div
            key={app.id}
            className="p-5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl transition flex flex-col md:flex-row md:items-center justify-between gap-4"
          >
            <div className="space-y-1.5 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-slate-100">{app.job_title}</h3>
                <span
                  className={`px-2.5 py-0.5 rounded text-xs font-bold border ${
                    app.status === 'APPROVED'
                      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                      : app.status === 'REJECTED'
                      ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                      : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                  }`}
                >
                  {app.status}
                </span>
              </div>

              <div className="flex items-center gap-4 text-xs text-slate-400">
                <span className="flex items-center gap-1 text-slate-300 font-medium">
                  <Building2 className="w-3.5 h-3.5 text-slate-500" />
                  {app.job_company}
                </span>
                <span>Source: {app.job_source}</span>
                <span>Match Score: <strong className="text-sky-400">{app.match_score.toFixed(1)}%</strong></span>
              </div>

              <p className="text-[11px] text-slate-400">
                Created: {new Date(app.created_at).toLocaleString()}
                {app.reviewed_at && ` • Reviewed: ${new Date(app.reviewed_at).toLocaleString()}`}
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <a
                href={app.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg transition"
              >
                Apply Manually <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
