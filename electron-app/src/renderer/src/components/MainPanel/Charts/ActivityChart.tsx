import { Line } from '@ant-design/plots';
import { useEffect, useRef, useState } from 'react';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';

dayjs.locale('ru');

interface ActivityChartProps {
  backendData: any[];
}

export const ActivityChart = ({ backendData }: ActivityChartProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  // Локальный стейт для триггера ререндера при изменении размеров
  const [, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    if (!containerRef.current) return;

    // Создаем наблюдатель за размерами нашего контейнера
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        // Записываем новые размеры, что заставит React обновить график под новые габариты
        setDimensions({ width, height });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  if (!backendData || backendData.length === 0) return null;

  const sortedData = [...backendData].sort((a, b) =>
    dayjs(a.date).unix() - dayjs(b.date).unix()
  );

  const config = {
    data: sortedData,
    xField: (d: any) => new Date(d.date),
    yField: 'value',
    colorField: 'project',

    // Обязательно оставляем true
    autoFit: true,

    axis: {
      x: {
        title: false,
        labelFormatter: (date: any) => {
          const d = dayjs(date);
          return d.date() <= 7 ? d.format('MMMM') : `н${Math.ceil(d.date() / 7)}`;
        },
      },
      y: { title: false }
    },

    slider: {
      x: {
        labelFormatter: (date: any) => dayjs(date).format('MMM'),
      },
    },

    scale: {
      x: { type: 'time' },
      y: { nice: true, min: 0 },
    },

    style: {
      lineWidth: 2.5,
    },

    color: ['#3460DC', '#00C2C2', '#52C41A', '#FF4D4F'],

    interaction: {
      tooltip: { shared: true, showMarkers: true },
    },
  };

  return (
    <div
      ref={containerRef}
      style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, width: '100%', height: '100%' }}
    >
      <Line {...config} />
    </div>
  );
};