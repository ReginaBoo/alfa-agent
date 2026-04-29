import s from './Header.module.css';
import { Button, Dropdown, Space } from 'antd';
import {
  MenuOutlined,
  CloseOutlined,
  MinusOutlined,
  RocketOutlined,
  BellOutlined,
  MessageOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';

let URL = 'http://localhost:5173/'
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
        if ((window as any).electron) {
          (window as any).electron.shell.openExternal(URL);
        } else {
          window.open(URL, '_blank');
        }
      }
    },
  ];

  const handleMinimize = () => {
    (window as any).electron?.ipcRenderer.send('window-minimize');
  };

  const handleClose = () => {
    (window as any).electron?.ipcRenderer.send('window-close');
  };
  return (
    <header className={s.customHeader}>
      <div className="no-drag">
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
          <Button type="text" icon={<MenuOutlined />} size="small" />
        </Dropdown>
      </div>

      <div className={s.headerDragArea}>
        <RocketOutlined style={{ color: '#3460DC' }} />
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
    </header >
  );
};