import { Button } from 'antd'

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
      </div>
    </div>
  )
}