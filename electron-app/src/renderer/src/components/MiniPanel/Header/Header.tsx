import s from './Header.module.css';
import { Button, Dropdown, Space } from 'antd';

import logo from '../../../assets/logo.svg';
import {
  MenuOutlined,
  CloseOutlined,
  MinusOutlined,
  BellOutlined,
  MessageOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
interface HeaderProps {
  onTabChange: (key: string) => void;
}

export const Header = ({ onTabChange }: HeaderProps) => {
  const menuItems = [
    {
      key: '1',
      label: 'Оповещения',
      icon: <BellOutlined />,
      onClick: () => onTabChange('1')
    },
    {
      key: '2',
      label: 'Чат',
      icon: <MessageOutlined />,
      onClick: () => onTabChange('2')
    },
    {
      key: '3',
      label: 'Метрики',
      icon: <AppstoreOutlined />,
      onClick: () => {
        const token = localStorage.getItem('session_token');
        const url = token
          ? `http://localhost:5173/login?token=${encodeURIComponent(token)}`
          : 'http://localhost:5173/login';

        if ((window as any).electron?.openExternal) {
          (window as any).electron.openExternal(url);
        } else {
          window.open(url, '_blank');
        }
      }
    },
  ];

  const handleMinimize = () => {
    (window as any).electron?.ipcRenderer?.send('window-minimize');
  };

  const handleClose = () => {
    (window as any).electron?.ipcRenderer?.send('window-close');
  };

  return (
    <header className={s.customHeader}>
      <div className="no-drag">
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
          <Button type="text" icon={<MenuOutlined />} size="small" />
        </Dropdown>
      </div>

      <div className={s.headerDragArea}>
        <img src={logo} alt="rocket" width={20} height={20} />
      </div>

      <div className="no-drag">
        <Space size={10}>
          <Button
            type="text"
            icon={<MinusOutlined />}
            className={s.headerControlBtn}
            onClick={handleMinimize}
          />
          <Button
            type="text"
            icon={<CloseOutlined />}
            className={`${s.headerControlBtn} ${s.closeBtn}`}
            onClick={handleClose}
          />
        </Space>
      </div>
    </header>
  );
};
