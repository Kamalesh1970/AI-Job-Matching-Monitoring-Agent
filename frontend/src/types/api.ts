export interface Job {
  id: number;
  source: string;
  source_job_id: string;
  title: string;
  company: string;
  location: string;
  description: string;
  url: string;
  created_at: string | null;
  fetched_at: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  employment_type: string | null;
  category: string | null;
  fingerprint: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface MatchResult {
  job_id: number;
  source_job_id: string;
  title: string;
  company: string;
  location: string;
  similarity_score: number;
  skill_score: number;
  rule_score: number;
  final_score: number;
  overall_score: number;
  matched_skills: string[];
  missing_skills: string[];
  skill_gaps: string[];
  experience_status: string;
  location_status: string;
  match_status: string;
  match_category: 'STRONG_MATCH' | 'POTENTIAL_MATCH' | 'LOW_MATCH' | 'NOT_RELEVANT';
  role_family: string | null;
  canonical_role: string | null;
  experience_match: 'MATCH' | 'POSSIBLE_MATCH' | 'EXPERIENCE_GAP' | 'NOT_ELIGIBLE';
  role_score: number;
  experience_score: number;
  education_score: number;
  location_score: number;
  seniority_score: number;
  reasons: string[];
  calculated_at: string;
}

export interface JobMatchPair {
  job: Job;
  match: MatchResult | null;
}

export interface PipelineRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  jobs_fetched: number;
  new_jobs: number;
  existing_jobs: number;
  matches_found: number;
  eligible_notifications: number;
  notifications_sent: number;
  failed_sources: number;
  error_message: string | null;
}

export interface DashboardData {
  total_jobs: number;
  ai_relevant_jobs: number;
  strong_matches: number;
  potential_matches: number;
  low_matches: number;
  experience_gaps: number;
  source_distribution: Record<string, number>;
  match_category_distribution: Record<string, number>;
  experience_status_distribution: Record<string, number>;
  top_matching_jobs: JobMatchPair[];
  recent_jobs: Job[];
  last_pipeline_run: PipelineRun | null;
}

export interface JobsResponse {
  total: number;
  limit: number;
  offset: number;
  jobs: JobMatchPair[];
  facets: {
    sources: string[];
    role_families: string[];
    companies: string[];
    match_categories: string[];
    experience_matches: string[];
  };
}

export interface JobDetailResponse {
  job: Job;
  match: MatchResult | null;
  tailored_drafts: any[];
  candidate_profile: {
    experience_level: string;
    years_experience: number;
    status: string;
  };
}

export interface CompanyInfo {
  name: string;
  location: string;
  associated_jobs_count: number;
  sources: string[];
  latest_job_title: string;
  latest_job_date: string;
}

export interface CompaniesResponse {
  companies: CompanyInfo[];
  total: number;
}

export interface ApplicationInfo {
  id: number;
  job_id: number;
  match_score: number;
  provider: string;
  model: string;
  status: string;
  resume_content: any;
  changes: string[];
  warnings: string[];
  validation_result: any;
  created_at: string;
  reviewed_at: string | null;
  job_title: string;
  job_company: string;
  job_source: string;
  job_url: string;
}

export interface ApplicationsResponse {
  applications: ApplicationInfo[];
  total: number;
}

export interface GmailEvent {
  id: number;
  sender: string;
  company: string;
  subject: string;
  category: string;
  received_date: string;
  extracted_role: string;
  source: string;
  action_required: string;
  url: string;
}

export interface GmailIntelligenceResponse {
  events: GmailEvent[];
  total: number;
  categories: string[];
  gmail_enabled: boolean;
}

export interface SkillFrequency {
  skill: string;
  count: number;
}

export interface SkillsResponse {
  candidate_skills: string[];
  frequently_requested_skills: SkillFrequency[];
  top_missing_skills: SkillFrequency[];
  top_matched_skills: SkillFrequency[];
}

export interface TailoredResumeDraft {
  id: number;
  job_id: number;
  match_score: number;
  provider: string;
  model: string;
  status: string;
  resume_content: any;
  changes: string[];
  warnings: string[];
  validation_result: any;
  created_at: string;
  reviewed_at: string | null;
  job_title: string;
  job_company: string;
}

export interface ResumesResponse {
  base_resume_path: string;
  base_resume_snippet: string;
  tailored_drafts: TailoredResumeDraft[];
  total_drafts: number;
}

export interface ChartDataPoint {
  name: string;
  value: number;
}

export interface TimeChartDataPoint {
  date: string;
  jobs: number;
}

export interface AnalyticsData {
  match_category_distribution: ChartDataPoint[];
  experience_status_distribution: ChartDataPoint[];
  jobs_by_source: ChartDataPoint[];
  jobs_by_role_family: ChartDataPoint[];
  jobs_over_time: TimeChartDataPoint[];
}

export interface SettingsData {
  candidate_status: string;
  candidate_experience_level: string;
  candidate_years_experience: number;
  min_match_score: number;
  preferred_locations: string[];
  keywords: string[];
  enabled_sources: string[];
  telegram_enabled: boolean;
  gmail_enabled: boolean;
  scheduler_enabled: boolean;
  scheduler_interval_minutes: number;
  db_path: string;
}
