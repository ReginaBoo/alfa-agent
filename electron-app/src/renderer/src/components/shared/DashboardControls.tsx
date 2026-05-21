import { Row, Button, Select, Spin, Empty } from 'antd';
import { DownloadOutlined, DownOutlined } from '@ant-design/icons';
import { DashboardPeriod } from '../../types/dashboard';
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
        { value: 'Весь период', label: 'Весь период' },
        { value: 'Последняя неделя', label: 'Последняя неделя' }
      ]}
    />
  );
};


interface DashboardLoaderProps {
  minHeight?: string | number;
  tip?: string;
}

export const DashboardLoader = ({ minHeight = '200px', tip = 'Загрузка данных...' }: DashboardLoaderProps) => {
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
  minHeight = '200px'
}: DashboardEmptyProps) => {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight,
      textAlign: 'center',
      width: '100%'
    }}>
      <Empty
        description={
          <span style={{ color: '#8c8c8c' }}>
            {description}
          </span>
        }
      />
    </div>
  );
};