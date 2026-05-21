import { WarningOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import s from './CycleTimeChart.module.css';

// Данные могут приходить с бэка в таком формате
const stages = [
  { id: '1', label: 'Аналитика', hours: 10, color: '#D6E4FF', warning: true, tooltip: 'Затронуто много файлов (>15)' },
  { id: '2', label: 'Код', hours: 25, color: '#FFD8BF', tooltip: 'Код часто переписывается' },
  { id: '3', label: 'Ожидание ревью', hours: 50, color: '#597EF7' },
  { id: '4', label: 'Тестирование', hours: 15, color: '#BAE7FF' },
  { id: '5', label: 'Бизнес-тестирование', hours: 12, color: '#FF7875' },
  { id: '6', label: 'Внедрение', hours: 18, color: '#2F54EB' },
];

export const CycleTimeChart = () => {
  const totalHours = stages.reduce((acc, stage) => acc + stage.hours, 0);

  return (
    <div className={s.container}>
      <div className={s.chartWrapper}>
        {stages.map((stage) => {
          const widthPercent = (stage.hours / totalHours) * 100;
          return (
            <Tooltip
              key={stage.id}
              title={stage.tooltip || `${stage.label}: ${stage.hours}ч`}
              color="white"
            >
              <div
                className={s.stageBlock}
                style={{
                  width: `${widthPercent}%`,
                  backgroundColor: stage.color,
                  zIndex: stages.length - stages.indexOf(stage)
                }}
              >
                <span className={s.hoursLabel}>{stage.hours}ч</span>
                {stage.warning && <WarningOutlined className={s.warningIcon} />}
              </div>
            </Tooltip>
          );
        })}
      </div>

      {/* Легенда */}
      <div className={s.legend}>
        {stages.map(stage => (
          <div key={stage.id} className={s.legendItem}>
            <span className={s.dot} style={{ backgroundColor: stage.color }} />
            <span className={s.legendLabel}>{stage.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};