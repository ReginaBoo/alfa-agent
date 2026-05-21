import axios from 'axios';
import { ProjectActivityItem, DashboardPeriod, InsightItem, ProjectStatsItem, LoadChartItem } from '../types/dashboard';
import { mockBackendData, mockInsightsData, mockProjectStats, mockLoadData } from './mocks/mocks';

let URL = 'localhost:8080'

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';
export const dashboardApi = {
  getProjectActivity: async (period: DashboardPeriod): Promise<ProjectActivityItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockBackendData); }, 500);
      });
    }

    const response = await axios.get<ProjectActivityItem[]>(URL + '/api/projects-activity', {
      params: { period }
    });

    return response.data;
  },

  getAIInsights: async (): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockInsightsData), 500));
    }
    const response = await axios.get<InsightItem[]>(URL + '/api/ai - insights');
    return response.data;
  },

  getProjectStats: async (period: DashboardPeriod): Promise<ProjectStatsItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockProjectStats), 500));
    }
    const response = await axios.get<ProjectStatsItem[]>('/api/projects-stats', { params: { period } });
    return response.data;
  },

  getTeamsLoad: async (period: DashboardPeriod): Promise<LoadChartItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockLoadData), 500));
    }
    const response = await axios.get<LoadChartItem[]>('/api/teams-load', { params: { period } });
    return response.data;
  }
};

