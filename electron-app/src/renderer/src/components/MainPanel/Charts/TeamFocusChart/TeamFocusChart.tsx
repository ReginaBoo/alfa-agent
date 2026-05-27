import { Pie } from '@ant-design/plots';
import s from './TeamFocusChart.module.css';
import { FocusCategory } from '../../../../types/dashboard';

interface TeamFocusChartProps {
  categories: FocusCategory[];
}

// Наша фиксированная фронтовая палитра для графика
const FOCUS_PALETTE = [
  '#10B981', // 1-я категория
  '#F59E0B', // 2-я категория
  '#3B82F6', // 3-я категория
  '#8B5CF6', // 4-я категория
  '#EC4899', // 5-я категория
  '#6B7280', // 6-я категория
];

export const TeamFocusChart = ({ categories }: TeamFocusChartProps) => {
  if (categories.length === 0) return null;

  // 1. Создаем жесткую карту "Категория -> Цвет"
  const dynamicColorsMap = categories.reduce<Record<string, string>>((acc, item, index) => {
    acc[item.type] = FOCUS_PALETTE[index % FOCUS_PALETTE.length];
    return acc;
  }, {});

  const config = {
    data: categories,
    angleField: 'value',
    colorField: 'type',

    // 2. В версиях Ant Design Plots (v4 / v5) явное сопоставление цветов делается через scale
    scale: {
      color: {
        domain: categories.map(c => c.type), // Список ключей из бэка
        range: categories.map((_, i) => FOCUS_PALETTE[i % FOCUS_PALETTE.length]), // Список цветов
      },
    },

    // На случай, если у тебя старая версия v4 (отказоустойчивость):
    legend: false,
    tooltip: false,
    radius: 1,
    innerRadius: 0.75,
  };

  return (
    <div className={s.card}>
      <div className={s.content}>
        <div className={s.chartWrapper}>
          <Pie {...config} />
        </div>

        <div className={s.legend}>
          {categories.map((item) => {
            // 3. Легенда берет цвет строго по имени категории из мапы
            const itemColor = dynamicColorsMap[item.type];

            return (
              <div key={item.type} className={s.legendItem}>
                <span
                  className={s.dot}
                  style={{ backgroundColor: itemColor }}
                />
                <span className={s.percent}>{item.value}%</span>
                <span className={s.label}>{item.type}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};