import { Row, Col, Space } from 'antd';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import s from './ProjectDashboard.module.css';
import { AIInsights } from '../../Charts/AIInsights/AIInsights';
import { CycleTimeChart } from '../../Charts/CycleTimeChart/CycleTimeChart';
import { TasksGanttChart } from '../../Charts/TasksGanttChart/TasksGanttChart';
import { TeamWorkloadList } from '../../Charts/TeamWorkloadList/TeamWorkloadList';
import { TeamFocusChart } from '../../Charts/TeamFocusChart/TeamFocusChart';
import { DownloadReportBtn, MetricsSelect, PeriodSelect, DashboardLoader, DashboardEmpty, MetricInfoTooltip, MetricTypeBadge } from '../../../shared/DashboardControls';
import { DashboardPeriod, DashboardMetric } from '../../../../types/dashboard';
import { useProjectTasks, useProjectAIInsights, useProjectCycleTime, useProjectTeamWorkload, useProjectTeamFocus } from '../../../../hooks/useProjectData';

export const ProjectDashboard = () => {
  const [timePeriod, setTimePeriod] = useState<DashboardPeriod>('all');
  const [activeMetrics, setActiveMetrics] = useState<DashboardMetric[]>([
    'effectiveness',
    'activity',
    'codeCount',
  ]);

  const { id } = useParams<{ id: string }>();
  const { data: aiInsights = [], isLoading: isAiInsightsLoading } = useProjectAIInsights(id || '');
  const { data: workloadData, isLoading: isWorkloadLoading } = useProjectTeamWorkload(id || '', timePeriod);
  const { data: cycleTimeData, isLoading: isCycleTimeLoading } = useProjectCycleTime(id || '', timePeriod);
  const { data: focusData, isLoading: isFocusLoading } = useProjectTeamFocus(id || '', timePeriod);
  const { data: projectData, isLoading } = useProjectTasks(id || '', timePeriod);

  const handleDownloadReport = () => {
    console.log('Скачивание отчета за период:', timePeriod);
  };

  // 🔥 УМНОЕ ОПРЕДЕЛЕНИЕ: что показывать
  const getDisplayData = () => {
    if (!cycleTimeData) return { data: null, view: null };

    const stages = cycleTimeData.stages || [];
    const statuses = cycleTimeData.statuses || [];

    // Если есть хотя бы 2 этапа (Внедрение + ещё какой-то)
    const hasValidStages = stages.length >= 2;

    if (hasValidStages) {
      return { data: stages, view: 'stages' };
    }

    // Если нет этапов, пробуем статусы
    if (statuses.length > 0) {
      return { data: statuses, view: 'statuses' };
    }

    // Нет данных
    return { data: null, view: null };
  };

  const displayData = getDisplayData();
  const hasCycleData = displayData.data && displayData.data.length > 0;

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
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle}>ai-выводы</h1>
                {aiInsights && (
                  <MetricInfoTooltip text="ИИ анализирует ключевые метрики проекта и формирует текстовый блок с интерпретацией состояния проекта, выявлением проблем и рекомендациями." />
                )}
              </div>
            </div>
            {isAiInsightsLoading ? (
              <DashboardLoader minHeight="200px" tip='Загружаем выводы' />
            ) : (
              <AIInsights variant="compact" data={aiInsights} />
            )}
          </div>
        </Col>

        <Col span={16}>
          <div className={s.CycleSection}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle} style={{ margin: 0, lineHeight: 1 }}>время цикла</h1>
                {cycleTimeData && (
                  <MetricInfoTooltip text="Среднее время от создания задачи до её закрытия" />
                )}
              </div>
            </div>

            {isCycleTimeLoading ? (
              <DashboardLoader minHeight="200px" tip="Загружаем время цикла..." />
            ) : !hasCycleData ? (
              <DashboardEmpty description="Нет данных по времени цикла за этот период" minHeight="200px" />
            ) : (
              <>
                <div className={s.avgTime}>
                  Среднее время — {cycleTimeData.averageTimeText}
                </div>
                <CycleTimeChart stages={displayData.data} />
              </>
            )}
          </div>
        </Col>
      </Row>

      {/* Остальной код без изменений */}
      <Row gutter={[20, 20]}>
        <Col span={18}>
          <div className={s.gantSection}>
            <div className={s.titles}>
              <div className={s.title}>
                <h1 className={s.blueTitle} style={{ margin: 0, lineHeight: 1 }}>ПЛАН ПО ЗАДАЧАМ</h1>
                {projectData && (
                  <MetricInfoTooltip text="Диаграмма ганта" />
                )}
              </div>
            </div>
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
              <div className={s.titles}>
                <div className={s.title}>
                  <h1 className={s.blueTitle}>ЗАГРУЖЕННОСТЬ КОМАНДЫ</h1>
                  {workloadData && (
                    <MetricInfoTooltip calculationType={workloadData.calculationType} />
                  )}
                </div>
                {workloadData && (
                  <MetricTypeBadge calculationType={workloadData.calculationType} />
                )}
              </div>

              {isWorkloadLoading ? (
                <DashboardLoader minHeight="180px" tip="Загрузка занятости..." />
              ) : !workloadData ? (
                <DashboardEmpty description="Нет данных по загрузке" minHeight="180px" />
              ) : (
                <TeamWorkloadList
                  members={workloadData.members}
                  recommendation={workloadData.recommendationText}
                  calculationType={workloadData.calculationType}
                  balance={workloadData.teamWorkloadBalance}
                />
              )}
            </div>

            <div className={s.focusStats}>
              <div className={s.titles}>
                <div className={s.title}>
                  <h1 className={s.blueTitle} style={{ margin: 0, lineHeight: 1 }}>ФОКУС КОМАНДЫ</h1>
                  {focusData && (
                    <MetricInfoTooltip text="Распределение рабочего времени команды." />
                  )}
                </div>
              </div>
              {isFocusLoading ? (
                <DashboardLoader minHeight="180px" tip="Считаем фокус..." />
              ) : !focusData ? (
                <DashboardEmpty description="Нет данных по фокусу" minHeight="180px" />
              ) : (
                <TeamFocusChart categories={focusData.categories} />
              )}
            </div>
          </Row>
        </Col>
      </Row>
    </div>
  );
};
