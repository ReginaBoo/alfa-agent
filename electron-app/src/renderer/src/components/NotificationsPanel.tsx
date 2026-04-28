import { List, Typography, Badge, Card } from 'antd';

const { Text } = Typography;

const mockData = [
  { id: 1, source: 'Jira', task: 'Разработка API для курьеров', status: 'New' },
  { id: 2, source: 'Git', task: 'Merge conflict в ветке feature/fuel-logic', status: 'Alert' },
  { id: 3, source: 'System', task: 'Бензин на станции №8 заканчивается', status: 'Warning' },
];

export const Notifications = () => {
  return (
    <div style={{ padding: '12px' }}>
      <List
        itemLayout="vertical"
        dataSource={mockData}
        renderItem={(item) => (
          <Card size="small" style={{ marginBottom: 8, borderRadius: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text strong>{item.source}</Text>
              <Badge status={item.status === 'Alert' ? 'error' : 'processing'} text={item.status} />
            </div>
            <div style={{ marginTop: 4 }}>
              <Text type="secondary">{item.task}</Text>
            </div>
          </Card>
        )}
      />
    </div>
  );
};