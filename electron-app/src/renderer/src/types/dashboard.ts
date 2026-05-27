//Активность по проектам
export interface ProjectActivityItem {
  date: string;
  value: number;
  project: string;
}

// Периоды дашбордов
export type DashboardPeriod = 'all' | 'last week';

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


//Выбор метрик
export type DashboardMetric = 'effectiveness' | 'activity' | 'codeCount';

//Список проектов
export interface ProjectItem {
  id: string;
  name: string;
}

//Гант
export interface GanttProjectResponse {
  viewRange: {
    start: string;
    end: string;
  };
  tasks: GanttRecord[];
}

export interface GanttRecord {
  id: string;
  task: string;
  duration: string;
  progress: number;
  start?: string;
  end?: string;
  responsible?: string;
  issueKey?: string; // Добавим ключ задачи (например, "HEALTH-123")
  children?: GanttRecord[];
}

//Время цикла
export interface CycleStage {
  id: string;
  label: string;
  hours: number;
  warning?: boolean;
  tooltip?: string;
}

export interface CycleTimeData {
  stages: CycleStage[];
  averageTimeText: string;
}

//Загрузка команды
export type WorkloadCalculationType = 'story_points' | 'hours' | 'task_count';

export interface TeamMemberWorkload {
  id: string;
  name: string;
  workloadIndex: number; // Теперь передаем WI (например: 0.85, 1.4) вместо процентов
}

export interface TeamWorkloadData {
  calculationType: WorkloadCalculationType; // 'story_points' | 'hours' | 'task_count'
  teamWorkloadBalance: number;              // Стандартное отклонение (Workload Balance)
  recommendationText: string;               // Текст рекомендации ИИ
  members: TeamMemberWorkload[];
}

//Фокус команды
export interface FocusCategory {
  type: string;  // "Новые фичи", "Рефактор/Долг", "Баги"
  value: number; // Процентное значение (например: 60, 25, 15)
}

export interface TeamFocusData {
  categories: FocusCategory[];
}
