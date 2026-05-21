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

          const responsibleName = record.responsible || 'default';
          const barColor = colorMap[responsibleName];

          return (
            <div className={s.anchorCell}>
              <Tooltip
                title={
                  <div style={{ padding: '4px' }}>
                    <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>{record.task}</div>
                    <div>Исполнитель: <b>{record.responsible || 'Не назначен'}</b></div>
                    <div>Сроки: {taskStart.format('DD.MM')} - {taskEnd.format('DD.MM')}</div>
                    <div>Прогресс: {record.progress}%</div>
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
                      ${isActualStart ? '8px' : '0px'} 
                      ${isActualEnd ? '8px' : '0px'} 
                      ${isActualEnd ? '8px' : '0px'} 
                      ${isActualStart ? '8px' : '0px'}
                    `,
                  }}
                >
                  {isActualStart && record.responsible}
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
    width: 160, // Можно слегка увеличить базовую ширину
    fixed: 'left' as const,
    ellipsis: true, // Включает автоматическое троеточие от Ant Design
    render: (text: string) => (
      <Tooltip
        title={text}
        placement="top"       /* Появляется сверху (можно "topLeft", "right" и т.д.) */
        mouseEnterDelay={0.3} /* Небольшая задержка в сек, чтобы не раздражать при быстром скролле */
      >
        <span style={{ cursor: 'pointer' }}>{text}</span>
      </Tooltip>
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
          indentSize={15}
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