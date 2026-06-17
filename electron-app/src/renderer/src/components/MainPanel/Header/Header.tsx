import { Select, Avatar, MenuProps, Dropdown } from 'antd';
import {
  AppstoreFilled,
  DownOutlined, TeamOutlined, ProjectOutlined
} from '@ant-design/icons';
import s from './Header.module.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { useProjects } from '../../../hooks/useDashboardData';
import { useAuth } from '../../../hooks/useHeader';
import { logout } from '../../../api/logout';
import logo from '../../../assets/logo.svg';
import { useState } from 'react';
export const Header = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { data: projects = [] } = useProjects();

  const [open, setOpen] = useState(false);

  const getCurrentValue = () => {
    const pathParts = location.pathname.split('/');
    if (pathParts[1] === 'project' && pathParts[2]) {
      return pathParts[2];
    }
    return 'all';
  };



  const currentProjectId = getCurrentValue();

  const currentProject = projects.find(
    p => String(p.id) === currentProjectId
  );

  const { user } = useAuth();

  const handleLogout = async () => {
    await logout();
  };

  const items: MenuProps['items'] = [
    {
      key: 'user-info',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 600, color: '#02489B' }}>
            {user?.name || 'Пользователь'}
          </div>
          <div style={{ fontSize: 12, color: '#02489B' }}>
            {user?.email}
          </div>
        </div>
      ),
      disabled: true,
    },
    {
      type: 'divider',
    },
    {
      key: 'logout',
      label: 'Выйти',
      danger: true,
      onClick: handleLogout,
    },
  ];


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
        <div className={s.headerDragArea}>
          <img src={logo} alt="rocket" width={24} height={24} />
        </div>
        <div className={s.logoTitle}>
          {currentProjectId === 'all' ? (
            <AppstoreFilled className={s.logo} />
          ) : (
            <ProjectOutlined className={s.logo} />
          )}

          <span className={s.title}>
            {currentProjectId === 'all'
              ? 'Главная'
              : currentProject?.name}
          </span>
        </div>
      </div>

      <div className={s.rightSection}>
        <Select
          className={s.projectSelect}
          value={getCurrentValue()}
          onChange={handleSelectChange}
          onOpenChange={setOpen}
          suffixIcon={
            <DownOutlined
              className={`${s.arrow} ${open ? s.arrowOpen : ''}`}
            />
          }
          options={[
            {
              value: 'all',
              label: (
                <div className={s.optionLabel}>
                  <TeamOutlined />
                  <span>Все проекты</span>
                </div>
              ),
            },
            ...projects.map(p => ({
              value: String(p.id),
              label: (
                <div className={s.optionLabel}>
                  <span>{p.name}</span>
                </div>
              )
            }))
          ]}
        />

        <Dropdown menu={{ items }} trigger={['click']}>
          <Avatar className={s.avatar}>
            {user?.name?.[0] || user?.email?.[0] || ''}
          </Avatar>
        </Dropdown>

      </div>
    </header >
  );
};
