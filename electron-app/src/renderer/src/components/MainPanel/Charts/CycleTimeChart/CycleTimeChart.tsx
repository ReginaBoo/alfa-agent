import { WarningOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import s from './CycleTimeChart.module.css';
import { CycleStage } from '../../../../types/dashboard';

interface CycleTimeChartProps {
  stages: CycleStage[];
}

const STAGE_COLORS = [
  '#E6F7FF', // 1. Самый светлый (Аналитика)
  '#BAE7FF', // 2. Чуть темнее
  '#91D5FF', // 3. Средний голубой
  '#40A9FF', // 4. Насыщенный голубой
  '#1890FF', // 5. Яркий синий
  '#0050B3', // 6. Глубокий синий (Внедрение)
];
export const CycleTimeChart = ({ stages }: CycleTimeChartProps) => {
  const totalHours = stages.reduce((acc, stage) => acc + stage.hours, 0);

  if (stages.length === 0) return <div className={s.empty}>Нет данных</div>;

  return (
    <div className={s.container}>
      <div className={s.chartWrapper}>
        {stages.map((stage, index) => {
          const widthPercent = (stage.hours / totalHours) * 100;

          // Берём цвет из массива по индексу. 
          // Оператор % (остаток от деления) защитит, если этапов будет больше, чем цветов в массиве
          const blockColor = STAGE_COLORS[index % STAGE_COLORS.length];

          return (
            <Tooltip
              key={stage.id}
              title={stage.tooltip || `${stage.label}: ${stage.hours}ч`}
              color="white"
              overlayInnerStyle={{ color: '#000' }}
            >
              <div
                className={s.stageBlock}
                style={{
                  width: `${widthPercent}%`,
                  backgroundColor: blockColor,
                  zIndex: stages.length - index
                }}
              >
                <span className={s.hoursLabel}>{stage.hours}ч</span>
                {stage.warning && <WarningOutlined className={s.warningIcon} />}
              </div>
            </Tooltip>
          );
        })}
      </div>

      <div className={s.legend}>
        {stages.map((stage, index) => (
          <div key={stage.id} className={s.legendItem}>
            <span
              className={s.dot}
              style={{ backgroundColor: STAGE_COLORS[index % STAGE_COLORS.length] }}
            />
            <span className={s.legendLabel}>{stage.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};