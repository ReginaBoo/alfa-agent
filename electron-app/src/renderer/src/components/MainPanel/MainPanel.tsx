import { Layout } from 'antd';
import { Header } from './Header/Header';
import { Dashboard } from './Dashboard/Dashboard';

const { Content } = Layout;

export const MainPanel = () => {
  return (
    <Layout style={{ minHeight: '100vh', margin: 0 }}>
      <Header />
      <Layout>
        <Content style={{ margin: 0, backgroundColor: '#F1F5F9' }}>
          <div>
            <Dashboard />
          </div>
        </Content>
      </Layout>
    </Layout >
  );
};
