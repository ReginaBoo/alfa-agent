import { Input, Button, Space, List, Avatar } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
import { useState } from 'react';

export const ChatBot = () => {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Привет! Я твой агент. Чем помочь?' }
  ]);
  const [inputValue, setInputValue] = useState('');

  const handleSend = () => {
    if (!inputValue.trim()) return;
    setMessages([...messages, { role: 'user', text: inputValue }]);
    setInputValue('');
    // Тут будет вызов бэкенда
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 100px)' }}>
      {/* Область сообщений */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
        <List
          itemLayout="horizontal"
          dataSource={messages}
          renderItem={(msg) => (
            <List.Item style={{ border: 'none', justifyContent: msg.role === 'ai' ? 'flex-start' : 'flex-end' }}>
              <List.Item.Meta
                avatar={<Avatar icon={msg.role === 'ai' ? <RobotOutlined /> : <UserOutlined />} />}
                title={msg.role === 'ai' ? 'AI Agent' : 'Вы'}
                description={msg.text}
                style={{
                  background: msg.role === 'ai' ? '#f0f2f5' : '#e6f7ff',
                  padding: '8px 12px',
                  borderRadius: '12px',
                  maxWidth: '80%'
                }}
              />
            </List.Item>
          )}
        />
      </div>

      {/* Поле ввода */}
      <div style={{ padding: '12px', borderTop: '1px solid #f0f0f0' }}>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={handleSend}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleSend} />
        </Space.Compact>
      </div>
    </div>
  );
};