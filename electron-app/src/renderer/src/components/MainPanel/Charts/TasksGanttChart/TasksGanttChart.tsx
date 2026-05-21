import { Table, Progress, Tooltip } from 'antd';
import s from './TasksGanttChart.module.css';
import isBetween from 'dayjs/plugin/isBetween';
import isoWeek from 'dayjs/plugin/isoWeek';
import dayjs from 'dayjs';

interface GanttRecord {
  id: string;
  task: string;
  duration: string;
  progress: number;
  start?: string;
  end?: string;
  responsible?: string;
  children?: GanttRecord[];
}

dayjs.extend(isBetween);
dayjs.extend(isoWeek);

const RESPONSIBLE_COLORS: Record<string, string> = {
  'Соня': '#36cfc9',
  'Иван': '#ff4d4f',
  'Анна': '#ffc53d',
  'default': '#1890ff'
};



const generateGanttColumns = (startDate: string, endDate: string) => {
  // Начинаем с начала недели (понедельник), чтобы сетка была ровной
  let currentWeekStart = dayjs(startDate).startOf('week').add(0, 'day');
  const endLimit = dayjs(endDate);

  const columns: any[] = [];

  // Итерируемся по неделям, пока не выйдем за пределы диапазона
  while (currentWeekStart.isBefore(endLimit)) {
    const sDate = currentWeekStart;
    const eDate = sDate.add(6, 'day');

    // Определяем, к какому месяцу относится эта неделя (по дате начала)
    const monthName = sDate.format('MMMM');
    const monthTitle = monthName.charAt(0).toUpperCase() + monthName.slice(1);

    // Ищем, есть ли уже колонка для этого месяца
    let monthColumn = columns.find(col => col.title === monthTitle);

    if (!monthColumn) {
      monthColumn = {
        title: monthTitle,
        children: [],
      };
      columns.push(monthColumn);
    }
    const weekOfYear = sDate.isoWeek();
    // Добавляем неделю внутрь месяца
    monthColumn.children.push({
      title: (
        <div className={s.weekHeader}>
          <div className={s.weekNum}>Неделя {weekOfYear}</div>
          <div className={s.weekDates}>{sDate.format('DD.MM')}-{eDate.format('DD.MM')}</div>
        </div>
      ),
      width: COLUMN_WIDTH,
      render: (_: any, record: GanttRecord) => {
        const taskStart = dayjs(record.start);

        // Рисуем полоску только если задача начинается именно в ЭТУ неделю
        const isStartWeek = taskStart.isBetween(sDate, eDate, 'day', '[]');

        if (isStartWeek && !record.children) {
          const taskEnd = dayjs(record.end);
          const durationDays = taskEnd.diff(taskStart, 'day') + 1;
          const startOffsetDays = taskStart.diff(sDate, 'day');

          const leftOffset = startOffsetDays * (COLUMN_WIDTH / 7);
          const totalWidth = durationDays * (COLUMN_WIDTH / 7);

          return (
            <div className={s.anchorCell}>
              <Tooltip
                title={
                  <div style={{ padding: '4px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{record.task}</div>
                    <div>Исполнитель: <b>{record.responsible}</b></div>
                    <div>Сроки: {taskStart.format('DD.MM')} - {taskEnd.format('DD.MM')}</div>
                    <div>Прогресс: {record.progress}%</div>
                  </div>
                }
              >
                <div
                  className={s.absoluteTaskBar}
                  style={{
                    left: leftOffset,
                    width: totalWidth,
                    backgroundColor: RESPONSIBLE_COLORS[record.responsible || 'default'],
                  }}
                >
                  {record.responsible}
                </div>
              </Tooltip>
            </div>
          );
        }
        return null;
      },
    });

    // Переходим к следующему понедельнику
    currentWeekStart = currentWeekStart.add(7, 'day');
  }

  return columns;
};

const fixedColumns = [
  { title: 'Задача', dataIndex: 'task', key: 'task', width: 120, fixed: 'left' as const },
  { title: 'Длительность', dataIndex: 'duration', key: 'duration', width: 130, fixed: 'left' as const },
  {
    title: 'Готовность',
    dataIndex: 'progress',
    width: 100,
    render: (p: number) => <Progress percent={p} size="small" />,
    fixed: 'left' as const
  },
];

const ganttData: GanttRecord[] = [
  {
    id: '1',
    task: 'Задача 1',
    duration: '10 дней',
    progress: 55,
    children: [
      { id: '1-1', task: 'Аналитика', duration: '3 дня', progress: 100, responsible: 'Соня', start: '2026-03-02', end: '2026-03-08' },
      { id: '1-2', task: 'Разработка', duration: '6 дней', progress: 20, responsible: 'Иван', start: '2026-03-09', end: '2026-03-25' },
      { id: '1-3', task: 'Тестирование', duration: '5 дней', progress: 3, responsible: 'Анна', start: '2026-03-18', end: '2026-03-24' },
    ]
  },
  {
    id: '2',
    task: 'Задача 2',
    duration: '12 дней',
    progress: 0,
    children: [
      { id: '2-1', task: 'Интеграция', duration: '3 дня', progress: 0, responsible: 'Анна', start: '2026-03-18', end: '2026-03-24' },
    ]
  },
  {
    id: '3',
    task: 'Задача 3',
    duration: '11 дней',
    progress: 0,
    children: [
      { id: '3-1', task: 'Интеграция', duration: '3 дня', progress: 0, responsible: 'Соня', start: '2026-03-18', end: '2026-04-24' },
    ]
  }
];

const COLUMN_WIDTH = 85;

export const TasksGanttChart = (viewRange = { start: '2026-03-01', end: '2026-07-31' }) => {
  const dynamicColumns = generateGanttColumns(viewRange.start, viewRange.end);

  const columns = [...fixedColumns, ...dynamicColumns];

  return (
    <div className={s.ganttCard}>
      <div className={s.header}>
        <h2 className={s.title}>ПЛАН ПО ЗАДАЧАМ</h2>
      </div>
      <div className={s.ganttContainer}>
        <Table
          className={s.ganttTable}
          rowKey="id"
          indentSize={0}
          columns={columns}
          dataSource={ganttData}
          pagination={false}
          bordered
          scroll={{ x: 'max-content' }}
        />
      </div>
    </div>
  );
};