import { Input, Button, Space, Spin, Alert } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { useState, useRef, useEffect } from 'react';
import { dashboardApi } from '../../../api/dashboardApi';
import s from './ChatBot.module.css';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

interface ChatHistoryItem {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export const ChatBot = () => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', text: 'Привет! Я твой аналитический агент. Чем помочь?' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => {
    const saved = localStorage.getItem('chat_session_id');
    if (saved) return saved;
    const newId = crypto.randomUUID();
    localStorage.setItem('chat_session_id', newId);
    return newId;
  });

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const historyData = messages.map(msg => ({
      role: msg.role,
      content: msg.text
    }));
    localStorage.setItem('chat_history', JSON.stringify(historyData));
  }, [messages]);

  useEffect(() => {
    const savedHistory = localStorage.getItem('chat_history');
    if (savedHistory) {
      try {
        const parsed = JSON.parse(savedHistory);
        if (parsed.length > 0) {
          setMessages(parsed.map((m: any) => ({
            role: m.role === 'assistant' ? 'assistant' : 'user',
            text: m.content
          })));
        }
      } catch (e) {
        console.error('Failed to parse chat history:', e);
      }
    }
  }, []);

  const buildHistory = (): ChatHistoryItem[] => {
    return messages.slice(0, -1).map(msg => ({
      role: msg.role,
      content: msg.text
    }));
  };

  // Рендеринг HTML сообщений
  const renderMessageText = (text: string, role: 'user' | 'assistant') => {
    if (role === 'user') {
      return text;
    }

    // Для AI сообщений преобразуем переносы строк в <br/>
    let formattedText = text;
    formattedText = formattedText.replace(/\n/g, '<br/>');

    return (
      <div
        dangerouslySetInnerHTML={{ __html: formattedText }}
        style={{
          whiteSpace: 'normal',
          lineHeight: 1.6,
        }}
      />
    );
  };

  const handleSend = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setError(null);

    setMessages((prev) => [...prev, { role: 'user', text: userMessage }]);
    setIsLoading(true);

    try {
      const response = await dashboardApi.chatAiCompletion(
        userMessage,
        sessionId,
        buildHistory()
      );

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: response.answer
        }
      ]);

    } catch (err: any) {
      console.error('Chat error:', err);
      setError(err.response?.data?.detail || 'Ошибка при отправке сообщения');

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Произошла ошибка: ${err.response?.data?.detail || 'Не удалось обработать запрос'}`
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = () => {
    setMessages([{ role: 'assistant', text: 'Привет! Я твой аналитический агент. Чем помочь?' }]);
    localStorage.removeItem('chat_history');
    const newId = crypto.randomUUID();
    setSessionId(newId);
    localStorage.setItem('chat_session_id', newId);
  };

  return (
    <div className={s.chatContainer}>
      <div className={s.chatHeader}>
        <span>Чат с AI</span>
        <Button size="small" onClick={handleClearHistory}>
          Очистить
        </Button>
      </div>

      <div className={s.messageList} ref={scrollRef}>
        {messages.map((msg, index) => (
          <div key={index} className={s.messageItem}>
            <Space align="start" className={msg.role === 'user' ? s.reverseRow : ''}>
              <div className={`${s.bubble} ${msg.role === 'assistant' ? s.aiBubble : s.userBubble}`}>
                {renderMessageText(msg.text, msg.role)}
              </div>
            </Space>
          </div>
        ))}

        {isLoading && (
          <div className={`${s.messageItem} ${s.aiItem}`}>
            <Space align="start">
              <div className={`${s.bubble} ${s.aiBubble}`}>
                <Spin size="small" />
                <span style={{ marginLeft: 8 }}>Думаю...</span>
              </div>
            </Space>
          </div>
        )}

        {error && (
          <div className={`${s.messageItem} ${s.aiItem}`}>
            <Alert
              message="Ошибка"
              description={error}
              type="error"
              showIcon
              closable
              onClose={() => setError(null)}
            />
          </div>
        )}
      </div>

      <div className={s.inputContainer}>
        <Space.Compact className={s.inputGroup} style={{ width: '100%' }}>
          <Input
            placeholder="Напишите сообщение..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={handleSend}
            disabled={isLoading}
            variant="borderless"
            style={{ background: '#f5f5f5', borderRadius: '6px 0 0 6px' }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={isLoading}
            disabled={!inputValue.trim()}
          />
        </Space.Compact>
      </div>
    </div>
  );
};
