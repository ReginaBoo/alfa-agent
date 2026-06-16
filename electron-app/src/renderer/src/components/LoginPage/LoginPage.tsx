import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Typography, message } from 'antd';
import api from '../../api/client';
import { LoginOutlined } from '@ant-design/icons';
import s from './LoginPage.module.css'; // Убедись, что путь к стилям правильный
const { Title, Text } = Typography;
export const LoginPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    console.log('[LoginPage] URL params:', window.location.search);
    console.log('[LoginPage] Token from URL:', token);

    if (token) {
      console.log('Saving token to localStorage...');
      localStorage.setItem('session_token', token);

      console.log('🔧 Setting token in API headers...');
      api.defaults.headers.common['X-Session-Token'] = token;

      console.log('Token saved, redirecting to /dashboard');
      message.success('Авторизация успешна!');

      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 20);
    } else {
      console.log('No token in URL');
    }
  }, [navigate]);

  const handleLogin = () => {
    window.location.href = 'http://localhost:8000/auth/login';
  };

  return (
    <div className={s.pageWrapper}>
      <div className={s.loginCard}>
        {/* Заголовок входа */}
        <Title level={3} className={s.loginTitle}>
          Вход в систему
        </Title>

        <Text type="secondary" style={{ display: 'block', marginBottom: 24, fontSize: 13 }}>
          Для продолжения работы вам необходимо пройти аутентификацию.
        </Text>

        {/* Контейнер с кнопкой авторизации */}
        <div className={s.socialButtons}>
          <Button
            type="primary"
            icon={<LoginOutlined />}
            onClick={handleLogin}
            className={s.continueBtn}
            block
          >
            Войти через Atlassian
          </Button>
        </div>
      </div>
    </div>
  );
};