import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { DashboardPage } from '../pages/DashboardPage';
import { JobsPage } from '../pages/JobsPage';
import { JobDetailPage } from '../pages/JobDetailPage';
import { CompaniesPage } from '../pages/CompaniesPage';
import { ApplicationsPage } from '../pages/ApplicationsPage';
import { GmailPage } from '../pages/GmailPage';
import { InterviewsPage } from '../pages/InterviewsPage';
import { SkillsPage } from '../pages/SkillsPage';
import { ResumePage } from '../pages/ResumePage';
import { AnalyticsPage } from '../pages/AnalyticsPage';
import { SettingsPage } from '../pages/SettingsPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:id" element={<JobDetailPage />} />
        <Route path="companies" element={<CompaniesPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="gmail" element={<GmailPage />} />
        <Route path="interviews" element={<InterviewsPage />} />
        <Route path="skills" element={<SkillsPage />} />
        <Route path="resume" element={<ResumePage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<DashboardPage />} />
      </Route>
    </Routes>
  );
};
