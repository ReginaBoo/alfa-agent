import { Row, Col, Space, Button, Select } from 'antd';

import s from './ProjectDashboard.module.css';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { CycleTimeChart } from '../../Charts/CycleTimeChart/CycleTimeChart';
import { TasksGanttChart } from '../../Charts/TasksGanttChart/TasksGanttChart';
import { TeamWorkloadList } from '../../Charts/TeamWorkloadList/TeamWorkloadList';
import { TeamFocusChart } from '../../Charts/TeamFocusChart/TeamFocusChart';
import { DownloadOutlined, DownOutlined } from '@ant-design/icons';
export const ProjectDashboard = () => {

  return (
    <div className={s.wrapper}>
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
            <Select
              className={s.metricsSelect}
              defaultValue="Метрики"
              suffixIcon={<DownOutlined />}
              options={[{
                value: 'Метрики',
                label: (
                  <Space>
                    <span>Метрики</span>
                  </Space>
                )
              },]}
            />
          </Space>
        </Col>
      </Row>

      <Row gutter={[20, 20]} style={{ marginBottom: 10 }}>
        <Col span={8}>
          <div className={s.aiSection}>
            <h1 className={s.blueTitle}>AI-ВЫВОДЫ</h1>
            <AIInsights variant="compact" />
          </div>
        </Col>
        <Col span={16}>
          <div className={s.CycleSection}>
            <h1 className={s.blueTitle}>ВРЕМЯ ЦИКЛА</h1>
            <div className={s.avgTime}>
              Среднее время — 5 дней, 1 час
            </div>
            <CycleTimeChart />
          </div>
        </Col>
      </Row>

      <Row gutter={[20, 20]}>
        <Col span={18}>
          <TasksGanttChart start='2026-03-01' end='2026-07-31' />
        </Col>
        <Col span={6}>
          <Row gutter={[16, 16]}>
            <div className={s.workloadStats}>
              <TeamWorkloadList />
            </div >
            <div className={s.focusStats}>
              <TeamFocusChart />
            </div>
          </Row >
        </Col>
      </Row>
    </div>
  );
};