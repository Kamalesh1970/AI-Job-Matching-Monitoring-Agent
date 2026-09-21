import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { JobsResponse } from '../types/api';
import { LoadingState, ErrorAlert, EmptyState } from '../components/States';
import { MatchCategoryBadge, ExperienceStatusBadge } from '../components/Badges';
import {
  Search,
  Filter,
  Building2,
  MapPin,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';

export const JobsPage: React.FC = () => {
  const [data, setData] = useState<JobsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter States
  const [search, setSearch] = useState('');
  const [roleFamily, setRoleFamily] = useState('');
  const [matchCategory, setMatchCategory] = useState('');
  const [experienceMatch, setExperienceMatch] = useState('');
  const [source, setSource] = useState('');
  const [location, setLocation] = useState('');
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const loadJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getJobs({
        search,
        role_family: roleFamily,
        match_category: matchCategory,
        experience_match: experienceMatch,
        source,
        location,
        limit,
        offset,
      });
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch jobs listing');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, [roleFamily, matchCategory, experienceMatch, source, location, offset]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOffset(0);
    loadJobs();
  };

  const clearFilters = () => {
    setSearch('');
    setRoleFamily('');
    setMatchCategory('');
    setExperienceMatch('');
    setSource('');
    setLocation('');
    setOffset(0);
  };

  return (
    <div className="space-y-6">
      {/* Search & Filter Header */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by job title, company name, or keywords..."
              className="w-full bg-slate-800/80 border border-slate-700/80 rounded-lg pl-10 pr-4 py-2 text-sm text-slate-200 placeholder-slate-400 focus:outline-none focus:border-sky-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm rounded-lg transition shrink-0"
          >
            Search
          </button>
        </form>

        {/* Filter Dropdowns */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 pt-2 border-t border-slate-800/80">
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">Match Category</label>
            <select
              value={matchCategory}
              onChange={(e) => {
                setMatchCategory(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All Categories</option>
              <option value="STRONG_MATCH">STRONG_MATCH</option>
              <option value="POTENTIAL_MATCH">POTENTIAL_MATCH</option>
              <option value="LOW_MATCH">LOW_MATCH</option>
              <option value="NOT_RELEVANT">NOT_RELEVANT</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">Experience Status</label>
            <select
              value={experienceMatch}
              onChange={(e) => {
                setExperienceMatch(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All Experience</option>
              <option value="MATCH">MATCH (Fresher)</option>
              <option value="POSSIBLE_MATCH">POSSIBLE_MATCH</option>
              <option value="EXPERIENCE_GAP">EXPERIENCE_GAP</option>
              <option value="NOT_ELIGIBLE">NOT_ELIGIBLE</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">Role Family</label>
            <select
              value={roleFamily}
              onChange={(e) => {
                setRoleFamily(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All Role Families</option>
              {data?.facets.role_families.map((rf) => (
                <option key={rf} value={rf}>
                  {rf}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-400 uppercase mb-1">Source</label>
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setOffset(0);
              }}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none"
            >
              <option value="">All Sources</option>
              {data?.facets.sources.map((src) => (
                <option key={src} value={src}>
                  {src}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={clearFilters}
              className="w-full py-1.5 px-3 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-xs font-medium rounded-lg transition"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      {loading ? (
        <LoadingState message="Fetching filtered AI jobs..." />
      ) : error ? (
        <ErrorAlert message={error} onRetry={loadJobs} />
      ) : !data || data.jobs.length === 0 ? (
        <EmptyState title="No Jobs Found" description="Try adjusting your filter choices or search query." onRetry={clearFilters} />
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-medium px-1">
            <span>
              Showing <strong className="text-slate-200">{offset + 1}</strong> -{' '}
              <strong className="text-slate-200">{Math.min(offset + limit, data.total)}</strong> of{' '}
              <strong className="text-sky-400">{data.total}</strong> discovered jobs
            </span>
          </div>

          <div className="space-y-3">
            {data.jobs.map(({ job, match }) => (
              <div
                key={job.id}
                className="p-4 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl transition flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Link
                      to={`/jobs/${job.id}`}
                      className="text-base font-bold text-slate-100 hover:text-sky-400 transition"
                    >
                      {job.title}
                    </Link>
                    {match && <MatchCategoryBadge category={match.match_category} />}
                  </div>

                  <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                    <span className="flex items-center gap-1 font-semibold text-slate-300">
                      <Building2 className="w-3.5 h-3.5 text-slate-500" />
                      {job.company || 'Not Specified'}
                    </span>
                    <span className="flex items-center gap-1 text-slate-400">
                      <MapPin className="w-3.5 h-3.5 text-slate-500" />
                      {job.location || 'Location Unspecified'}
                    </span>
                    <span className="text-slate-500">• {job.source}</span>
                  </div>

                  {match && (
                    <div className="flex items-center gap-2 flex-wrap pt-1">
                      <ExperienceStatusBadge status={match.experience_match} />
                      {match.role_family && (
                        <span className="px-2 py-0.5 rounded text-[11px] bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-medium">
                          {match.role_family}
                        </span>
                      )}
                      {match.canonical_role && (
                        <span className="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-slate-300 border border-slate-700">
                          {match.canonical_role}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="flex md:flex-col items-center md:items-end justify-between gap-3 shrink-0">
                  {match && (
                    <div className="text-left md:text-right">
                      <p className="text-xl font-extrabold text-sky-400">{match.final_score.toFixed(1)}%</p>
                      <p className="text-[10px] text-slate-400 font-medium">Match Score</p>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <Link
                      to={`/jobs/${job.id}`}
                      className="px-3 py-1.5 bg-sky-600/20 hover:bg-sky-600/30 border border-sky-500/30 text-sky-300 text-xs font-semibold rounded-lg transition"
                    >
                      Details
                    </Link>
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg transition"
                      title="Apply Manually"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination Footer */}
          <div className="flex items-center justify-between pt-4">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className="inline-flex items-center gap-1 px-3 py-2 bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition"
            >
              <ChevronLeft className="w-4 h-4" /> Previous
            </button>

            <span className="text-xs text-slate-400 font-medium">
              Page {Math.floor(offset / limit) + 1} of {Math.ceil(data.total / limit) || 1}
            </span>

            <button
              disabled={offset + limit >= data.total}
              onClick={() => setOffset(offset + limit)}
              className="inline-flex items-center gap-1 px-3 py-2 bg-slate-800 disabled:opacity-40 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
