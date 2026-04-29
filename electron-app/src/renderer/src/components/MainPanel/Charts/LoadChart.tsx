import { Column } from '@ant-design/plots';

export const LoadChart = () => {
  const data = [
    { project: 'Проект 1', load: 0.85 },
    { project: 'Проект 2', load: 0.60 },
    { project: 'Проект 3', load: 0.75 },
    { project: 'Проект 4', load: 0.25 },
  ];

  const config = {
    data,
    xField: 'project',
    yField: 'load',
    tooltip: {
      name: 'Загрузка', // Здесь меняем отображаемое имя
      channel: 'y',     // Указываем, что менять имя нужно для оси Y
      valueFormatter: (val: number) => (val * 100).toFixed(0) + '%', // Сразу форматируем в проценты
    },
    style: {
      fill: ({ load }: { load: number }) => {
        if (load >= 0.8) return '#FF4D4F';
        if (load >= 0.6) return '#597EF7';
        if (load >= 0.4) return '#2F54EB';
        return '#ADC6FF';
      },
      maxWidth: 50,
      radiusTopLeft: 10,
      radiusTopRight: 10,
    },
    legend: false,
  };

  return (
    <div style={{ height: '200px' }}>
      <Column {...config} />
    </div>
  );
};