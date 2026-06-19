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

  // ВРЕМЕННО - для продакшена захардкодим URL
  const BACKEND_URL = 'https://89.169.165.170.nip.io';
  // const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

  const checkAuth = async () => {
    try {
      console.log('🔍 Checking auth...');
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
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');

    if (tokenFromUrl) {
      console.log('✅ Token found in URL, saving to localStorage');
      setAuthToken(tokenFromUrl);
      window.history.replaceState({}, document.title, window.location.pathname);
      window.location.href = '/dashboard';
    } else {
      const savedToken = localStorage.getItem('session_token');
      if (savedToken) {
        setAuthToken(savedToken);
      }
      checkAuth();
    }
  }, []);

  const handleLogin = () => {
    setIsLoggingIn(true);
    const loginUrl = `${BACKEND_URL}/auth/login`;
    console.log('🔑 Login URL:', loginUrl);

    if (window.electron?.openExternal) {
      window.electron.openExternal(loginUrl);
    } else {
      window.open(loginUrl, '_blank');
    }

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
