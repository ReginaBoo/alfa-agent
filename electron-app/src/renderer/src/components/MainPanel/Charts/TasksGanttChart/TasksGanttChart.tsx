import React, { useMemo } from 'react';
import { Table, Progress, Tooltip } from 'antd';
import s from './TasksGanttChart.module.css';
import isBetween from 'dayjs/plugin/isBetween';
import isoWeek from 'dayjs/plugin/isoWeek';
import dayjs from 'dayjs';
import { GanttRecord, ViewRange } from '../../../../types/dashboard';

dayjs.extend(isBetween);
dayjs.extend(isoWeek);

interface TasksGanttChartProps {
  data: GanttRecord[];
  viewRange: ViewRange;
}

const COLUMN_WIDTH = 85;

const DISTINCT_COLORS = [
  '#1890ff', // Ярко-синий
  '#13c2c2', // Бирюзовый
  '#fa8c16', // Оранжевый
  '#722ed1', // Фиолетовый
  '#eb2f96', // Насыщенный розовый
  '#faad14', // Песочно-желтый
  '#2f54eb', // Индиго
  '#fa541c', // Кирпично-красный
  '#a0d911', // Салатовый
  '#135200', // Темно-зеленый
  '#00474f', // Глубокий сине-зеленый
  '#b37feb', // Светло-пурпурный
];

// Дефолтный цвет для неназначенных задач
const UNASSIGNED_COLOR = '#8c8c8c'; // Спокойный серый (идеально для "Не назначен")

const generateColorMap = (records: GanttRecord[]): Record<string, string> => {
  const colors: Record<string, string> = {
    'default': '#1890ff',
    'Не назначен': UNASSIGNED_COLOR
  };

  // Собираем ТОЛЬКО уникальных реальных сотрудников
  const uniqueNames = new Set<string>();

  const extractResponsibles = (dataList: GanttRecord[]) => {
    dataList.forEach(item => {
      if (item.responsible && item.responsible !== 'Не назначен') {
        uniqueNames.add(item.responsible);
      }
      if (item.children) extractResponsibles(item.children);
    });
  };

  extractResponsibles(records);

  // Распределяем контрастные цвета из палитры
  Array.from(uniqueNames).forEach((name, index) => {
    const colorIndex = index % DISTINCT_COLORS.length;
    colors[name] = DISTINCT_COLORS[colorIndex];
  });

  return colors;
};

const generateGanttColumns = (
  startDate: string,
  endDate: string,
  colorMap: Record<string, string>
) => {
  const timelineStart = dayjs(startDate).startOf('isoWeek');
  const timelineEnd = dayjs(endDate);

  let currentWeekStart = timelineStart;
  const columns: any[] = [];

  while (currentWeekStart.isBefore(timelineEnd)) {
    const sDate = currentWeekStart;
    const eDate = sDate.add(6, 'day');

    const monthName = sDate.format('MMMM');
    const monthTitle = monthName.charAt(0).toUpperCase() + monthName.slice(1);

    let monthColumn = columns.find(col => col.title === monthTitle);

    if (!monthColumn) {
      monthColumn = { title: monthTitle, children: [] };
      columns.push(monthColumn);
    }

    const weekOfYear = sDate.isoWeek();

    monthColumn.children.push({
      title: (
        <div className={s.weekHeader}>
          <div className={s.weekNum}>Неделя {weekOfYear}</div>
          <div className={s.weekDates}>{sDate.format('DD.MM')}-{eDate.format('DD.MM')}</div>
        </div>
      ),
      width: COLUMN_WIDTH,
      onCell: () => ({ className: s.timelineCell }),
      render: (_: any, record: GanttRecord) => {
        if (record.children || !record.start || !record.end) return null;

        const taskStart = dayjs(record.start);
        const taskEnd = dayjs(record.end);

        if (taskEnd.isBefore(timelineStart, 'day') || taskStart.isAfter(timelineEnd, 'day')) {
          return null;
        }

        const visibleStart = taskStart.isBefore(timelineStart, 'day') ? timelineStart : taskStart;
        const visibleEnd = taskEnd.isAfter(timelineEnd, 'day') ? timelineEnd : taskEnd;

        const isStartColumn = visibleStart.isBetween(sDate, eDate, 'day', '[]');

        if (isStartColumn) {
          const offsetDays = visibleStart.diff(sDate, 'day');
          const totalVisibleDays = visibleEnd.diff(visibleStart, 'day') + 1;

          const leftPercent = (offsetDays / 7) * 100;
          const widthPercent = (totalVisibleDays / 7) * 100;

          const isCutLeft = taskStart.isBefore(timelineStart, 'day');
          const isCutRight = taskEnd.isAfter(timelineEnd, 'day');

          const responsibleName = record.responsible || 'Не назначен';
          const barColor = colorMap[responsibleName] || colorMap['default'];

          return (
            <div className={s.anchorCell}>
              <Tooltip
                title={
                  <div style={{ padding: '4px', minWidth: '180px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '6px' }}>{record.task}</div>
                    <div><span style={{ color: '#aaa' }}>Исполнитель:</span> {responsibleName}</div>
                    <div><span style={{ color: '#aaa' }}>Сроки:</span> {taskStart.format('DD.MM')} - {taskEnd.format('DD.MM')}</div>
                    {record.isOverdue && record.overdueSince && (
                      <div style={{ color: '#ff4d4f' }}>Просрочена с {dayjs(record.overdueSince).format('DD.MM.YYYY')}</div>
                    )}
                    <div><span style={{ color: '#aaa' }}>Прогресс:</span> {record.progress}%</div>
                  </div>
                }
              >
                <div
                  className={`${s.absoluteTaskBar} ${record.isOverdue ? s.overdueTask : ''}`}
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                    backgroundColor: barColor,
                    borderRadius: `${isCutLeft ? '0' : '4px'} ${isCutRight ? '0' : '4px'} ${isCutRight ? '0' : '4px'} ${isCutLeft ? '0' : '4px'}`
                  }}
                >
                  <span className={s.barText}>
                    {responsibleName !== 'Не назначен' ? responsibleName : ''}
                  </span>
                </div>
              </Tooltip>
            </div>
          );
        }

        return null;
      },
    });

    currentWeekStart = currentWeekStart.add(7, 'day');
  }

  return columns;
};

