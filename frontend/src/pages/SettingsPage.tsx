import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { SettingsData } from '../types/api';
import { LoadingState, ErrorAlert } from '../components/States';
import { Settings, ShieldCheck, User, Database, Bell, Radio } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [data, setData] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSettings = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getSettings();
      setData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to load system settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  if (loading) return <LoadingState message="Reading safe system configuration..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadSettings} />;
  if (!data) return null;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <Settings className="w-5 h-5 text-sky-400" />
          System & Candidate Configuration
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Read-only configuration parameters loaded from environment & profile configuration.
        </p>
      </div>

      {/* Candidate Profile Section */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <User className="w-4 h-4 text-sky-400" />
          Candidate Fresher Profile
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-slate-800/50 rounded-lg">
            <span className="text-slate-400">Current Status:</span>
            <p className="font-semibold text-slate-100 mt-1">{data.candidate_status}</p>
          </div>
          <div className="p-3 bg-slate-800/50 rounded-lg">
            <span className="text-slate-400">Experience Level:</span>
            <p className="font-semibold text-slate-100 mt-1">{data.candidate_experience_level}</p>
          </div>
          <div className="p-3 bg-slate-800/50 rounded-lg">
            <span className="text-slate-400">Years of Experience:</span>
            <p className="font-semibold text-slate-100 mt-1">{data.candidate_years_experience} Years</p>
          </div>
        </div>
      </div>

      {/* Active Platforms */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Radio className="w-4 h-4 text-indigo-400" />
          Enabled Job Sources ({data.enabled_sources.length})
        </h3>
        <div className="flex flex-wrap gap-2">
          {data.enabled_sources.map((src) => (
            <span
              key={src}
              className="px-3 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700"
            >
              {src}
            </span>
          ))}
        </div>
      </div>

      {/* System Settings & Storage */}
      <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
          <Database className="w-4 h-4 text-emerald-400" />
          Storage & Pipeline Runtime
        </h3>

        <div className="space-y-3 text-xs">
          <div className="flex items-center justify-between p-3 bg-slate-800/40 rounded-lg">
            <span className="text-slate-400">Database Path:</span>
            <code className="text-slate-200 font-mono">{data.db_path}</code>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-800/40 rounded-lg">
            <span className="text-slate-400">Scheduled Monitoring:</span>
            <span className="font-semibold text-emerald-400">
              {data.scheduler_enabled ? `Active (Every ${data.scheduler_interval_minutes}m)` : 'Disabled'}
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-800/40 rounded-lg">
            <span className="text-slate-400">Telegram Notifications:</span>
            <span className="font-semibold text-sky-400">
              {data.telegram_enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        </div>
      </div>

      {/* Security Note */}
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-xs text-slate-400 flex items-center gap-2">
        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
        <span>Sensitive API keys and OAuth tokens are strictly shielded from frontend exposure.</span>
      </div>
    </div>
  );
};
