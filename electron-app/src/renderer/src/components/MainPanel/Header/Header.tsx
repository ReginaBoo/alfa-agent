import { Select, Badge, Avatar, Space } from 'antd';
import {
  AppstoreFilled,
  BellOutlined,
  DownOutlined, RocketOutlined, TeamOutlined, ProjectOutlined
} from '@ant-design/icons';
import s from './Header.module.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { useProjects } from '../../../hooks/useDashboardData';
export const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: projects = [] } = useProjects();


  const getCurrentValue = () => {
    const pathParts = location.pathname.split('/');
    if (pathParts[1] === 'project' && pathParts[2]) {
      return pathParts[2];
    }
    return 'all';
  };

  const handleSelectChange = (value: string) => {
    if (value === 'all') {
      navigate('/dashboard');
    } else {
      navigate(`/project/${value}`);
    }
  };

  return (
    <header className={s.header}>
      <div className={s.leftSection}>
        <RocketOutlined className={s.rocketIcon} />
        <div className={s.logoTitle}>
          <AppstoreFilled className={s.logo} />
          <span className={s.title}>Главная</span>
        </div>
      </div>

      <div className={s.rightSection}>
        <Select
          className={s.projectSelect}
          value={getCurrentValue()}
          suffixIcon={<DownOutlined />}
          onChange={handleSelectChange}
          options={[
            {
              value: 'all',
              label: (
                <Space>
                  <TeamOutlined />
                  <span>Все проекты</span>
                </Space>
              ),
            },
            ...projects.map(p => ({
              value: String(p.id),
              label: (
                <Space>
                  <ProjectOutlined />
                  <span>{p.name}</span>
                </Space>
              )
            }))
          ]}
        />

        <Badge dot color="#ff4d4f" offset={[-2, 4]}>
          <div className={s.iconBtn}>
            <BellOutlined />
          </div>
        </Badge>

        <Avatar style={{ backgroundColor: '#e6f7ff', color: '#1677ff', fontWeight: 'bold' }}>
          Л
        </Avatar>
      </div>
    </header>
  );
};
