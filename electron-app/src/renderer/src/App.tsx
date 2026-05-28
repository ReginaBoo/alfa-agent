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
import axios from 'axios'
import { Spin, Button, Typography, Card } from 'antd';
import { LoginOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

// Electron компонент проверки авторизации
function ElectronAuthChecker({ children }: { children: React.ReactNode }) {
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

      const response = await axios.get('http://localhost:8000/auth/me', {
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
    if (window.electron?.getSessionToken) {
      const token = await window.electron.getSessionToken();
      if (token) {
        localStorage.setItem('session_token', token);
        return true;
      }
    }
    return false;
  };

  const handleLogin = async () => {
    setIsLoggingIn(true);
    if (window.electron?.startLogin) {
      await window.electron.startLogin();
    }
    setIsLoggingIn(false);
  };

  useEffect(() => {
    if (window.electron?.onAuthSuccess) {
      window.electron.onAuthSuccess(async (token: string) => {
        localStorage.setItem('session_token', token);
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
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Spin size="large" />
    </div>;
  }

  if (!authorized) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Card style={{ maxWidth: 400, textAlign: 'center' }}>
          <Title level={3}>Требуется авторизация</Title>
          <Text>Для работы с Мини Панелью необходимо авторизоваться</Text>
          <Button type="primary" onClick={handleLogin} loading={isLoggingIn} style={{ marginTop: 20 }}>
            Авторизоваться
          </Button>
        </Card>
      </div>
    );
  }

  return <>{children}</>;
}

// Веб-компонент проверки авторизации
function WebAuthChecker() {
  const navigate = useNavigate()

  useEffect(() => {
    axios.defaults.withCredentials = true

    axios
      .get('/auth/me', {
        withCredentials: true,
      })
      .catch(() => {
        navigate('/login')
      })
  }, [navigate])

  return null
}

function App() {
  return (
    <div>
      {isElectron ? (
        <ElectronAuthChecker>
          <MiniPanel />
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

export default App
