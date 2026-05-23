import api from './client';
import {
  ProjectActivityItem,
  DashboardPeriod,
  InsightItem,
  ProjectStatsItem,
  LoadChartItem,
  DashboardProject
} from '../types/dashboard';

import { mockBackendData, mockInsightsData, mockProjectStats, mockLoadData } from './mocks/mocks';

let URL = 'localhost:8080'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';
export const dashboardApi = {
    getProjects: async (): Promise<DashboardProject[]> => {
    const response = await api.get<DashboardProject[]>(
      '/dashboard/projects'
    );

    return response.data;
  },
  getProjectActivity: async (period: DashboardPeriod): Promise<ProjectActivityItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockBackendData); }, 500);
      });
    }

    const response = await api.get<ProjectActivityItem[]>(
      '/dashboard/projects-activity',
      {
        params: { period }
      }
    );

    return response.data;
  },

  getAIInsights: async (): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockInsightsData), 500));
    }
    const response = await api.get<InsightItem[]>(
      '/dashboard/ai-insights'
    );
    return response.data;
  },

  getProjectStats: async (period: DashboardPeriod): Promise<ProjectStatsItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockProjectStats), 500));
    }
    const response = await api.get<ProjectStatsItem[]>(
      '/dashboard/projects-stats',
      {
        params: { period }
      }
    );
    return response.data;
  },

  getTeamsLoad: async (period: DashboardPeriod): Promise<LoadChartItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockLoadData), 500));
    }
    const response = await api.get<LoadChartItem[]>(
      '/dashboard/teams-load',
      {
        params: { period }
      }
    );
    return response.data;
  }
};

