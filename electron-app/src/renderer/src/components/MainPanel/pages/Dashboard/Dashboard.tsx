import { Row, Col, Space } from 'antd';
import { ActivityChart } from '../../Charts/ActivityChart';
import { LoadChart } from '../../Charts/LoadChart/LoadChart';
import { ProjectStats } from '../../Charts/ProjectStats/ProjectStats';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { useState } from 'react';
import s from './Dashboard.module.css';
import { useProjectActivity, useAIInsights, useProjectStats, useTeamsLoad, useProjects } from '../../../../hooks/useDashboardData';
import { DownloadReportBtn, DashboardLoader, DashboardEmpty, PeriodSelect, NoProjectsEmpty, MetricInfoTooltip } from '../../../shared/DashboardControls';
import { DashboardPeriod } from '../../../../types/dashboard';

export const Dashboard = () => {
  const [timePeriod, setTimePeriod] = useState<DashboardPeriod>('all');

  const activity = useProjectActivity(timePeriod);
  const aiInsights = useAIInsights();
  const projectStats = useProjectStats(timePeriod);
  const { data: projects = [], isLoading: isProjectsLoading } = useProjects();
  const teamsLoad = useTeamsLoad(timePeriod);
  const handleDownloadReport = () => {
    console.log('Скачивание отчета за период:', timePeriod);
  };

  if (isProjectsLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <DashboardLoader minHeight="100px" tip="Загрузка..." />
      </div>
    );
  }

  if (projects.length === 0) {
    return <NoProjectsEmpty />;
  }

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
                <div className={s.titles}>
                  <div className={s.title}>
                    <h1 className={s.blueTitle}>ai-выводы</h1>
                    {aiInsights && (
                      <MetricInfoTooltip text="ИИ анализирует ключевые метрики проектов и формирует текстовый блок с интерпретацией состояния проектов, выявлением проблем и рекомендациями." />
                    )}
                  </div>
                </div>
                {aiInsights.isLoading ? (
                  <DashboardLoader minHeight="200px" />
                ) : (
                  <AIInsights variant="detailed" data={aiInsights.data} />
                )}
              </div>
            </Col>

            <Col span={24}>
              <div className={s.loadSection} style={{ marginBottom: '24px' }}>
                <div className={s.titles}>
                  <div className={s.title}>
                    <h1 className={s.blueTitle}>загруженность команд</h1>
                    {teamsLoad && (
                      <MetricInfoTooltip text="Общий уровень загрузки команд по всем проектам" />
                    )}
                  </div>
                </div>
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
              <div className={s.statsSection}>
                {projectStats.isLoading ? (
                  <DashboardLoader minHeight="120px" tip="Считаем коммиты и пул-реквесты..." />
                ) : (
                  <ProjectStats data={projectStats.data} />
                )}
              </div>
            </Col>

            <Col span={24}>
              <div className={s.chartSection}>
                <div className={s.titles}>
                  <div className={s.title}>
                    <h1 className={s.blueTitle}>активность по проектам</h1>
                    {activity && (
                      <MetricInfoTooltip text="Показывает, насколько активно команда работает над проектом, учитывая действия: коммиты, Pull Requests и обновления задач в Jira" />
                    )}
                  </div>
                </div>
                {activity.isLoading ? (
                  <DashboardLoader minHeight="200px" tip="Загружаем активность" />
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