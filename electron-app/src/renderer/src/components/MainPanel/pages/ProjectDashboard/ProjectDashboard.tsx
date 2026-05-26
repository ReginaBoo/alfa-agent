import { Row, Col, Space } from 'antd';

import s from './ProjectDashboard.module.css';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { CycleTimeChart } from '../../Charts/CycleTimeChart/CycleTimeChart';
import { TasksGanttChart } from '../../Charts/TasksGanttChart/TasksGanttChart';
import { TeamWorkloadList } from '../../Charts/TeamWorkloadList/TeamWorkloadList';
import { TeamFocusChart } from '../../Charts/TeamFocusChart/TeamFocusChart';
import { DownloadReportBtn, MetricsSelect, PeriodSelect, DashboardLoader, DashboardEmpty } from '../../../shared/DashboardControls';
import { DashboardPeriod, DashboardMetric } from '../../../../types/dashboard';
import { useState } from 'react';
import { useProjectTasks, useProjectAIInsights, useProjectCycleTime } from '../../../../hooks/useProjectData';
import { useParams } from 'react-router-dom';


export const ProjectDashboard = () => {
  const [timePeriod, setTimePeriod] = useState<DashboardPeriod>('all');
  const [activeMetrics, setActiveMetrics] = useState<DashboardMetric[]>([
    'effectiveness',
    'activity',
    'codeCount',
  ]);
  const { id } = useParams<{ id: string }>();
  const { data: aiInsights = [], isLoading: isAiInsightsLoading } = useProjectAIInsights(id || '');

  const { data: cycleTimeData, isLoading: isCycleTimeLoading } = useProjectCycleTime(id || '', timePeriod);
  const { data: projectData, isLoading } = useProjectTasks(id || '', timePeriod);
  const handleDownloadReport = () => {
    console.log('Скачивание отчета за период:', timePeriod);
  };

  return (
    <div className={s.wrapper}>
      <Row justify="end" style={{ marginBottom: 20 }}>
        <Col>
          <Space size={16}>
            <DownloadReportBtn onDownload={handleDownloadReport} />
            <PeriodSelect value={timePeriod} onChange={setTimePeriod} />
            <MetricsSelect
              value={activeMetrics}
              onChange={(metrics) => setActiveMetrics(metrics)}
            />
          </Space>
        </Col>
      </Row>

      <Row gutter={[20, 20]} style={{ marginBottom: 10 }}>
        <Col span={8}>
          <div className={s.aiSection}>
            <h1 className={s.blueTitle}>AI-ВЫВОДЫ</h1>
            {isAiInsightsLoading ? (
              <DashboardLoader minHeight="200px" tip='Загружаем выводы' />
            ) : (
              <AIInsights variant="compact" data={aiInsights} />)}
          </div>
        </Col>

        <Col span={16}>
          <div className={s.CycleSection}>
            <h1 className={s.blueTitle}>ВРЕМЯ ЦИКЛА</h1>

            {isCycleTimeLoading ? (
              <DashboardLoader minHeight="200px" tip="Загружаем время цикла..." />
            ) : !cycleTimeData || cycleTimeData.stages.length === 0 ? (
              <DashboardEmpty description="Нет данных по времени цикла за этот период" minHeight="200px" />
            ) : (
              <>
                <div className={s.avgTime}>
                  Среднее время — {cycleTimeData.averageTimeText}
                </div>
                <CycleTimeChart stages={cycleTimeData.stages} />
              </>
            )}
          </div>
        </Col>
      </Row>

      <Row gutter={[20, 20]}>
        <Col span={18}>
          <div className={s.gantSection}>
            <h1 className={s.blueTitle}> ПЛАН ПО ЗАДАЧАМ</h1>
            {isLoading ? (
              <DashboardLoader minHeight="200px" tip='Загружаем план' />
            ) : !projectData ? (
              <DashboardEmpty description="Пока нет плана по задачам" minHeight="200px" />
            ) : (
              <TasksGanttChart
                data={projectData?.tasks || []}
                viewRange={projectData?.viewRange || { start: '2026-03-01', end: '2026-03-31' }}
              />

            )}

          </div>
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
    </div >
  );
};