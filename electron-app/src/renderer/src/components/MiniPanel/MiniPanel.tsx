import { useState } from 'react';
import { Header } from './Header/Header';
import { Tabs } from 'antd';
import { Notifications } from './Notifications/Notifications';
import { ChatBot } from './ChatBot/ChatBot';
import s from './MiniPanel.module.css';

export const MiniPanel = () => {
  const [activeTab, setActiveTab] = useState('1');

  return (
    <div className={s.appContainer}>
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