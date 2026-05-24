import { Typography, Empty } from 'antd';
import { InfoCircleOutlined, FlagFilled, CheckCircleOutlined } from '@ant-design/icons';
import s from './AIInsights.module.css';
import { InsightItem } from '../../../../types/dashboard'
const { Text } = Typography;


interface AIInsightsProps {
  variant?: 'compact' | 'detailed';
  data: InsightItem[];
}

export const AIInsights = ({ variant = 'compact', data }: AIInsightsProps) => {
  if (!data || data.length === 0) {
    return <Empty description="Нет доступных выводов" />;
  }

  return (
    <div className={`${s.insightsContainer} ${s[variant]}`}>
      {data.map((item) => (
        <div key={item.id} className={`${s.insightCard} ${s[item.type]}`}>
          <div className={s.contentRow}>
            <Text className={s.mainText}>{item.text}</Text>
            <div className={s.statusIcon}>{getIcon(item.type)}</div>
          </div>

          <div className={s.recommendationBox}>
            <div className={s.verticalLine} />
            <Text className={s.recommendationText}>{item.recommendation}</Text>
          </div>

        </div>
      ))}
    </div>
  );
};

const getIcon = (type: InsightItem['type']) => {
  switch (type) {
    case 'error':
      return <InfoCircleOutlined className={s.errorIcon} />;
    case 'warning':
      return <FlagFilled className={s.warningIcon} />;
    case 'success':
      return <CheckCircleOutlined className={s.successIcon} />;
    default:
      return null;
  }
};