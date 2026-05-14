import { Layout } from 'antd';
import { Header } from './Header/Header';

const { Content } = Layout;

export const MainPanel = ({ children }) => {
  return (
    <Layout style={{ minHeight: '100vh', margin: 0 }}>
      <Header />
      <Layout>
        <Content style={{ margin: 0, backgroundColor: '#F1F5F9' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};