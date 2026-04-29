import { List, Typography, Card } from 'antd';
import s from './Notifications.module.css';

const { Text } = Typography;

const mockData = [
  { id: 1, source: 'Проект 1', task: 'просрочено 6 задач, CI/CD сломан уже 8 часов. Проект «CRM»: обнаружен Bus Factor 92% на модуле авторизации', status: 'New' },
  { id: 2, source: 'Проект 3', task: 'Merge conflict в ветке feature/fuel-logic', status: 'Alert' },
  { id: 3, source: 'Проект 4', task: 'В проекте высокий риск срыва спринта (отставание на 3 дня). Обнаружен застой — 4 PR висят без ревью.', status: 'Warning' },
  { id: 4, source: 'Проект 2', task: 'Ситуация стабильная. Все проекты идут по плану. Общая готовность спринтов — 78%.', status: 'New' },

];

export const Notifications = () => {
  const getStatusClass = (status: string) => {
    switch (status) {
      case 'Alert': return s.statusAlert;
      case 'Warning': return s.statusWarning;
      default: return s.statusDefault;
    }
  };

  return (
    <div className={s.container}>
      <List
        split={false}
        dataSource={mockData}
        renderItem={(item) => (
          <Card
            size="small"
            className={`${s.notificationCard} ${getStatusClass(item.status)}`}
          >
            <div className={s.header}>
              <Text className={s.sourceText} strong>
                {item.source}
              </Text>
            </div>
            <div style={{ marginTop: 4 }}>
              <Text className={s.taskText}>
                {item.task}
              </Text>
            </div>

          </Card>
        )}
      />
    </div>
  );
};