import { Input, Button, Space } from 'antd';
import { SendOutlined, } from '@ant-design/icons';
import { useState, useRef, useEffect } from 'react';
import s from './ChatBot.module.css';

export const ChatBot = () => {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Привет! Я твой агент. Чем помочь?' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // Автопрокрутка вниз при новом сообщении
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!inputValue.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', text: inputValue }]);
    setInputValue('');

    // Имитация ответа бота
    setTimeout(() => {
      setMessages((prev) => [...prev, { role: 'ai', text: 'Обрабатываю...' }]);
    }, 1000);
  };

  return (
    <div className={s.chatContainer}>
      {/* Область сообщений */}
      <div className={s.messageList} ref={scrollRef}>
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`${s.messageItem} ${msg.role === 'ai' ? s.aiItem : s.userItem}`}
          >
            <Space align="start" className={msg.role === 'user' ? s.reverseRow : ''}>
              <div className={`${s.bubble} ${msg.role === 'ai' ? s.aiBubble : s.userBubble}`}>
                {msg.text}
              </div>
            </Space>
          </div>
        ))}
      </div>

      {/* Поле ввода */}
      <div className={s.inputContainer}>
        <Space.Compact className={s.inputGroup}>
          <Input
            placeholder="Напишите сообщение..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={handleSend}
            variant="borderless"
            style={{ background: '#f5f5f5', borderRadius: '6px 0 0 6px' }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
          />
        </Space.Compact>
      </div>
    </div>
  );
};