import React, { useEffect, useState } from 'react';
import { Spin, Button, Typography, Card } from 'antd';
import { LoginOutlined } from '@ant-design/icons';
import api, { setAuthToken } from '../../api/client';

const { Title, Text } = Typography;

interface AuthCheckerProps {
  children: React.ReactNode;
}

const AuthChecker: React.FC<AuthCheckerProps> = ({ children }) => {
  const [loading, setLoading] = useState(true);
  const [authorized, setAuthorized] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const checkAuth = async () => {
    try {
      console.log('🔍 Checking auth...');
      // Теперь baseURL уже включает /api
      const response = await api.get('/auth/me');
      console.log('✅ Auth response:', response.data);
      setAuthorized(true);
      return true;
    } catch (error: any) {
      console.log('❌ Auth failed:', error.response?.status);
      setAuthorized(false);
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Проверяем, есть ли токен в URL параметрах (при переходе из Electron)
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');

    if (tokenFromUrl) {
      console.log('✅ Token found in URL, saving to localStorage');
      // Сохраняем токен через функцию
      setAuthToken(tokenFromUrl);
      // Убираем токен из URL, чтобы не светился
      window.history.replaceState({}, document.title, window.location.pathname);

      // Перенаправляем на дашборд после сохранения токена
      window.location.href = '/dashboard';
    } else {
      // Проверяем, есть ли токен в localStorage
      const savedToken = localStorage.getItem('session_token');
      if (savedToken) {
        setAuthToken(savedToken);
      }
      checkAuth();
    }
  }, []);

  const handleLogin = () => {
    setIsLoggingIn(true);
    const loginUrl = 'http://localhost:8000/auth/login';

    // Открываем в браузере
    if (window.electron?.openExternal) {
      window.electron.openExternal(loginUrl);
    } else {
      window.open(loginUrl, '_blank');
    }

    // Polling: проверяем авторизацию каждые 2 секунды
    const interval = setInterval(async () => {
      try {
        await api.get('/auth/me');
        setAuthorized(true);
        setIsLoggingIn(false);
        clearInterval(interval);
      } catch (error) {
        // Всё ещё не авторизован
      }
    }, 2000);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="Проверка авторизации..." />
      </div>
    );
  }

  if (!authorized) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Card style={{ maxWidth: 400, textAlign: 'center' }}>
          <Title level={3}>Требуется авторизация</Title>
          <Text type="secondary">Для работы с Мини Панелью необходимо авторизоваться</Text>
          <Button
            type="primary"
            icon={<LoginOutlined />}
            onClick={handleLogin}
            loading={isLoggingIn}
            style={{ marginTop: 20 }}
          >
            Авторизоваться
          </Button>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
};

export default AuthChecker;
