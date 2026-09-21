import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, HelpCircle, Flame, Star, AlertCircle } from 'lucide-react';

interface CategoryBadgeProps {
  category?: string | null;
}

export const MatchCategoryBadge: React.FC<CategoryBadgeProps> = ({ category }) => {
  switch (category) {
    case 'STRONG_MATCH':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <Flame className="w-3.5 h-3.5" />
          Strong Match
        </span>
      );
    case 'POTENTIAL_MATCH':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <Star className="w-3.5 h-3.5" />
          Potential Match
        </span>
      );
    case 'LOW_MATCH':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/15 text-sky-400 border border-sky-500/30">
          <AlertCircle className="w-3.5 h-3.5" />
          Low Match
        </span>
      );
    case 'NOT_RELEVANT':
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
          Not Relevant
        </span>
      );
  }
};

interface ExperienceBadgeProps {
  status?: string | null;
}

export const ExperienceStatusBadge: React.FC<ExperienceBadgeProps> = ({ status }) => {
  switch (status) {
    case 'MATCH':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="w-3.5 h-3.5" />
          Fresher Eligible (0 yrs)
        </span>
      );
    case 'POSSIBLE_MATCH':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
          <HelpCircle className="w-3.5 h-3.5" />
          Possible Match (0-1 yrs)
        </span>
      );
    case 'EXPERIENCE_GAP':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertTriangle className="w-3.5 h-3.5" />
          ⚠️ Experience Gap
        </span>
      );
    case 'NOT_ELIGIBLE':
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <XCircle className="w-3.5 h-3.5" />
          ❌ Not Eligible
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
          {status || 'Unknown'}
        </span>
      );
  }
};
