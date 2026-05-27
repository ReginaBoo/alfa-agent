import React, { useMemo } from 'react';
import { Table, Progress, Tooltip } from 'antd';
import s from './TasksGanttChart.module.css';
import isBetween from 'dayjs/plugin/isBetween';
import isoWeek from 'dayjs/plugin/isoWeek';
import dayjs from 'dayjs';

dayjs.extend(isBetween);
dayjs.extend(isoWeek);

export interface GanttRecord {
  id: string;
  task: string;
  duration: string;
  progress: number;
  start?: string;
  end?: string;
  responsible?: string;
  children?: GanttRecord[];
}

interface TasksGanttChartProps {
  data: GanttRecord[];
  viewRange: {
    start: string;
    end: string;
  };
}

const COLUMN_WIDTH = 85;

// Утилита генерации мягкого пастельного цвета по имени (Хеширование строки)
const generateColorByName = (name: string): string => {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  // Распределяем оттенки по кругу HSL, сохраняя приятную насыщенность и яркость
  const hue = Math.abs(hash % 360);
  return `hsl(${hue}, 75%, 60%)`;
};

const generateGanttColumns = (
  startDate: string,
  endDate: string,
  colorMap: Record<string, string>
) => {
  let currentWeekStart = dayjs(startDate).startOf('isoWeek');
  const endLimit = dayjs(endDate);
  const columns: any[] = [];

  while (currentWeekStart.isBefore(endLimit)) {
    const sDate = currentWeekStart;
    const eDate = sDate.add(6, 'day');

    const monthName = sDate.format('MMMM');
    const monthTitle = monthName.charAt(0).toUpperCase() + monthName.slice(1);

    let monthColumn = columns.find(col => col.title === monthTitle);

    if (!monthColumn) {
      monthColumn = {
        title: monthTitle,
        children: [],
      };
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
      onCell: () => ({
        className: s.timelineCell
      }),
      render: (_: any, record: GanttRecord) => {
        if (record.children || !record.start || !record.end) return null;

        const taskStart = dayjs(record.start);
        const taskEnd = dayjs(record.end);

        const isTaskInWeek = !(taskEnd.isBefore(sDate, 'day') || taskStart.isAfter(eDate, 'day'));

        if (isTaskInWeek) {
          const startInWeek = taskStart.isBefore(sDate, 'day') ? sDate : taskStart;
          const endInWeek = taskEnd.isAfter(eDate, 'day') ? eDate : taskEnd;

          const daysActiveInWeek = endInWeek.diff(startInWeek, 'day') + 1;
          const offsetDays = startInWeek.diff(sDate, 'day');

          const leftPercent = (offsetDays / 7) * 100;
          const widthPercent = (daysActiveInWeek / 7) * 100;

          const isActualStart = taskStart.isBetween(sDate, eDate, 'day', '[]');
          const isActualEnd = taskEnd.isBetween(sDate, eDate, 'day', '[]');

          // Показываем имя ТОЛЬКО в первой неделе задачи (когда taskStart попадает в эту неделю)
          const isFirstWeekOfTask = taskStart.isSame(sDate, 'day') || taskStart.isAfter(sDate, 'day');
          const showResponsibleName = isFirstWeekOfTask && widthPercent >= 15 && record.responsible && record.responsible !== 'Не назначен';

          const responsibleName = record.responsible || 'default';
          const barColor = colorMap[responsibleName];

          return (
            <div className={s.anchorCell}>
              <Tooltip
                title={
                  <div style={{ padding: '8px', minWidth: '200px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '8px', fontSize: 14 }}>{record.task}</div>
                    <div style={{ marginBottom: '4px' }}>
                      <span style={{ color: '#666' }}>Исполнитель:</span>{' '}
                      <b>{record.responsible || 'Не назначен'}</b>
                    </div>
                    <div style={{ marginBottom: '4px' }}>
                      <span style={{ color: '#666' }}>Сроки:</span>{' '}
                      {taskStart.format('DD.MM')} - {taskEnd.format('DD.MM')}
                    </div>
                    <div style={{ marginBottom: '4px' }}>
                      <span style={{ color: '#666' }}>Прогресс:</span>{' '}
                      {record.progress}%
                    </div>
                    <div>
                      <span style={{ color: '#666' }}>Длительность:</span>{' '}
                      {record.duration}
                    </div>
                  </div>
                }
              >
                <div
                  className={s.absoluteTaskBar}
                  style={{
                    left: `${leftPercent}%`,
                    width: `${widthPercent}%`,
                    backgroundColor: barColor,
                    borderRadius: `
                      ${isActualStart ? '6px' : '0px'}
                      ${isActualEnd ? '6px' : '0px'}
                      ${isActualEnd ? '6px' : '0px'}
                      ${isActualStart ? '6px' : '0px'}
                    `,
                  }}
                >
                  {/* Показываем имя только в первой неделе задачи */}
                  {showResponsibleName && (
                    <span style={{
                      fontSize: 10,
                      color: 'white',
                      fontWeight: 500,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      padding: '0 4px',
                      display: 'block',
                      textAlign: 'center',
                      lineHeight: '20px',
                      textShadow: '0 1px 2px rgba(0,0,0,0.3)'
                    }}>
                      {record.responsible}
                    </span>
                  )}
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
    width: 250, // Увеличил с 160 до 250 для имени исполнителя
    fixed: 'left' as const,
    ellipsis: true,
    render: (text: string, record: GanttRecord) => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <Tooltip
          title={text}
          placement="topRight"
          mouseEnterDelay={0.3}
        >
          <span style={{ cursor: 'pointer', fontWeight: 500 }}>{text}</span>
        </Tooltip>
        {/* Показываем исполнителя прямо в колонке */}
        {record.responsible && record.responsible !== 'Не назначен' && (
          <span style={{ fontSize: 11, color: '#666', fontWeight: 400 }}>
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
    width: 110,
    fixed: 'left' as const,
    ellipsis: true,
    render: (text: string) => <span title={text}>{text}</span>
  },
  {
    title: 'Готовность',
    dataIndex: 'progress',
    width: 100,
    render: (p: number) => <Progress percent={p} size="small" />,
    fixed: 'left' as const
  },
];

export const TasksGanttChart: React.FC<TasksGanttChartProps> = ({ data, viewRange }) => {
  // Динамически собираем карту цветов для всех уникальных исполнителей из пришедших данных
  const autoResponsibleColors = useMemo(() => {
    const colors: Record<string, string> = { default: '#1890ff' };

    const extractResponsibles = (records: GanttRecord[]) => {
      records.forEach(item => {
        if (item.responsible && !colors[item.responsible]) {
          colors[item.responsible] = generateColorByName(item.responsible);
        }
        if (item.children) {
          extractResponsibles(item.children);
        }
      });
    };

    extractResponsibles(data);
    return colors;
  }, [data]);

  const dynamicColumns = useMemo(() => {
    return generateGanttColumns(viewRange.start, viewRange.end, autoResponsibleColors);
  }, [viewRange.start, viewRange.end, autoResponsibleColors]);

  const columns = useMemo(() => [...fixedColumns, ...dynamicColumns], [dynamicColumns]);

  return (
    <div className={s.ganttCard}>
      <div className={s.ganttContainer}>
        <Table
          className={s.ganttTable}
          rowKey="id"
          indentSize={20}
          columns={columns}
          dataSource={data}
          pagination={false}
          bordered
          scroll={{
            x: 'max-content',
            y: 380
          }}
        />
      </div>
    </div>
  );
};
