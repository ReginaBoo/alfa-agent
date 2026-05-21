import { ProjectActivityItem, InsightItem, ProjectStatsItem, LoadChartItem, GanttProjectResponse } from '../../types/dashboard';
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

export const mockProjectsData = [
  { id: '1', name: 'Проект Арака' },
  { id: '2', name: 'Проект 2' }
];

export const mockGanttData: GanttProjectResponse = {
  // Наш бэкенд решил показать период с марта по май 2026 года
  viewRange: {
    start: '2026-03-01',
    end: '2027-01-31',
  },
  tasks: [
    {
      id: '1',
      task: 'Этап 1. Аналитика и Архитектура',
      duration: '24 дня',
      progress: 65,
      children: [
        {
          id: '1-1',
          task: 'Сбор требований и ТЗ',
          duration: '7 дней',
          progress: 100,
          responsible: 'Соня',
          start: '2026-03-02', // Понедельник (Неделя 10)
          end: '2026-03-08',   // Воскресенье (Неделя 10) -> Рендерится ровно на ВСЮ ячейку
        },
        {
          id: '1-2',
          task: 'Проектирование базы данных',
          duration: '17 дней',
          progress: 45,
          responsible: 'Иван',
          start: '2026-03-09', // Понедельник (Неделя 11)
          end: '2026-03-25',   // Среда (Неделя 13) -> Пройдет сквозь 11, 12 недели и обрежется посреди 13-й
        },
        {
          id: '1-3',
          task: 'Согласование архитектуры',
          duration: '7 дней',
          progress: 0,
          responsible: 'Анна',
          start: '2026-03-23', // Понедельник (Неделя 13)
          end: '2026-03-29',   // Воскресенье (Неделя 13) -> Накладывается параллельно Ивану на 13-й неделе
        }
      ]
    },
    {
      id: '2',
      task: 'Этап 2. Разработка базового функционала',
      duration: '30 дней',
      progress: 15,
      children: [
        {
          id: '2-1',
          task: 'Разработка API (Backend)',
          duration: '14 дней',
          progress: 30,
          responsible: 'Дмитрий', // Новый сотрудник, для него цвет сгенерируется автоматически!
          start: '2026-04-06', // Неделя 15
          end: '2026-04-19',   // Неделя 16
        },
        {
          id: '2-2',
          task: 'Интеграция UI компонентов',
          duration: '12 дней',
          progress: 0,
          responsible: 'Анна',
          start: '2026-04-22', // Среда (Неделя 17) -> Начнется со смещением внутри ячейки
          end: '2026-05-03',   // Воскресенье (Неделя 18)
        }
      ]
    },
    {
      id: '3',
      task: 'Этап 3. Тестирование и Релиз',
      duration: '10 дней',
      progress: 0,
      children: [
        {
          id: '3-1',
          task: 'QA Автоматизация',
          duration: '10 дней',
          progress: 0,
          responsible: 'Соня',
          start: '2026-05-11', // Неделя 20
          end: '2026-05-20',   // Неделя 21
        }
      ]
    },
    {
      id: '4',
      task: 'Этап 5. Деплой',
      duration: '5 дней',
      progress: 0,
      children: [
        {
          id: '4-1',
          task: 'QA Автоматизация',
          duration: '10 дней',
          progress: 0,
          responsible: 'Соня',
          start: '2026-05-11', // Неделя 20
          end: '2026-05-20',   // Неделя 21
        }
      ]
    },
    {
      id: '5',
      task: 'Этап 6. Правки',
      duration: '7 дней',
      progress: 0,
      children: [
        {
          id: '5-1',
          task: 'QA Автоматизация',
          duration: '10 дней',
          progress: 0,
          responsible: 'Соня',
          start: '2026-05-11', // Неделя 20
          end: '2026-05-20',   // Неделя 21
        }
      ]
    }
  ],
};

export const mockProjectInsightsData: InsightItem[] = [
  {
    id: 1,
    type: 'error',
    text: 'Критический сбой процессов: в текущем проекте просрочено 6 задач, а основной CI/CD пайплайн сломан уже 8 часов. Дополнительно зафиксирован Bus Factor 92% на модуле авторизации.',
    recommendation: 'Рекомендация: Срочно перенаправить дежурного инженера на стабилизацию сборки и распределить просроченные задачи.',
  },
  {
    id: 2,
    type: 'warning',
    text: 'Риск срыва сроков: зафиксировано отставание от календарного графика спринта на 3 дня. Обнаружен застой в код-ревью — 4 важных PR висят без внимания команды.',
    recommendation: 'Рекомендация: Проверить текущую загрузку Николая, снизить с него фокус и назначить на застрявшие PR дополнительного ревьюера.',
  },
  {
    id: 3,
    type: 'success',
    text: 'Показатели стабильности: общая готовность текущего спринта составляет 78%. Команда движется по графику в рамках релизного окна.',
    recommendation: 'Доступные резервы: Ольга (загрузка 0.4), обладает компетенциями для подключения к активным задачам текущего этапа.',
  },
];