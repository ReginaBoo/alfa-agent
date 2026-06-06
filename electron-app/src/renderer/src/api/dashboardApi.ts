import api from './client';  // 👈 Используем настроенный клиент

import {
  ProjectActivityItem,
  DashboardPeriod,
  InsightItem,
  ProjectStatsItem,
  LoadChartItem,
  ProjectItem,
  GanttProjectResponse,
  CycleTimeData,
  TeamWorkloadData,
  TeamFocusData
} from '../types/dashboard';

import {
  mockBackendData,
  mockInsightsData,
  mockProjectStats,
  mockLoadData,
  mockProjectsData,
  mockGanttData,
  mockProjectInsightsData,
  mockProjectCycleTimeData,
  mockTeamWorkloadData,
  mockTeamFocusData
} from './mocks/mocks';

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true';

export const dashboardApi = {

  getProjects: async (): Promise<ProjectItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockProjectsData); }, 500);
      });
    }

    const response = await api.get<ProjectItem[]>('/projects');
    return response.data;
  },

  getProjectActivity: async (period: DashboardPeriod): Promise<ProjectActivityItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => { resolve(mockBackendData); }, 500);
      });
    }

    const response = await api.get<ProjectActivityItem[]>('/projects-activity', {
      params: { period }
    });

    return response.data;
  },

  getAIInsights: async (): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockInsightsData), 500));
    }

    const response = await api.get<InsightItem[]>('/ai-insights');
    return response.data;
  },

  getProjectStats: async (period: DashboardPeriod): Promise<ProjectStatsItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockProjectStats), 500));
    }

    const response = await api.get<ProjectStatsItem[]>('/projects-stats', {
      params: { period }
    });
    return response.data;
  },

  getTeamsLoad: async (period: DashboardPeriod): Promise<LoadChartItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockLoadData), 500));
    }

    const response = await api.get<LoadChartItem[]>('/teams-load', {
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

    const response = await api.get<GanttProjectResponse>(`/projects/${projectId}/tasks`, {
      params: { period },
    });
    return response.data;
  },

  getProjectAIInsights: async (projectId: string): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockProjectInsightsData), 500));
    }
    const response = await api.get<InsightItem[]>(`/projects/${projectId}/ai-insights`);
    return response.data;
  },

  getProjectCycleTime: async (
    projectId: string,
    period: string
  ): Promise<{
    averageTimeText: string;
    stages: CycleTimeData['stages'];      // по этапам (Аналитика, Код...)
    statuses: CycleTimeData['stages'];    // по статусам (Backlog, In Progress...)
  }> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve({
        averageTimeText: "9 дн. 1 ч.",
        stages: mockProjectCycleTimeData.stages,
        statuses: [
          { id: "1", label: "In Progress", hours: 98.3, warning: true, tooltip: "..." },
          { id: "2", label: "Backlog", hours: 152.4, warning: true, tooltip: "..." },
          { id: "3", label: "Done", hours: 195 }
        ]
      }), 500));
    }

    const response = await api.get<{
      averageTimeText: string;
      stages: CycleTimeData['stages'];
      statuses: CycleTimeData['stages'];
    }>(`/projects/${projectId}/cycle-time`, {
      params: { period }
    });
    return response.data;
  },

  getProjectTeamWorkload: async (projectId: string, period: string): Promise<TeamWorkloadData> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockTeamWorkloadData), 500));
    }

    const response = await api.get<TeamWorkloadData>(
      `/projects/${projectId}/team-workload`,
      { params: { period } }
    );
    return response.data;
  },

  getProjectTeamFocus: async (projectId: string, period: string): Promise<TeamFocusData> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve(mockTeamFocusData), 500));
    }

    const response = await api.get<TeamFocusData>(
      `/projects/${projectId}/team-focus`,
      { params: { period } }
    );
    return response.data;
  },

  getMiniPanelInsights: async (): Promise<InsightItem[]> => {
    if (USE_MOCKS) {
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve([
            {
              id: 1,
              type: 'error',
              text: 'Проект «CRM»: просрочено 6 задач',
              recommendation: 'Проверьте пайплайн деплоя'
            },
            {
              id: 2,
              type: 'warning',
              text: 'Проект «Mobile»: Merge конфликт в ветке feature',
              recommendation: 'Срочно разрешите конфликт'
            }
          ]);
        }, 500);
      });
    }

    const response = await api.get<InsightItem[]>('/mini-panel/insights');
    return response.data;
  },

  // ============================================================
  // Chat Bot API
  // ============================================================

  chatCompletion: async (
    message: string,
    sessionId?: string,
    history?: { role: 'user' | 'assistant' | 'system'; content: string }[]
  ): Promise<{
    answer: string;
    session_id: string;
    metadata: {
      sql_queries?: string[];
      tool_calls?: string[];
      error?: string;
    };
  }> => {
    const response = await api.post('/chat/completion', {
      message,
      session_id: sessionId,
      history: history || []
    });
    return response.data;
  },

  chatAiCompletion: async (
    message: string,
    sessionId?: string,
    history?: { role: 'user' | 'assistant' | 'system'; content: string }[]
  ): Promise<{
    answer: string;
    session_id: string;
    metadata: {
      sql_queries?: string[];
      tool_calls?: string[];
      error?: string;
    };
  }> => {
    const response = await api.post('/chat/ai-completion', {
      message,
      session_id: sessionId,
      history: history || []
    });
    return response.data;
  },

  executeSqlTool: async (
    sql: string,
    sessionId?: string
  ): Promise<{
    success: boolean;
    data?: any[];
    row_count: number;
    error?: string;
  }> => {
    const response = await api.post('/chat/tools/execute-sql', {
      sql,
      session_id: sessionId
    });
    return response.data;
  },

  callTool: async (
    toolName: 'execute_sql' | 'get_project_metrics' | 'get_user_workload',
    params: Record<string, any>,
    sessionId?: string
  ): Promise<{
    success: boolean;
    tool_name: string;
    data: any;
    error?: string;
  }> => {
    const response = await api.post('/chat/tools/call', {
      tool_name: toolName,
      params,
      session_id: sessionId
    });
    return response.data;
  },

  getChatHistory: async (sessionId: string): Promise<{
    session_id: string;
    messages: { role: string; content: string }[];
  }> => {
    const response = await api.get(`/chat/history/${sessionId}`);
    return response.data;
  },

  getAllowedTables: async (): Promise<{
    tables: string[];
    description: string;
  }> => {
    const response = await api.get('/chat/allowed-tables');
    return response.data;
  },

};
