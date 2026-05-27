import { Button } from 'antd'
import {
  GoogleOutlined,
  AppleFilled,
  WindowsOutlined,
  SlackOutlined,
} from '@ant-design/icons'

import s from './LoginPage.module.css'
import atlassianIcon from './atlassian.svg'

const AtlassianLogo = () => (
  <div className={s.logoContainer}>
    <img
      src={atlassianIcon}
      alt="Atlassian"
      className={s.logoIcon}
    />

    <span className={s.logoText}>ATLASSIAN</span>
  </div>
)

export const LoginPage = () => {
  const handleLogin = () => {
    window.location.href = '/api/auth/login'
  }

  return (
    <div className={s.pageWrapper}>
      <div className={s.loginCard}>
        <AtlassianLogo />

        <h2 className={s.loginTitle}>Войдите</h2>

        <Button
          type="primary"
          block
          className={s.continueBtn}
          onClick={handleLogin}
        >
          Войти через Atlassian
        </Button>

        <p className={s.orLabel}>Или продолжите с</p>

        <div className={s.socialButtons}>
          <Button
            block
            icon={
              <GoogleOutlined style={{ color: '#EA4335' }} />
            }
          >
            Google
          </Button>

          <Button
            block
            icon={
              <WindowsOutlined style={{ color: '#00A4EF' }} />
            }
          >
            Microsoft
          </Button>

          <Button block icon={<AppleFilled />}>
            Apple
          </Button>

          <Button
            block
            icon={<SlackOutlined style={{ color: '#4A154B' }} />}
          >
            Slack
          </Button>
        </div>
      </div>
    </div>
  )
}