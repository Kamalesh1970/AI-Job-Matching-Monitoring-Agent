import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { CompaniesResponse, CompanyInfo } from '../types/api';
import { LoadingState, ErrorAlert, EmptyState } from '../components/States';
import { Building2, MapPin, Briefcase, ExternalLink, Globe } from 'lucide-react';

export const CompaniesPage: React.FC = () => {
  const [data, setData] = useState<CompaniesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const loadCompanies = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getCompanies();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load companies listing');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompanies();
  }, []);

  if (loading) return <LoadingState message="Fetching company records from backend..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadCompanies} />;
  if (!data || data.companies.length === 0) {
    return (
      <EmptyState
        title="No Companies Discovered"
        description="Companies associated with ingested job postings will appear here."
      />
    );
  }

  const filteredCompanies = data.companies.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()) ||
    c.location.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-sky-400" />
            Discovered Employers ({data.total})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Companies represented across stored job opportunities and email alerts.
          </p>
        </div>

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter companies..."
          className="bg-slate-900 border border-slate-800 rounded-lg px-3.5 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 w-full md:w-64"
        />
      </div>

      {/* Companies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredCompanies.map((company) => (
          <div
            key={company.name}
            className="p-5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl transition space-y-3 flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-base font-bold text-slate-100 line-clamp-1">{company.name}</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 shrink-0">
                  {company.associated_jobs_count} Job{company.associated_jobs_count > 1 ? 's' : ''}
                </span>
              </div>

              <p className="text-xs text-slate-400 flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-slate-500" />
                {company.location || 'Multiple Locations'}
              </p>

              <p className="text-[11px] text-slate-400 line-clamp-1">
                Latest Role: <strong className="text-slate-300">{company.latest_job_title}</strong>
              </p>
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
              <span className="flex items-center gap-1 text-[11px]">
                Sources: {company.sources.join(', ')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
