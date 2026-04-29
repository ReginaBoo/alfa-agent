import { Line } from '@ant-design/plots';
import dayjs from 'dayjs';
import 'dayjs/locale/ru';

dayjs.locale('ru');

export const ActivityChart = ({ backendData }) => {
  if (!backendData || backendData.length === 0) return null;

  const sortedData = [...backendData].sort((a, b) =>
    dayjs(a.date).unix() - dayjs(b.date).unix()
  );

  const config = {
    data: sortedData,
    xField: (d) => new Date(d.date),
    yField: 'value',
    colorField: 'project',


    axis: {
      x: {
        title: false,
        labelFormatter: (date) => {
          const d = dayjs(date);
          return d.date() <= 7 ? d.format('MMMM') : `н${Math.ceil(d.date() / 7)}`;
        },
      },
      y: { title: false }
    },

    slider: {
      x: {
        labelFormatter: (date) => dayjs(date).format('MMM'),
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

  return <Line {...config} />;
};