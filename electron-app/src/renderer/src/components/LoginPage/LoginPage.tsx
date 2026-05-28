import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Typography, message } from 'antd';
import api from '../../api/client';

const { Title } = Typography;

export const LoginPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    console.log('🔐 [LoginPage] URL params:', window.location.search);
    console.log('🔐 [LoginPage] Token from URL:', token);

    if (token) {
      console.log('💾 Saving token to localStorage...');
      localStorage.setItem('session_token', token);

      console.log('🔧 Setting token in API headers...');
      api.defaults.headers.common['X-Session-Token'] = token;

      console.log('✅ Token saved, redirecting to /dashboard');
      message.success('Авторизация успешна!');

      // Очищаем URL от токена и перенаправляем
      navigate('/dashboard', { replace: true });
    } else {
      console.log('❌ No token in URL');
    }
  }, [navigate]);

  const handleLogin = () => {
    window.location.href = 'http://localhost:8000/auth/login';
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Card style={{ maxWidth: 400 }}>
        <Title level={3}>Вход в систему</Title>
        <Button type="primary" onClick={handleLogin}>
          Войти через Atlassian
        </Button>
      </Card>
    </div>
  );
};
