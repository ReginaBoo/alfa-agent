import { Typography, Card, Spin, Empty } from 'antd';
import { useEffect, useState } from 'react';
import { dashboardApi } from '../../../api/dashboardApi';
import { InsightItem } from '../../../types/dashboard';
import s from './Notifications.module.css';

const { Text } = Typography;

// Функция для определения статуса на основе type
const getStatusClass = (type: string) => {
  switch (type?.toLowerCase()) {
    case 'error':
      return s.statusAlert;
    case 'warning':
      return s.statusWarning;
    default:
      return s.statusDefault;
  }
};

// Функция для получения иконки/типа уведомления
const getTypeLabel = (type: string) => {
  switch (type?.toLowerCase()) {
    case 'error':
      return 'Критично';
    case 'warning':
      return 'Внимание';
    case 'success':
      return 'Информация';
    default:
      return 'Уведомление';
  }
};

export const Notifications = () => {
  const [notifications, setNotifications] = useState<InsightItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      // Используем новый метод
      const data = await dashboardApi.getMiniPanelInsights();
      console.log('📊 Mini Panel insights:', data);
      setNotifications(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch insights:', err);
      setError('Не удалось загрузить инсайты');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 600000);
    return () => clearInterval(interval);
  }, []);

  if (loading && notifications.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
        <Spin tip="Загрузка инсайтов..." />
      </div>
    );
  }

  if (error && notifications.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
        <Empty description={error} />
      </div>
    );
  }

  if (notifications.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
        <Empty description="Нет инсайтов. Всё в порядке!" />
      </div>
    );
  }

  return (
    <div className={s.container}>
      <div className={s.listWrapper} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {notifications.map((item) => (
          <Card
            key={item.id}
            size="small"
            className={`${s.notificationCard} ${getStatusClass(item.type)}`}
          >
            <div className={s.header}>
              <Text className={s.sourceText} strong>
                AI Анализ
              </Text>
              <Text type="secondary" style={{ fontSize: 10 }}>
                {getTypeLabel(item.type)}
              </Text>
            </div>
            <div style={{ marginTop: 4 }}>
              <Text className={s.taskText}>
                {item.text}
              </Text>
            </div>
            {item.recommendation && (
              <div style={{ marginTop: 8, padding: 8, background: '#f5f5f5', borderRadius: 6 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {item.recommendation}
                </Text>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
};
