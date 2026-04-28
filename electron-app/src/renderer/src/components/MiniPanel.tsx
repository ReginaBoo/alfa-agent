import { useState } from 'react';
import { Header } from './HeaderPanel';
import { Tabs } from 'antd';
import { Notifications } from './NotificationsPanel';
import { ChatBot } from './ChatBotPanel';

export const MiniPanel = () => {
  const [activeTab, setActiveTab] = useState('1');

  return (
    <div className="app-container">
      <Header onTabChange={(key) => setActiveTab(key)} />

      <main className="content-area">
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          renderTabBar={() => <></>} // Скрываем стандартные вкладки
          animated={{ inkBar: true, tabPane: true }}
          items={[
            {
              key: '1',
              label: '',
              children: <Notifications />
            },
            {
              key: '2',
              label: '',
              children: <ChatBot />
            },
          ]}
        />
      </main>
    </div>

  );
};