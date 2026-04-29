import { Select, Badge, Avatar, Space } from 'antd';
import {
  AppstoreFilled,
  BellOutlined,
  DownOutlined, RocketOutlined, TeamOutlined, ProjectOutlined
} from '@ant-design/icons';
import s from './Header.module.css';

export const Header = () => {
  return (
    <header className={s.header}>
      {/* Левая часть: Лого и Название */}
      <div className={s.leftSection}>
        <RocketOutlined className={s.rocketIcon} />
        <div className={s.logoTitle}>
          <AppstoreFilled className={s.logo} />
          <span className={s.title}>Главная</span>
        </div>
      </div>

      {/* Правая часть: Управление */}
      <div className={s.rightSection}>
        <Select
          className={s.projectSelect}
          defaultValue="all"
          suffixIcon={<DownOutlined />}
          options={[
            {
              value: 'all',
              label: (
                <Space>
                  <TeamOutlined style={{ color: '#989898' }} />
                  <span>Все проекты</span>
                </Space>
              )
            },
            {
              value: 'p1',
              label: (
                <Space>
                  <ProjectOutlined />
                  <span>Проект 1</span>
                </Space>
              )
            },
            {
              value: 'p2',
              label: (
                <Space>
                  <ProjectOutlined />
                  <span>Проект 2</span>
                </Space>
              )
            },
          ]}
        />

        <Badge dot color="#ff4d4f" offset={[-2, 4]}>
          <div className={s.iconBtn}>
            <BellOutlined />
          </div>
        </Badge>

        <Avatar
          style={{ backgroundColor: '#e6f7ff', color: '#1677ff', fontWeight: 'bold' }}
        >
          Л
        </Avatar>
      </div>
    </header >
  );
};