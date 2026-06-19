import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Typography, message } from 'antd';
import api from '../../api/client';
import { LoginOutlined } from '@ant-design/icons';
import s from './LoginPage.module.css';

const { Title, Text } = Typography;

// 🔥 Жестко задаем бекенд URL
const BACKEND_URL = 'https://89.169.165.170.nip.io';

export const LoginPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    console.log('[LoginPage] URL params:', window.location.search);
    console.log('[LoginPage] Token from URL:', token);

    if (token) {
      console.log('✅ Saving token to localStorage...');
      localStorage.setItem('session_token', token);

      console.log('🔧 Setting token in API headers...');
      api.defaults.headers.common['X-Session-Token'] = token;

      console.log('Token in localStorage:', localStorage.getItem('session_token'));
      console.log('Token in API headers:', api.defaults.headers.common['X-Session-Token']);

      message.success('Авторизация успешна!');

      setTimeout(() => {
        console.log('🚀 Redirecting to /dashboard...');
        navigate('/dashboard', { replace: true });
      }, 500);
    } else {
      console.log('❌ No token in URL');
    }
  }, [navigate]);

  const handleLogin = () => {
    console.log('🔑 Redirecting to:', `${BACKEND_URL}/auth/login`);
    window.location.href = `${BACKEND_URL}/auth/login`;
  };

  return (
    <div className={s.pageWrapper}>
      <div className={s.loginCard}>
        <Title level={3} className={s.loginTitle}>
          Вход в систему
        </Title>

        <Text type="secondary" style={{ display: 'block', marginBottom: 24, fontSize: 13 }}>
          Для продолжения работы вам необходимо пройти аутентификацию.
        </Text>

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
