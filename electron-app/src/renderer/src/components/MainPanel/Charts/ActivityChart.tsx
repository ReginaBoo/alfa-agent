import { Line } from '@ant-design/plots';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';

dayjs.locale('ru');

interface ActivityChartProps {
  backendData: any[]; // Замените на ваш тип, если есть (например, ProjectActivityItem[])
}

export const ActivityChart = ({ backendData }: ActivityChartProps) => {
  if (!backendData || backendData.length === 0) return null;

  const sortedData = [...backendData].sort((a, b) =>
    dayjs(a.date).unix() - dayjs(b.date).unix()
  );

  const config = {
    data: sortedData,
    xField: (d: any) => new Date(d.date),
    yField: 'value',
    colorField: 'project',

    // Включаем авто-ресайз графиков под размеры родительского DOM-элемента
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
    /* Этот инлайн-стиль — важнейшая часть для @ant-design/plots во флексбоксах.
      position: absolute заставляет график брать размеры контейнера .chartContainer из Dashboard.css,
      не раздувая его изнутри и не вызывая баг бесконечного роста высоты.
    */
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
      <Line {...config} />
    </div>
  );
};