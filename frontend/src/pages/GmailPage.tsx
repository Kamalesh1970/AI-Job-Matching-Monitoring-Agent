import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { GmailIntelligenceResponse } from '../types/api';
import { LoadingState, ErrorAlert, EmptyState } from '../components/States';
import { Mail, Building2, Calendar, ExternalLink, ShieldCheck, Tag, AlertCircle } from 'lucide-react';

export const GmailPage: React.FC = () => {
  const [data, setData] = useState<GmailIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState('');

  const loadGmailEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getGmailIntelligence();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch Gmail intelligence events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGmailEvents();
  }, []);

  if (loading) return <LoadingState message="Fetching Gmail career intelligence events..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadGmailEvents} />;
  if (!data || data.events.length === 0) {
    return (
      <EmptyState
        title="No Career Email Events"
        description="Ingested Gmail job alert emails and career notifications will appear here."
      />
    );
  }

  const filteredEvents = categoryFilter
    ? data.events.filter((e) => e.category === categoryFilter)
    : data.events;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Mail className="w-5 h-5 text-sky-400" />
            Gmail Career Intelligence ({data.total})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated categorization of career emails, job alerts, and recruitment events.
          </p>
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
        >
          <option value="">All Categories ({data.categories.length})</option>
          {data.categories.map((cat) => (
            <option key={cat} value={cat}>
              {cat}
            </option>
          ))}
        </select>
      </div>

      {/* Events List */}
      <div className="space-y-3">
        {filteredEvents.map((evt) => (
          <div
            key={evt.id}
            className="p-5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl transition flex flex-col md:flex-row md:items-center justify-between gap-4"
          >
            <div className="space-y-2 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-0.5 rounded text-xs font-bold bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex items-center gap-1">
                  <Tag className="w-3 h-3" />
                  {evt.category}
                </span>
                <h3 className="text-sm font-bold text-slate-100">{evt.subject}</h3>
              </div>

              <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                <span className="flex items-center gap-1 text-slate-300 font-medium">
                  <Building2 className="w-3.5 h-3.5 text-slate-500" />
                  {evt.company}
                </span>
                <span>Sender: <code className="text-slate-300">{evt.sender}</code></span>
                <span className="flex items-center gap-1 text-slate-400">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  {new Date(evt.received_date).toLocaleDateString()}
                </span>
              </div>

              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="text-slate-500">Action:</span>
                <span className="font-semibold text-amber-400">{evt.action_required}</span>
              </div>
            </div>

            {evt.url && (
              <a
                href={evt.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition shrink-0"
              >
                View Job <ExternalLink className="w-3.5 h-3.5" />
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
