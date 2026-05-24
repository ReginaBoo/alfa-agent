
import axios from 'axios';

import {
  ProjectActivityItem,
  DashboardPeriod,
  InsightItem,
  ProjectStatsItem,
  LoadChartItem,
  ProjectItem, GanttProjectResponse // Импортируем тип проекта
} from '../types/dashboard';

import {
  mockBackendData,
  mockInsightsData,
  mockProjectStats,
  mockLoadData,
  mockProjectsData, mockGanttData, mockProjectInsightsData// Импортируем мок проектов
} from './mocks/mocks';



const URL = 'http://localhost:8000';

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

export const dashboardApi = {

  getProjects: async (): Promise<ProjectItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockProjectsData); }, 500);
      });
    }

    const response = await axios.get<ProjectItem[]>(`${URL}/api/projects`);
    return response.data;
  },

  getProjectActivity: async (period: DashboardPeriod): Promise<ProjectActivityItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockBackendData); }, 500);
      });
    }

    const response = await axios.get<ProjectActivityItem[]>(`${URL}/api/projects-activity`, {
      params: { period }
    });

    return response.data;
  },

  getAIInsights: async (): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockInsightsData), 500));
    }

    const response = await axios.get<InsightItem[]>(`${URL}/api/ai-insights`);
    return response.data;
  },

  getProjectStats: async (period: DashboardPeriod): Promise<ProjectStatsItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockProjectStats), 500));
    }

    const response = await axios.get<ProjectStatsItem[]>(`${URL}/api/projects-stats`, {
      params: { period }
    });
    return response.data;
  },

  getTeamsLoad: async (period: DashboardPeriod): Promise<LoadChartItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockLoadData), 500));
    }

    const response = await axios.get<LoadChartItem[]>(`${URL}/api/teams-load`, {
      params: { period }
    });

    return response.data;
  },

  getProjectTasks: async (projectId: string, period: DashboardPeriod): Promise<GanttProjectResponse> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockGanttData); }, 500);
      });
    }

    const response = await axios.get<GanttProjectResponse>(`${URL}/api/projects/${projectId}/tasks`, {
      params: { period },
    });
    return response.data;
  },
  getProjectAIInsights: async (projectId: string): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockProjectInsightsData), 500));
    }
    const response = await axios.get<InsightItem[]>(`${URL}/api/projects/${projectId}/ai-insights`);
    return response.data;
  },


};
