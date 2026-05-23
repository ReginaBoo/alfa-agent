//Активность по проектам
export interface ProjectActivityItem {
  date: string;
  value: number;
  project: string;
}

// Периоды дашбордов
export type DashboardPeriod = 'Весь период' | 'Последняя неделя';

//Ai-выводы
export interface InsightItem {
  id: number;
  type: 'error' | 'warning' | 'success';
  text: string;
  recommendation: string;
}

//Статусы проектов
export interface ProjectStatsItem {
  id: number;
  name: string;
  project_id?: number;
  jira_url?: string;
  status:'error' | 'warning' | 'success';
  stats: {
    workload: number;
    reviewTime: string;
    bugs: number;
    prCount: number;
    commits: string;
    sla: number;
  };
}

//Загруженность команд
export interface LoadChartItem {
  project: string;
  load: number;          // Значение от 0 до 1 (например, 0.62)
  statusType: 'underload' | 'optimal' | 'high' | 'overload';
  description?: string;
}

export interface DashboardProject {
  id: number;
  key: string;
  name: string;
  avatar_url?: string;
}
