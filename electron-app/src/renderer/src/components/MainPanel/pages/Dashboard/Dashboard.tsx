import { Row, Col, Space } from 'antd';
import { ActivityChart } from '../../Charts/ActivityChart';
import { LoadChart } from '../../Charts/LoadChart/LoadChart';
import { ProjectStats } from '../../Charts/ProjectStats/ProjectStats';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { useState, useMemo } from 'react';
import s from './Dashboard.module.css';
import { useProjectActivity, useAIInsights, useProjectStats, useTeamsLoad, useProjects } from '../../../../hooks/useDashboardData';
import { DashboardLoader, DashboardEmpty, PeriodSelect, NoProjectsEmpty, MetricInfoTooltip } from '../../../shared/DashboardControls';
import { DashboardPeriod, ProjectStatsItem } from '../../../../types/dashboard';
import { useMinLoading } from '../../../../hooks/useMinLoading'
export const Dashboard = () => {
  const [timePeriod, setTimePeriod] = useState<DashboardPeriod>('all');

  const activity = useProjectActivity(timePeriod);
  const aiInsights = useAIInsights();
  const projectStats = useProjectStats(timePeriod);
  const { data: projects = [], isLoading: isProjectsLoading } = useProjects();
  const teamsLoad = useTeamsLoad(timePeriod);

  // const handleDownloadReport = () => {
  //   console.log('Скачивание отчета за период:', timePeriod);
  // };

  const normalizedStats = useMemo<ProjectStatsItem[]>(() => {
    if (!projects.length) return [];

    return projects.map((proj) => {
      const existingData = projectStats.data?.find(
        (stat: any) => stat.name === proj.name
      );

      if (existingData) return existingData;

      return {
        id: Number(proj.id),
        name: proj.name,
        status: 'success',
        noData: true,
        stats: {
          workload: 0,
          reviewTime: '0ч',
          bugs: 0,
          prCount: 0,
          commits: '0',
          sla: 0,
        },
      };
    });
  }, [projects, projectStats.data]);

  const showLoader = useMinLoading(isProjectsLoading, 250);
  if (showLoader) {
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
            {/* <DownloadReportBtn onDownload={handleDownloadReport} /> */}
            <PeriodSelect value={timePeriod} onChange={setTimePeriod} />
          </Space>
        </Col>
      </Row>

      {/* Сетка с корректным классом dashboardGridRow */}
      <Row gutter={[24, 24]} align="stretch" className={s.dashboardGridRow}>

        {/* ЛЕВАЯ КОЛОНКА (AI-выводы + Загруженность команд) */}
        <Col xs={24} xl={12} className={s.dashboardColumn}>
          {/* AI-выводы */}
          <div className={`${s.dashboardCard} ${s.aiCard}`}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>ai-выводы</h1>
                {aiInsights && <MetricInfoTooltip text="ИИ анализирует ключевые метрики..." />}
              </div>
            </div>
            <div className={s.scrollableContent}>
              {aiInsights.isLoading ? (
                <DashboardLoader minHeight="150px" />
              ) : (
                <AIInsights variant="detailed" data={aiInsights.data} />
              )}
            </div>
          </div>

          {/* Загруженность команд */}
          <div className={`${s.dashboardCard} ${s.fillCard}`}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>загруженность команд</h1>
                {teamsLoad && <MetricInfoTooltip text="Общий уровень загрузки команд" />}
              </div>
            </div>
            <div className={s.chartContainer}>
              {teamsLoad.isLoading ? (
                <DashboardLoader minHeight="180px" tip="Анализируем загруженность..." />
              ) : (
                <LoadChart backendData={teamsLoad.data} />
              )}
            </div>
          </div>
        </Col>

        {/* ПРАВАЯ КОЛОНКА (Статистика проектов + Активность по проектам) */}
        <Col xs={24} xl={12} className={s.dashboardColumn}>
          {/* Статистика по проектам (мини-карточки сверху) */}
          <div className={s.statsSection}>
            {projectStats.isLoading ? (
              <DashboardLoader minHeight="120px" tip="Считаем коммиты..." />
            ) : (
              <ProjectStats data={normalizedStats} />
            )}
          </div>

          {/* Активность по проектам */}
          <div className={`${s.dashboardCard} ${s.fillCard}`}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>активность по проектам</h1>
                {activity && <MetricInfoTooltip text="Показывает активность работы..." />}
              </div>
            </div>
            <div className={s.chartContainer}>
              {activity.isLoading ? (
                <div className={s.emptyState}>
                  <DashboardLoader minHeight="200px" tip="Загружаем активность" />
                </div>
              ) : activity.data.length === 0 ? (
                <div className={s.emptyState}>
                  <DashboardEmpty description="Пока нет активности по проектам" />
                </div>
              ) : (
                <ActivityChart backendData={activity.data} />
              )}
            </div>
          </div>
        </Col>

      </Row>
    </div>
  );
};