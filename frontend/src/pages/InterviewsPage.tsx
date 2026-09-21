import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { LoadingState, ErrorAlert, EmptyState } from '../components/States';
import { Calendar, Clock, Info } from 'lucide-react';

export const InterviewsPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [interviews, setInterviews] = useState<any[]>([]);

  const loadInterviews = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getInterviews();
      setInterviews(res.interviews || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch interview schedules');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInterviews();
  }, []);

  if (loading) return <LoadingState message="Checking interview schedules..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadInterviews} />;

  if (interviews.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-sky-400" />
            Interview Schedules
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Upcoming recruitment interviews, technical assessments, and interview invitations.
          </p>
        </div>

        <EmptyState
          title="No Scheduled Interviews"
          description="Interview invitations detected from Gmail or ATS updates will automatically appear here once scheduled."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
        <Calendar className="w-5 h-5 text-sky-400" />
        Interview Schedules ({interviews.length})
      </h2>
      <div className="space-y-3">
        {interviews.map((item, idx) => (
          <div key={idx} className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
            <p className="text-sm font-bold text-slate-100">{item.company} - {item.role}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
