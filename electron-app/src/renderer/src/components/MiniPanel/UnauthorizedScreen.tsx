import React from 'react';
import { Button, Typography, Space, Card } from 'antd';
import { LoginOutlined, WarningOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

interface UnauthorizedScreenProps {
  onLogin: () => void;
  isLoading?: boolean;
}

const UnauthorizedScreen: React.FC<UnauthorizedScreenProps> = ({ onLogin, isLoading = false }) => {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100%',
        minHeight: '400px',
        padding: '24px',
      }}
    >
      <Card
        style={{
          maxWidth: 400,
          width: '100%',
          textAlign: 'center',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        }}
      >
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <WarningOutlined style={{ fontSize: 48, color: '#faad14' }} />

          <Title level={3}>Требуется авторизация</Title>

          <Text type="secondary">
            Для работы с Мини Панелью необходимо авторизоваться.
            Вы будете перенаправлены в браузер для входа через OAuth.
          </Text>

          <Button
            type="primary"
            size="large"
            icon={<LoginOutlined />}
            onClick={onLogin}
            loading={isLoading}
            style={{ width: '100%' }}
          >
            Авторизоваться
          </Button>

          <Text type="secondary" style={{ fontSize: 12 }}>
            После авторизации в браузере вернитесь в приложение
          </Text>
        </Space>
      </Card>
    </div>
  );
};

export default UnauthorizedScreen;
