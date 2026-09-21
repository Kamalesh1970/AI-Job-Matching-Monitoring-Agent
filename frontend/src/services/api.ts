import {
  DashboardData,
  JobsResponse,
  JobDetailResponse,
  CompaniesResponse,
  ApplicationsResponse,
  GmailIntelligenceResponse,
  SkillsResponse,
  ResumesResponse,
  TailoredResumeDraft,
  AnalyticsData,
  SettingsData,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${url}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API Error (${response.status}): ${errorText || response.statusText}`);
    }

    return await response.json();
  } catch (error: any) {
    console.error(`Fetch failed for ${url}:`, error);
    throw new Error(error.message || 'Network connection failed. Backend service might be unavailable.');
  }
}

export const api = {
  getDashboard: () => fetchJson<DashboardData>('/api/dashboard'),
  
  getJobs: (params?: {
    search?: string;
    role_family?: string;
    match_category?: string;
    experience_match?: string;
    location?: string;
    source?: string;
    company?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          query.append(key, String(value));
        }
      });
    }
    const queryString = query.toString();
    return fetchJson<JobsResponse>(`/api/jobs${queryString ? `?${queryString}` : ''}`);
  },

  getJobDetail: (id: number) => fetchJson<JobDetailResponse>(`/api/jobs/${id}`),

  getCompanies: () => fetchJson<CompaniesResponse>('/api/companies'),

  getApplications: () => fetchJson<ApplicationsResponse>('/api/applications'),

  getGmailIntelligence: () => fetchJson<GmailIntelligenceResponse>('/api/gmail'),

  getInterviews: () => fetchJson<{ interviews: any[]; total: number; status: string }>('/api/interviews'),

  getSkills: () => fetchJson<SkillsResponse>('/api/skills'),

  getResumes: () => fetchJson<ResumesResponse>('/api/resumes'),

  getResumeDetail: (id: number) => fetchJson<TailoredResumeDraft>(`/api/resumes/${id}`),

  updateResumeStatus: (id: number, status: string) =>
    fetchJson<{ status: string; draft_id: number; new_status: string }>(`/api/resumes/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),

  getAnalytics: () => fetchJson<AnalyticsData>('/api/analytics'),

  getSettings: () => fetchJson<SettingsData>('/api/settings'),
};
