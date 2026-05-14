import { Typography } from 'antd';
import { InfoCircleOutlined, FlagFilled, ArrowRightOutlined } from '@ant-design/icons';
import s from './AIInsights.module.css';

const { Text } = Typography;

interface Insight {
  id: number;
  type: 'error' | 'warning' | 'success';
  text: string;
  recommendation: string;
  icon?: React.ReactNode;
}

const insights: Insight[] = [
  {
    id: 1,
    type: 'error',
    text: 'Проект 1: просрочено 6 задач, CI/CD сломан уже 8 часов. Проект «CRM»: обнаружен Bus Factor 92% на модуле авторизации',
    recommendation: 'Рекомендация: Срочно перераспределить ресурсы в Проекте 3',
    icon: <InfoCircleOutlined className={s.errorIcon} />
  },
  {
    id: 2,
    type: 'warning',
    text: 'В проекте «Проект 2» высокий риск срыва спринта (отставание на 3 дня). Обнаружен застой — 4 PR висят без ревью.',
    recommendation: 'Рекомендация: Проверить загрузку Николая в Проект 2 и назначить дополнительного ревьюера в проект',
    icon: <FlagFilled className={s.warningIcon} />
  },
  {
    id: 3,
    type: 'success',
    text: 'Проект 3: Ситуация стабильная. Все проекты идут по плану. Общая готовность спринтов — 78%.',
    recommendation: 'Свободные ресурсы: Ольга (загрузка 0.4), можно подключить к активным задачам.',
  },
  {
    id: 4,
    type: 'success',
    text: 'Проект 4: Ситуация стабильная. Все проекты идут по плану. Общая готовность спринтов — 78%.',
    recommendation: 'Свободные ресурсы: Ольга (загрузка 0.4), можно подключить к активным задачам.',
  },
];

export const AIInsights = ({ variant = 'compact' }) => {
  return (
    <div className={`${s.insightsContainer} ${s[variant]}`}>
      {insights.map((item) => (
        <div key={item.id} className={`${s.insightCard} ${s[item.type]}`}>
          <div className={s.contentRow}>
            <Text className={s.mainText}>{item.text}</Text>
            {item.icon && <div className={s.statusIcon}>{item.icon}</div>}
          </div>

          <div className={s.recommendationBox}>
            <div className={s.verticalLine} />
            <Text className={s.recommendationText}>{item.recommendation}</Text>
          </div>

          <ArrowRightOutlined className={s.cornerArrow} />
        </div>
      ))}
    </div>
  );
};