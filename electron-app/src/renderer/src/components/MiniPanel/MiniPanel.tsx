import { useState } from 'react';
import { Header } from './Header/Header';
import { Tabs, Card, Button, Typography } from 'antd';
import { Notifications } from './Notifications/Notifications';
import { ChatBot } from './ChatBot/ChatBot';
import s from './MiniPanel.module.css';

const { Title, Text } = Typography;

interface MiniPanelProps {
  authorized?: boolean;
  handleLogin?: () => Promise<void>;
  isLoggingIn?: boolean;
}

export const MiniPanel = ({ authorized = true, handleLogin, isLoggingIn = false }: MiniPanelProps) => {
  const [activeTab, setActiveTab] = useState('1');

  // Выносим заглушку в отдельную переменную, чтобы не дублировать код в табах
  const renderAuthPlaceholder = () => (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', padding: '24px 16px' }}>
      <Card style={{ maxWidth: 400, textAlign: 'center', width: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}>
        <Title level={4}>Приветствуем!</Title>
        <Text type="secondary">Авторизуйтесь для начала работы </Text>
        {handleLogin && (
          <Button type="primary" onClick={handleLogin} loading={isLoggingIn} style={{ marginTop: 20, width: '100%' }}>
            Авторизоваться
          </Button>
        )}
      </Card>
    </div>
  );

  return (
    <div className={s.appContainer}>
      {/* Шапка всегда на месте и доступна */}
      <Header onTabChange={(key) => setActiveTab(key)} />

      <main className={s.contentArea}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          renderTabBar={() => <></>}
          animated={{ inkBar: true, tabPane: true }}
          items={[
            {
              key: '1',
              label: '',
              // Если авторизован — показываем Уведомления, если нет — заглушку авторизации
              children: authorized ? <Notifications /> : renderAuthPlaceholder()
            },
            {
              key: '2',
              label: '',
              // То же самое для Чата
              children: authorized ? <ChatBot /> : renderAuthPlaceholder()
            },
          ]}
        />
      </main>
    </div>
  );
};