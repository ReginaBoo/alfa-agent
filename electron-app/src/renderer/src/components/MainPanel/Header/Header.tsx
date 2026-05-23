import { Select, Badge, Avatar, Space } from 'antd';
import {
  AppstoreFilled,
  BellOutlined,
  DownOutlined, RocketOutlined, TeamOutlined, ProjectOutlined
} from '@ant-design/icons';
import s from './Header.module.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { dashboardApi } from '../../../api/dashboardApi';
import { DashboardProject } from '../../../types/dashboard';

export const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [projects, setProjects] = useState<DashboardProject[]>([]);

  useEffect(() => {
    dashboardApi
      .getProjects()
      .then(setProjects)
      .catch((err) => {
        console.error('Failed to load projects', err);
      });
  }, []);

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
              value: p.key,
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