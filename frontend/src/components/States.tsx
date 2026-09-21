import React from 'react';
import { Loader2, AlertCircle, Inbox, RefreshCw } from 'lucide-react';

interface LoadingProps {
  message?: string;
}

export const LoadingState: React.FC<LoadingProps> = ({ message = 'Loading career intelligence data...' }) => (
  <div className="flex flex-col items-center justify-center p-12 min-h-[300px] text-slate-400">
    <Loader2 className="w-8 h-8 animate-spin text-sky-500 mb-3" />
    <p className="text-sm font-medium">{message}</p>
  </div>
);

interface EmptyProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
}

export const EmptyState: React.FC<EmptyProps> = ({
  title = 'No Records Found',
  description = 'No matching data is available at this time.',
  onRetry,
}) => (
  <div className="flex flex-col items-center justify-center p-12 bg-slate-800/40 rounded-xl border border-slate-700/50 text-center min-h-[250px]">
    <div className="p-3 bg-slate-800/80 rounded-full text-slate-400 mb-3 border border-slate-700">
      <Inbox className="w-6 h-6" />
    </div>
    <h3 className="text-base font-semibold text-slate-200 mb-1">{title}</h3>
    <p className="text-sm text-slate-400 max-w-md mb-4">{description}</p>
    {onRetry && (
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium border border-slate-700 transition"
      >
        <RefreshCw className="w-4 h-4" />
        Refresh Data
      </button>
    )}
  </div>
);

interface ErrorProps {
  message: string;
  onRetry?: () => void;
}

export const ErrorAlert: React.FC<ErrorProps> = ({ message, onRetry }) => (
  <div className="p-4 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm flex items-start justify-between gap-3">
    <div className="flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
      <div>
        <h4 className="font-semibold text-rose-200 mb-1">Failed to Load Data</h4>
        <p className="text-rose-300/90">{message}</p>
      </div>
    </div>
    {onRetry && (
      <button
        onClick={onRetry}
        className="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-200 text-xs font-semibold rounded-lg transition shrink-0"
      >
        Try Again
      </button>
    )}
  </div>
);
