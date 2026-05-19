import { Row, Col, Space } from 'antd';
import { ActivityChart } from '../../Charts/ActivityChart';
import { LoadChart } from '../../Charts/LoadChart/LoadChart';
import { ProjectStats } from '../../Charts/ProjectStats/ProjectStats';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { useState } from 'react';
import s from './Dashboard.module.css';
import { useProjectActivity, useAIInsights, useProjectStats, useTeamsLoad } from '../../../../hooks/useDashboardData';
import { DownloadReportBtn, DashboardLoader, DashboardEmpty, PeriodSelect } from '../../../shared/DashboardControls';
import { DashboardPeriod } from '../../../../types/dashboard';

export const Dashboard = () => {
  const [timePeriod, setTimePeriod] = useState<DashboardPeriod>('Весь период');

  const activity = useProjectActivity(timePeriod);
  const aiInsights = useAIInsights();
  const projectStats = useProjectStats(timePeriod);

  const teamsLoad = useTeamsLoad(timePeriod);
  const handleDownloadReport = () => {
    console.log('Скачивание отчета за период:', timePeriod);
  };
  return (
    <div className={s.dashboardWrapper}>
      <Row justify="end" style={{ marginBottom: 20 }}>
        <Col>
          <Space size={16}>
            <DownloadReportBtn onDownload={handleDownloadReport} />
            <PeriodSelect value={timePeriod} onChange={setTimePeriod} />
          </Space>
        </Col>
      </Row>

      <Row gutter={[24, 24]} >
        <Col xs={24} lg={12}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <div className={s.aiSection}>
                <h1 className={s.blueTitle}>AI-ВЫВОДЫ</h1>
                {aiInsights.isLoading ? (
                  <DashboardLoader minHeight="200px" />
                ) : (
                  <AIInsights variant="detailed" data={aiInsights.data} />
                )}
              </div>
            </Col>

            <Col span={24}>
              <div className={s.loadSection} style={{ marginBottom: '24px' }}>
                <h1 className={s.blueTitle}>ЗАГРУЖЕННОСТЬ КОМАНД</h1>

                {teamsLoad.isLoading ? (
                  <DashboardLoader minHeight="240px" tip="Анализируем загруженность команд..." />
                ) : (
                  <LoadChart backendData={teamsLoad.data} />
                )}
              </div>
            </Col>

          </Row>
        </Col>

        <Col xs={24} lg={12}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              {projectStats.isLoading ? (
                <DashboardLoader minHeight="120px" tip="Считаем коммиты и пул-реквесты..." />
              ) : (
                <ProjectStats data={projectStats.data} />
              )}
            </Col>

            <Col span={24}>
              <div className={s.chartSection}>
                <h1 className={s.blueTitle}>АКТИВНОСТЬ ПО ПРОЕКТАМ</h1>

                {activity.isLoading ? (
                  <DashboardLoader minHeight="200px" />
                ) : activity.data.length === 0 ? (
                  <DashboardEmpty description="Пока нет активности по проектам" minHeight="200px" />
                ) : (
                  <ActivityChart backendData={activity.data} />
                )}
              </div>
            </Col>

          </Row>
        </Col>
      </Row >

    </div >
  );
};