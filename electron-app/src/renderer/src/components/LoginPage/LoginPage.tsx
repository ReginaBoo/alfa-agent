
import { Button, Input, Form } from 'antd';
import {
  GoogleOutlined,
  AppleFilled,
  WindowsOutlined,
  SlackOutlined
} from '@ant-design/icons';
import s from './LoginPage.module.css';
import atlassianIcon from './atlassian.svg';
import { useNavigate } from 'react-router-dom';

// Логотип Atlassian (упрощенный текст + иконка)
const AtlassianLogo = () => (
  <div className={s.logoContainer}>
    <img src={atlassianIcon} alt="Atlassian" className={s.logoIcon} />
    <span className={s.logoText}>ATLASSIAN</span>
  </div>
);

export const LoginPage = () => {
  const [form] = Form.useForm();


  const navigate = useNavigate();

  const onFinish = (values: any) => {
    console.log('Success:', values);
    // 3. Выполняем переход на страницу дашборда
    navigate('/dashboard');
  };
  return (
    <div className={s.pageWrapper}>
      <div className={s.loginCard}>
        <AtlassianLogo />

        <h2 className={s.loginTitle}>Войдите</h2>

        <Form
          form={form}
          name="atlassian_login"
          onFinish={onFinish}
          layout="vertical"
        >
          <Form.Item
            name="email"
            rules={[{ required: true, type: 'email', message: 'Веддите корректную почту' }]}
          >
            <Input placeholder="Введите почту" className={s.mainInput} />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" block className={s.continueBtn}>
              Войти
            </Button>
          </Form.Item>
        </Form>

        <p className={s.orLabel}>Или продолжите с</p>

        <div className={s.socialButtons}>
          <Button block icon={<GoogleOutlined style={{ color: '#EA4335' }} />}>Google</Button>
          <Button block icon={<WindowsOutlined style={{ color: '#00A4EF' }} />}>Microsoft</Button>
          <Button block icon={<AppleFilled />}>Apple</Button>
          <Button block icon={<SlackOutlined style={{ color: '#4A154B' }} />}>Slack</Button>
        </div>


      </div>
    </div>
  );
};