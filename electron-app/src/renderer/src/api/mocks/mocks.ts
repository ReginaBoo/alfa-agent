import { ProjectActivityItem, InsightItem, ProjectStatsItem, LoadChartItem } from '../../types/dashboard';
export const mockBackendData: ProjectActivityItem[] = [
  // МАРТ
  { date: '2026-03-01', value: 15, project: 'Проект 1' },
  { date: '2026-03-08', value: 25, project: 'Проект 1' },
  { date: '2026-03-15', value: 35, project: 'Проект 1' },
  { date: '2026-03-22', value: 50, project: 'Проект 1' },
  { date: '2026-03-29', value: 55, project: 'Проект 1' },
  { date: '2026-03-01', value: 40, project: 'Проект 2' },
  { date: '2026-03-08', value: 80, project: 'Проект 2' },
  { date: '2026-03-15', value: 95, project: 'Проект 2' },
  { date: '2026-03-22', value: 60, project: 'Проект 2' },
  { date: '2026-03-29', value: 30, project: 'Проект 2' },
  { date: '2026-03-01', value: 5, project: 'Проект 3' },
  { date: '2026-03-15', value: 20, project: 'Проект 3' },
  { date: '2026-03-29', value: 45, project: 'Проект 3' },
  // АПРЕЛЬ
  { date: '2026-04-05', value: 65, project: 'Проект 1' },
  { date: '2026-04-12', value: 75, project: 'Проект 1' },
  { date: '2026-04-19', value: 85, project: 'Проект 1' },
  { date: '2026-04-26', value: 90, project: 'Проект 1' },
  { date: '2026-04-05', value: 20, project: 'Проект 2' },
  { date: '2026-04-12', value: 15, project: 'Проект 2' },
  { date: '2026-04-19', value: 40, project: 'Проект 2' },
  { date: '2026-04-26', value: 55, project: 'Проект 2' },
  { date: '2026-04-05', value: 50, project: 'Проект 3' },
  { date: '2026-04-12', value: 60, project: 'Проект 3' },
  { date: '2026-04-19', value: 55, project: 'Проект 3' },
  { date: '2026-04-26', value: 70, project: 'Проект 3' },
];

export const mockInsightsData: InsightItem[] = [
  {
    id: 1,
    type: 'error',
    text: 'Проект 1: просрочено 6 задач, CI/CD сломан уже 8 часов. Проект «CRM»: обнаружен Bus Factor 92% на модуле авторизации',
    recommendation: 'Рекомендация: Срочно перераспределить ресурсы в Проекте 3',
  },
  {
    id: 2,
    type: 'warning',
    text: 'В проекте «Проект 2» высокий риск срыва спринта (отставание на 3 дня). Обнаружен застой — 4 PR висят без ревью.',
    recommendation: 'Рекомендация: Проверить загрузку Николая в Проект 2 и назначить дополнительного ревьюера в проект',
  },
  {
    id: 3,
    type: 'success',
    text: 'Проект 3: Ситуация стабильная. Все проекты идут по плану. Общая готовность спринтов — 78%.',
    recommendation: 'Свободные ресурсы: Ольга (загрузка 0.4), можно подключить к active задачам.',
  },
  {
    id: 4,
    type: 'success',
    text: 'Проект 4: Ситуация стабильная. Все проекты идут по плану. Общая готовность спринтов — 78%.',
    recommendation: 'Свободные ресурсы: Ольга (загрузка 0.4), можно подключить к активным задачам.',
  },
];

export const mockProjectStats: ProjectStatsItem[] = [
  {
    id: 1,
    name: 'Проект 1',
    status: 'error',
    stats: { workload: 105, reviewTime: '42ч', bugs: 12, prCount: 12, commits: '120↑', sla: 72 }
  },
  {
    id: 2,
    name: 'Проект 2',
    status: 'warning',
    stats: { workload: 90, reviewTime: '15ч', bugs: 5, prCount: 8, commits: '45↑', sla: 88 }
  },
  {
    id: 3,
    name: 'Проект 3',
    status: 'normal',
    stats: { workload: 78, reviewTime: '4ч', bugs: 1, prCount: 2, commits: '80↑', sla: 96 }
  },
  {
    id: 4,
    name: 'Проект 4',
    status: 'normal',
    stats: { workload: 60, reviewTime: '2ч', bugs: 0, prCount: 1, commits: '15↑', sla: 99 }
  },
];

export const mockLoadData: LoadChartItem[] = [
  { project: 'Проект 1', load: 1.75, statusType: 'overload', description: 'Критический перегруз ключевых разработчиков' },
  { project: 'Проект 2', load: 0.62, statusType: 'optimal', description: 'Команда идет строго по графику спринта' },
  { project: 'Проект 3', load: 0.45, statusType: 'high', description: 'Неравномерное распределение обязанностей' },
  { project: 'Проект 4', load: 0.1, statusType: 'underload', description: 'Ресурсы освободились, можно подключать новые задачи' },
];