const fixedColumns = [
  {
    title: 'Задача',
    dataIndex: 'task',
    key: 'task',
    width: 160,
    fixed: 'left' as const,
    ellipsis: true,
    render: (text: string, record: GanttRecord) => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, width: '100%', overflow: 'hidden' }}>
        <Tooltip title={text} placement="topRight" mouseEnterDelay={0.3}>
          <span style={{ cursor: 'pointer', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>
            {text}
          </span>
        </Tooltip>
        {record.responsible && record.responsible !== 'Не назначен' && (
          <span style={{ fontSize: 11, color: '#666', fontWeight: 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', display: 'block' }}>
            {record.responsible}
          </span>
        )}
      </div>
    )
  },
  {
    title: 'Длительность',
    dataIndex: 'duration',
    key: 'duration',
    width: 80,
    fixed: 'left' as const,
    ellipsis: true,
    render: (text: string) => <span title={text}>{text}</span>
  },
  {
    title: 'Готовность',
    dataIndex: 'progress',
    width: 90,
    render: (p: number) => <Progress percent={p} size="small" />,
    fixed: 'left' as const
  }
];

export const TasksGanttChart: React.FC<TasksGanttChartProps> = ({ data, viewRange }) => {

  // Карта цветов сотрудников
  const autoResponsibleColors = useMemo(() => {
    return generateColorMap(data);
  }, [data]);

  // Вытаскиваем список сотрудников для отображения в легенде (исключая системный дефолт)
  const legendItems = useMemo(() => {
    return Object.keys(autoResponsibleColors).filter(name => name !== 'default');
  }, [autoResponsibleColors]);

  const dynamicColumns = useMemo(() => {
    return generateGanttColumns(viewRange.start, viewRange.end, autoResponsibleColors);
  }, [viewRange.start, viewRange.end, autoResponsibleColors]);

  const columns = useMemo(() => [...fixedColumns, ...dynamicColumns], [dynamicColumns]);

  return (
    <div className={s.ganttCard}>
      {/* Секция Легенды */}
      {legendItems.length > 0 && (
        <div className={s.legendWrapper}>
          <span className={s.legendTitle}>Исполнители:</span>
          <div className={s.legendContainer}>
            {legendItems.map(name => (
              <div key={name} className={s.legendItem}>
                <span
                  className={s.legendColorBadge}
                  style={{ backgroundColor: autoResponsibleColors[name] }}
                />
                <span className={s.legendName}>{name}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className={s.ganttContainer}>
        <Table
          className={s.ganttTable}
          rowKey="id"
          indentSize={20}
          columns={columns}
          dataSource={data}
          pagination={false}
          bordered
          scroll={{ x: 'max-content', y: 380 }}
        />
      </div>
    </div>
  );
};