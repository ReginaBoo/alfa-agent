import { Row, Col, Space } from 'antd';
import { ActivityChart } from '../../Charts/ActivityChart';
import { LoadChart } from '../../Charts/LoadChart/LoadChart';
import { ProjectStats } from '../../Charts/ProjectStats/ProjectStats';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { useState, useMemo } from 'react';
import s from './Dashboard.module.css';
import { useProjectActivity, useAIInsights, useProjectStats, useTeamsLoad, useProjects } from '../../../../hooks/useDashboardData';
import { DownloadReportBtn, DashboardLoader, DashboardEmpty, PeriodSelect, NoProjectsEmpty, MetricInfoTooltip } from '../../../shared/DashboardControls';
import { DashboardPeriod, ProjectStatsItem } from '../../../../types/dashboard';

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

  const normalizedStats = useMemo<ProjectStatsItem[]>(() => {
    if (!projects.length) return [];

    return projects.map((proj) => {
      // Ищем данные от бэкенда по имени проекта (так как на графиках выводятся имена)
      const existingData = projectStats.data?.find(
        (stat: any) => stat.name === proj.name
      );

      // Если данные по проекту есть — отдаем их без изменений
      if (existingData) {
        return existingData;
      }

      // Если данных нет — генерируем карточку-заглушку с флагом noData
      return {
        id: Number(proj.id), // Принудительно приводим к числу
        name: proj.name,
        status: 'success',   // Дефолтный статус из доступных литералов
        noData: true,        // Тот самый флаг для отображения заглушки
        stats: {
          workload: 0,
          reviewTime: '0ч',
          bugs: 0,
          prCount: 0,
          commits: '0',      // Строковое значение согласно интерфейсу
          sla: 0,
        },
      };
    });
  }, [projects, projectStats.data]);

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

      {/* Основная сетка: на мобильных в 1 колонку, на десктопах в 2 колонки */}
      <Row gutter={[24, 24]}>

        {/* ЛЕВАЯ КОЛОНКА (AI + Загрузка) */}
        <Col xs={24} xl={12} className={s.dashboardColumn}>
          <div className={s.dashboardCard}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>ai-выводы</h1>
                {aiInsights && (
                  <MetricInfoTooltip text="ИИ анализирует ключевые метрики..." />
                )}
              </div>
            </div>
            {/* Обертка для контента, которая будет скроллиться */}
            <div className={s.scrollableContent}>
              {aiInsights.isLoading ? (
                <DashboardLoader minHeight="150px" />
              ) : (
                <AIInsights variant="detailed" data={aiInsights.data} />
              )}
            </div>
          </div>

          <div className={s.dashboardCard}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>загруженность команд</h1>
                {teamsLoad && (
                  <MetricInfoTooltip text="Общий уровень загрузки команд по всем проектам" />
                )}
              </div>
            </div>


            <div>
              {teamsLoad.isLoading ? (
                <DashboardLoader minHeight="180px" tip="Анализируем загруженность команд..." />
              ) : (
                <LoadChart backendData={teamsLoad.data} />
              )}
            </div>
          </div>
        </Col>

        {/* ПРАВАЯ КОЛОНКА (Статистика + Активность) */}
        <Col xs={24} xl={12} className={s.dashboardColumn}>
          <div className={s.statsSection}>
            {projectStats.isLoading ? (
              <DashboardLoader minHeight="120px" tip="Считаем коммиты..." />
            ) : (
              <ProjectStats data={normalizedStats} />
            )}
          </div>

          <div className={s.dashboardCard}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>активность по проектам</h1>
                {activity && (
                  <MetricInfoTooltip text="Показывает, насколько активно команда работает..." />
                )}
              </div>
            </div>
            <div className={s.chartContainer}>
              {activity.isLoading ? (
                <DashboardLoader minHeight="200px" tip="Загружаем активность" />
              ) : activity.data.length === 0 ? (
                <DashboardEmpty description="Пока нет активности по проектам" minHeight="200px" />
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