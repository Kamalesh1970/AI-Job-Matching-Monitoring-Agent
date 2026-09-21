import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { SkillsResponse } from '../types/api';
import { LoadingState, ErrorAlert } from '../components/States';
import { Sparkles, CheckCircle2, AlertTriangle, BarChart2 } from 'lucide-react';

export const SkillsPage: React.FC = () => {
  const [data, setData] = useState<SkillsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSkills = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getSkills();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load skill metrics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSkills();
  }, []);

  if (loading) return <LoadingState message="Extracting skill frequency breakdown..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadSkills} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-sky-400" />
          Skill Analytics & Intelligence
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Candidate skills vocabulary vs. market-requested skills across all discovered AI jobs.
        </p>
      </div>

      {/* Grid of Skill Lists */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Candidate Skills */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
          <h3 className="text-sm font-bold text-emerald-400 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            Candidate Skills ({data.candidate_skills.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.candidate_skills.map((skill) => (
              <span
                key={skill}
                className="px-2.5 py-1 rounded-md text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>

        {/* Top Requested Market Skills */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
          <h3 className="text-sm font-bold text-sky-400 flex items-center gap-2">
            <BarChart2 className="w-4 h-4" />
            Most Requested Market Skills
          </h3>
          <div className="space-y-2">
            {data.frequently_requested_skills.slice(0, 10).map(({ skill, count }) => (
              <div key={skill} className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">{skill}</span>
                <span className="px-2 py-0.5 bg-slate-800 text-slate-400 rounded-md font-bold">{count} jobs</span>
              </div>
            ))}
          </div>
        </div>

        {/* Top Missing Skill Gaps */}
        <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
          <h3 className="text-sm font-bold text-amber-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Top Skill Gaps
          </h3>
          <div className="space-y-2">
            {data.top_missing_skills.slice(0, 10).map(({ skill, count }) => (
              <div key={skill} className="flex items-center justify-between text-xs">
                <span className="text-slate-300 font-medium">{skill}</span>
                <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-md font-bold">
                  Missing in {count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
