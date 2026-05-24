import { Row, Button, Select, Spin, Empty, Space, Checkbox, Dropdown } from 'antd';
import {
  DownloadOutlined, DownOutlined, FilterOutlined
} from '@ant-design/icons';
import { DashboardPeriod, DashboardMetric } from '../../types/dashboard';
import s from './DashboardControls.module.css';

interface DownloadReportBtnProps {
  onDownload?: () => void;
  loading?: boolean; // Полезно, если отчет будет генерироваться какое-то время
}

export const DownloadReportBtn = ({ onDownload, loading = false }: DownloadReportBtnProps) => {
  return (
    <Button
      type="primary"
      icon={<DownloadOutlined />}
      size="large"
      className={s.downloadBtn}
      onClick={onDownload}
      loading={loading}
    >
      Скачать отчет
    </Button>
  );
};



interface PeriodSelectProps {
  value: DashboardPeriod;
  onChange: (value: DashboardPeriod) => void;
}

export const PeriodSelect = ({ value, onChange }: PeriodSelectProps) => {
  return (
    <Select
      className={s.projectSelect}
      value={value}
      onChange={(val) => onChange(val as DashboardPeriod)}
      suffixIcon={<DownOutlined />}
      options={[
        { value: 'all', label: 'Весь период' },
        { value: 'last week', label: 'Последняя неделя' }
      ]}
    />
  );
};


interface MetricsSelectProps {
  value: DashboardMetric[];
  onChange: (value: DashboardMetric[]) => void;
}

export const MetricsSelect = ({ value, onChange }: MetricsSelectProps) => {
  const metricsList = [
    { key: 'effectiveness', label: 'Эффективность команды' },
    { key: 'activity', label: 'Активность разработки' },
    { key: 'codeCount', label: 'Количество кода и ревью' },
  ];

  const handleCheckboxChange = (key: DashboardMetric, checked: boolean) => {
    if (checked) {
      onChange([...value, key]);
    } else {
      onChange(value.filter((item) => item !== key));
    }
  };
  const menuItems = metricsList.map((item) => ({
    key: item.key,
    label: (
      // Обернули в onClick, чтобы клик по всей строчке переключал чекбокс
      <div onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={value.includes(item.key as DashboardMetric)}
          onChange={(e) => handleCheckboxChange(item.key as DashboardMetric, e.target.checked)}
        >
          <Space className={s.itemContent}>
            <span>{item.label}</span>
          </Space>
        </Checkbox>
      </div>
    ),
  }));

  return (
    <Dropdown
      menu={{ items: menuItems }}
      trigger={['click']}
      placement="bottomRight"
    >
      <Button
        type="default"
        icon={<FilterOutlined />}
        className={s.filterButton}
      />
    </Dropdown>
  );
};

interface DashboardLoaderProps {
  minHeight?: string | number;
  tip?: string;
}

export const DashboardLoader = ({ minHeight = '200px', tip = '' }: DashboardLoaderProps) => {
  return (
    <Row justify="center" align="middle" style={{ minHeight, color: '#02489B' }}>
      <Spin size="large" description={tip} />
    </Row>
  );
};

interface DashboardEmptyProps {
  description?: string;
  minHeight?: string | number;
}

export const DashboardEmpty = ({
  description = 'Пока нет данных',
}: DashboardEmptyProps) => {
  return (
    <Empty
      description={
        <span style={{ color: '#8c8c8c' }}>
          {description}
        </span>
      }
    />
  );
};

export const NoProjectsEmpty = () => {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '80vh',
      width: '100%'
    }}>
      <Empty
        image={Empty.PRESENTED_IMAGE_DEFAULT}
        description={
          <div style={{ textAlign: 'center' }}>
            <h2 style={{ color: '#cbd5e1', fontSize: '24px', margin: '0 0 8px 0' }}>Проектов пока нет</h2>
            <p style={{ color: '#cbd5e1', margin: 0 }}>Начните новый проект</p>
          </div>
        }
      >
      </Empty>
    </div>
  );
};