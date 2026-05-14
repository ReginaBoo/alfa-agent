import { Row, Col, Button, Select, Space } from 'antd';
import { DownloadOutlined, DownOutlined } from '@ant-design/icons';
import { ActivityChart } from '../../Charts/ActivityChart';
import { LoadChart } from '../../Charts/LoadChart';
import { ProjectStats } from '../../Charts/ProjectStats/ProjectStats';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import s from './Dashboard.module.css';


const mockBackendData = [
  // МАРТ
  // Проект 1 (Стабильный рост)
  { date: '2026-03-01', value: 15, project: 'Проект 1' },
  { date: '2026-03-08', value: 25, project: 'Проект 1' },
  { date: '2026-03-15', value: 35, project: 'Проект 1' },
  { date: '2026-03-22', value: 50, project: 'Проект 1' },
  { date: '2026-03-29', value: 55, project: 'Проект 1' },

  // Проект 2 (Высокая активность в середине месяца)
  { date: '2026-03-01', value: 40, project: 'Проект 2' },
  { date: '2026-03-08', value: 80, project: 'Проект 2' },
  { date: '2026-03-15', value: 95, project: 'Проект 2' },
  { date: '2026-03-22', value: 60, project: 'Проект 2' },
  { date: '2026-03-29', value: 30, project: 'Проект 2' },

  // Проект 3 (Постепенный разгон)
  { date: '2026-03-01', value: 5, project: 'Проект 3' },
  { date: '2026-03-15', value: 20, project: 'Проект 3' },
  { date: '2026-03-29', value: 45, project: 'Проект 3' },

  // АПРЕЛЬ
  // Проект 1
  { date: '2026-04-05', value: 65, project: 'Проект 1' },
  { date: '2026-04-12', value: 75, project: 'Проект 1' },
  { date: '2026-04-19', value: 85, project: 'Проект 1' },
  { date: '2026-04-26', value: 90, project: 'Проект 1' },

  // Проект 2
  { date: '2026-04-05', value: 20, project: 'Проект 2' },
  { date: '2026-04-12', value: 15, project: 'Проект 2' },
  { date: '2026-04-19', value: 40, project: 'Проект 2' },
  { date: '2026-04-26', value: 55, project: 'Проект 2' },

  // Проект 3
  { date: '2026-04-05', value: 50, project: 'Проект 3' },
  { date: '2026-04-12', value: 60, project: 'Проект 3' },
  { date: '2026-04-19', value: 55, project: 'Проект 3' },
  { date: '2026-04-26', value: 70, project: 'Проект 3' },
];

export const Dashboard = () => {
  return (
    <div className={s.dashboardWrapper}>
      <Row justify="end" style={{ marginBottom: 20 }}>
        <Col>
          <Space size={16}>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              size="large"
              className={s.downloadBtn}
            >
              Скачать отчет
            </Button>
            <Select
              className={s.projectSelect}
              defaultValue="Весь период"
              suffixIcon={<DownOutlined />}
              options={[{
                value: 'Весь период',
                label: (
                  <Space>
                    <span>Весь период</span>
                  </Space>
                )
              },
              {
                value: 'Последняя неделя',
                label: (
                  <Space>
                    <span>Последняя неделя</span>
                  </Space>
                )
              },]}
            />
          </Space>
        </Col>
      </Row>

      <Row gutter={[24, 24]} >

        <Col xs={24} lg={12}>
          <Row gutter={[16, 16]}>

            <Col span={24}>
              <div className={s.aiSection}>
                <h1 className={s.blueTitle}>AI-ВЫВОДЫ</h1>
                <AIInsights variant="detailed" />
              </div>
            </Col>

            <Col span={24}>
              <div className={s.loadSection} style={{ marginBottom: '24px' }}>
                <h1 className={s.blueTitle}>ЗАГРУЖЕННОСТЬ ПРОЕКТОВ</h1>
                <LoadChart />
              </div>
            </Col>
          </Row>
        </Col>

        <Col xs={24} lg={12}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <ProjectStats />
            </Col>

            <Col span={24}>
              <div className={s.chartSection}>
                <h1 className={s.blueTitle}>АКТИВНОСТЬ ПО ПРОЕКТАМ</h1>
                <ActivityChart backendData={mockBackendData} />
              </div>
            </Col>
          </Row>
        </Col>
      </Row >
    </div >
  );
};