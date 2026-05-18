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
  status: 'error' | 'warning' | 'normal';
  stats: {
    workload: number;
    reviewTime: string;
    bugs: number;
    prCount: number;
    commits: string;
    sla: number;
  };
}