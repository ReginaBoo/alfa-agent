import './index.css'
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MiniPanel } from './components/MiniPanel/MiniPanel'
import { isElectron } from './utils'
import { MainPanel } from './components/MainPanel/MainPanel'
import { ProjectDashboard } from './components/MainPanel/pages/ProjectDashboard/ProjectDashboard';
import { Dashboard } from './components/MainPanel/pages/Dashboard/Dashboard';
import { LoginPage } from './components/LoginPage/LoginPage';
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Spin } from 'antd';
import { setAuthToken } from './api/client';
import api from './api/client';

// Меняем тип пропсов для ElectronAuthChecker, теперь children — это функция
interface ElectronAuthCheckerProps {
  children: (authProps: { authorized: boolean; handleLogin: () => Promise<void>; isLoggingIn: boolean }) => React.ReactNode;
}

// Electron компонент проверки авторизации
function ElectronAuthChecker({ children }: ElectronAuthCheckerProps) {
  const [loading, setLoading] = useState(true);
  const [authorized, setAuthorized] = useState(false);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('session_token');
      if (!token) {
        setAuthorized(false);
        return;
      }

      const response = await api.get('/auth/me', {
        headers: { 'X-Session-Token': token }
      });

      if (response.data?.user) {
        setAuthorized(true);
      }
    } catch (error) {
      setAuthorized(false);
    } finally {
      setLoading(false);
    }
  };

  const syncTokenFromMain = async () => {
    console.log('[React] syncTokenFromMain called');
    if (window.electron?.getSessionToken) {
      const token = await window.electron.getSessionToken();
      console.log('[React] Token from main:', token ? '✅ exists' : '❌ no');
      if (token) {
        localStorage.setItem('session_token', token);
        setAuthToken(token);
        return true;
      }
    }
    return false;
  };

  const handleLogin = async () => {
    console.log('[React] handleLogin called');
    setIsLoggingIn(true);
    if (window.electron?.startLogin) {
      await window.electron.startLogin();
    }
    setIsLoggingIn(false);

    // После закрытия браузера проверяем токен
    console.log('[React] Checking token after login...');
    setTimeout(async () => {
      const token = await window.electron?.getSessionToken();
      if (token) {
        console.log('[React] ✅ Token found after login');
        localStorage.setItem('session_token', token);
        setAuthToken(token);
        await checkAuth();
      } else {
        console.log('[React] ❌ No token found after login');
      }
    }, 3000);
  };

  useEffect(() => {
    const handler = () => {
      console.log('[Auth] logout from Electron');

      setAuthToken(null);
      localStorage.removeItem('session_token');

      setAuthorized(false);
    };

    window.electron?.onLogout?.(handler);

    return () => {
      window.electron?.removeAuthListener?.();
    };

  }, []);

  useEffect(() => {
    const handleFocus = () => {
      console.log('[React] Window focused, checking auth...');
      syncTokenFromMain().then(() => {
        checkAuth();
      });
    };

    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, []);

  useEffect(() => {
    if (window.electron?.onAuthSuccess) {
      window.electron.onAuthSuccess(async (token: string) => {
        setAuthToken(token);
        await checkAuth();
      });
    }
    const init = async () => {
      await syncTokenFromMain();
      await checkAuth();
    };

    init();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  /* ЗДЕСЬ ИЗМЕНЕНИЕ: Мы больше не блокируем рендер карточкой.
    Мы всегда рендерим внутренности MiniPanel, передавая туда состояние авторизации
  */
  return <>{children({ authorized, handleLogin, isLoggingIn })}</>;
}

export function WebAuthChecker() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const check = async () => {
      try {
        await api.get('/auth/me');

        if (window.location.pathname === '/login') {
          navigate('/dashboard', { replace: true });
        }
      } catch {
        navigate('/login', { replace: true });
      } finally {
        setLoading(false);
      }
    };

    check();
  }, [navigate]);

  if (loading) {
    return (
      <div style={{
        height: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <Spin size="large" />
      </div>
    );
  }

  return null;
}


function App() {
  return (
    <div>
      {isElectron ? (
        /* ЗДЕСЬ ИЗМЕНЕНИЕ: Получаем пропсы из чекера
          и прокидываем их развернутым объектом в MiniPanel
        */
        <ElectronAuthChecker>
          {(authProps) => <MiniPanel {...authProps} />}
        </ElectronAuthChecker>
      ) : (
        <BrowserRouter>
          <WebAuthChecker />
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/*"
              element={
                <MainPanel>
                  <Routes>
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/project/:id" element={<ProjectDashboard />} />
                  </Routes>
                </MainPanel>
              }
            />
          </Routes>
        </BrowserRouter>
      )}
    </div>
  )
}

export default App;
