import { Pie } from '@ant-design/plots';
import s from './TeamFocusChart.module.css';

export const TeamFocusChart = () => {
  const data = [
    { type: 'Новые фичи', value: 60, color: '#17b877' },
    { type: 'Рефактор/Долг', value: 25, color: '#f59e0b' },
    { type: 'Баги', value: 15, color: '#e5e7eb' },
  ];

  const config = {
    data,
    angleField: 'value',
    colorField: 'type',
    radius: 1,
    innerRadius: 0.75,
    legend: false,
    tooltip: false,
    state: {
      active: {
        status: 'active',
      },
    },
  };

  return (
    <div className={s.card}>
      <h2 className={s.title}>ФОКУС КОМАНДЫ</h2>

      <div className={s.content}>
        <div className={s.chartWrapper}>
          <Pie {...config} />
        </div>

        <div className={s.legend}>
          {data.map((item) => (
            <div key={item.type} className={s.legendItem}>
              <span
                className={s.dot}
                style={{ backgroundColor: item.color }}
              />
              <span className={s.percent}>{item.value}%</span>
              <span className={s.label}>{item.type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};