import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ResumesResponse, TailoredResumeDraft } from '../types/api';
import { LoadingState, ErrorAlert } from '../components/States';
import { FileText, CheckCircle2, XCircle, Clock, FileCode, ShieldAlert } from 'lucide-react';

export const ResumePage: React.FC = () => {
  const [data, setData] = useState<ResumesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDraft, setSelectedDraft] = useState<TailoredResumeDraft | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadResumes = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getResumes();
      setData(res);
      if (res.tailored_drafts.length > 0 && !selectedDraft) {
        setSelectedDraft(res.tailored_drafts[0]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load resume drafts');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResumes();
  }, []);

  const handleUpdateStatus = async (draftId: number, newStatus: string) => {
    try {
      setActionLoading(true);
      await api.updateResumeStatus(draftId, newStatus);
      await loadResumes();
      if (selectedDraft && selectedDraft.id === draftId) {
        setSelectedDraft({ ...selectedDraft, status: newStatus });
      }
    } catch (err: any) {
      alert(`Error updating draft status: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <LoadingState message="Fetching resume tailoring drafts..." />;
  if (error) return <ErrorAlert message={error} onRetry={loadResumes} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          <FileText className="w-5 h-5 text-sky-400" />
          Base Resume & Tailored Drafts ({data.total_drafts})
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Review base candidate profile and human-approved LLM tailored resume drafts.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left List of Tailored Drafts */}
        <div className="space-y-4">
          {/* Base Resume snippet card */}
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-2">
            <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <FileCode className="w-4 h-4 text-sky-400" />
              Base Resume Path
            </h3>
            <p className="text-xs font-mono text-slate-400 truncate">{data.base_resume_path}</p>
          </div>

          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider pt-2">
            Tailored Resume Drafts
          </h3>

          {data.tailored_drafts.length === 0 ? (
            <p className="text-xs text-slate-500 italic p-4 bg-slate-900 border border-slate-800 rounded-xl">
              No tailored resume drafts generated yet. Trigger LLM tailoring via CLI or backend pipeline.
            </p>
          ) : (
            <div className="space-y-2">
              {data.tailored_drafts.map((draft) => (
                <div
                  key={draft.id}
                  onClick={() => setSelectedDraft(draft)}
                  className={`p-3.5 rounded-xl border transition cursor-pointer ${
                    selectedDraft?.id === draft.id
                      ? 'bg-sky-500/10 border-sky-500/40 text-slate-100'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <h4 className="text-xs font-bold truncate">{draft.job_title || `Draft #${draft.id}`}</h4>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                        draft.status === 'APPROVED'
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : draft.status === 'REJECTED'
                          ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                          : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                      }`}
                    >
                      {draft.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 truncate">{draft.job_company}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 mt-2 pt-2 border-t border-slate-800/80">
                    <span>Score: {draft.match_score.toFixed(1)}%</span>
                    <span>{new Date(draft.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Draft Detail View & Human Approval Actions */}
        <div className="lg:col-span-2 space-y-6">
          {selectedDraft ? (
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-bold text-slate-100">{selectedDraft.job_title}</h3>
                    <span
                      className={`px-2.5 py-0.5 rounded text-xs font-bold border ${
                        selectedDraft.status === 'APPROVED'
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : selectedDraft.status === 'REJECTED'
                          ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                          : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                      }`}
                    >
                      {selectedDraft.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{selectedDraft.job_company} • Match: {selectedDraft.match_score.toFixed(1)}%</p>
                </div>

                {/* Status Action Buttons */}
                <div className="flex items-center gap-2">
                  <button
                    disabled={actionLoading || selectedDraft.status === 'APPROVED'}
                    onClick={() => handleUpdateStatus(selectedDraft.id, 'APPROVED')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Approve
                  </button>

                  <button
                    disabled={actionLoading || selectedDraft.status === 'REJECTED'}
                    onClick={() => handleUpdateStatus(selectedDraft.id, 'REJECTED')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 text-white text-xs font-semibold rounded-lg transition"
                  >
                    <XCircle className="w-4 h-4" /> Reject
                  </button>
                </div>
              </div>

              {/* Warnings / Truth Validation */}
              {selectedDraft.warnings && selectedDraft.warnings.length > 0 && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-300 text-xs space-y-1">
                  <p className="font-semibold flex items-center gap-1">
                    <ShieldAlert className="w-4 h-4" /> Tailoring Warnings:
                  </p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {selectedDraft.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Resume Draft Content Preview */}
              <div className="space-y-3 pt-2">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Summary
                </h4>
                <p className="text-xs text-slate-300 bg-slate-800/60 p-3 rounded-lg border border-slate-800">
                  {selectedDraft.resume_content?.summary || 'No summary text.'}
                </p>

                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider pt-2">
                  Highlighted Skills
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {(selectedDraft.resume_content?.skills || []).map((skill: string) => (
                    <span key={skill} className="px-2 py-0.5 bg-sky-500/10 text-sky-300 text-xs rounded border border-sky-500/20">
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-12 text-center text-slate-500 bg-slate-900 border border-slate-800 rounded-xl text-xs">
              Select a tailored resume draft from the list to review details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
