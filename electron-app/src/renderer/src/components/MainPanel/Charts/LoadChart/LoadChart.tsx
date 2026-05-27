import { Column } from '@ant-design/plots';
import { Empty } from 'antd';
import { LoadChartItem } from '../../../../types/dashboard';
import s from './LoadChart.module.css';

interface LoadChartProps {
  backendData: LoadChartItem[];
}

export const LoadChart = ({ backendData }: LoadChartProps) => {
  if (!Array.isArray(backendData) || !backendData || backendData.length === 0) {
    return <Empty description="Нет данных по загруженности" />;
  }

  const colorMap = {
    underload: '#F27A41', // Недогруз
    optimal: '#13C2C2',   // Оптимально
    high: '#FADB14',      // Повышенная
    overload: '#FF4D4F',  // Перегруз
  };

  const config = {
    data: backendData,
    xField: 'project',
    yField: 'load',

    scale: {
      y: {
        domain: [0, 2], // От 0 до 2, чтобы 1.0 была ровно по центру
        tickCount: 5,
      },
    },

    axis: {
      y: {
        labelFormatter: (v: number) => v === 1 ? '1,0' : v.toString().replace('.', ','),
      },
    },

    style: {
      fill: (datum: LoadChartItem) => colorMap[datum.statusType] || '#13C2C2',
      maxWidth: 40,
      radiusTopLeft: 8,
      radiusTopRight: 8,
      zIndex: 10,
    },

    tooltip: {
      items: [
        (datum: LoadChartItem) => ({
          name: 'Загрузка',
          value: `${(datum.load * 100).toFixed(0)}%`,
        }),
        (datum: LoadChartItem) =>
          datum.description
            ? {
              name: 'Описание',
              value: datum.description,
            }
            : null,
      ],
    },
    legend: false,
  };

  return (
    <div className={s.chartContainer}>
      <div className={s.chartCanvasWrapper}>
        <div className={s.gridLineTop} />
        <div className={s.gridLineBottom} />

        <Column {...config} />
      </div>

      {/* HTML-Легенда */}
      <div className={s.legendContainer}>
        <div className={s.legendItem}>
          <div className={s.legendMarker} style={{ backgroundColor: colorMap.overload }} />
          <span>Перегруз</span>
        </div>
        <div className={s.legendItem}>
          <div className={s.legendMarker} style={{ backgroundColor: colorMap.high }} />
          <span>Повышенная</span>
        </div>
        <div className={s.legendItem}>
          <div className={s.legendMarker} style={{ backgroundColor: colorMap.optimal }} />
          <span>Оптимально</span>
        </div>
        <div className={s.legendItem}>
          <div className={s.legendMarker} style={{ backgroundColor: colorMap.underload }} />
          <span>Недогруз</span>
        </div>
      </div>
    </div>
  );
};
