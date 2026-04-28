import { Button, Dropdown, Space } from 'antd';
import {
  MenuOutlined,
  CloseOutlined,
  MinusOutlined,
  RocketOutlined
} from '@ant-design/icons';

interface HeaderProps {
  onTabChange: (key: string) => void;
}

export const Header = ({ onTabChange }: HeaderProps) => {
  const menuItems = [
    {
      key: '1',
      label: 'Уведомления',
      onClick: () => onTabChange('1')
    },
    {
      key: '2',
      label: 'Чат',
      onClick: () => onTabChange('2')
    },
  ];

  const handleMinimize = () => {
    (window as any).electron.ipcRenderer.send('window-minimize');
  };

  const handleClose = () => {
    (window as any).electron.ipcRenderer.send('window-close');
  };
  return (
    <header className="custom-header">
      <div className="no-drag">
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
          <Button type="text" icon={<MenuOutlined />} size="small" />
        </Dropdown>
      </div>

      <div className="header-drag-area">
        <Space size={4}>
          <RocketOutlined style={{ color: '#1677ff' }} />
          <span className="header-title">Alfa agent</span>
        </Space>
      </div>

      <div className="no-drag">
        <Space size={0}>
          <Button
            type="text"
            icon={<MinusOutlined />}
            className="header-control-btn"
            onClick={handleMinimize}
          />
          <Button
            type="text"
            danger
            icon={<CloseOutlined />}
            className="header-control-btn close-btn"
            onClick={handleClose}
          />
        </Space>
      </div>
    </header>
  );
};