import { Row, Col, Card, Typography, Empty } from 'antd';
import { InfoCircleOutlined, FlagFilled, ArrowRightOutlined } from '@ant-design/icons';
import { ProjectStatsItem } from '../../../../types/dashboard';
import s from './ProjectStats.module.css';

const { Title } = Typography;

interface ProjectStatsProps {
  data: ProjectStatsItem[];
}

// Конфигуратор темы карточки в зависимости от статуса проекта
const getStatusConfig = (status: ProjectStatsItem['status']) => {
  switch (status) {
    case 'error':
      return { color: '#FF4D4F', icon: <InfoCircleOutlined style={{ color: '#FF4D4F' }} /> };
    case 'warning':
      return { color: '#FAAD14', icon: <FlagFilled style={{ color: '#FAAD14' }} /> };
    case 'normal':
    default:
      return { color: '#F0F0F0', icon: null };
  }
};

export const ProjectStats = ({ data }: ProjectStatsProps) => {
  if (!Array.isArray(data) || !data || data.length === 0) return <Empty description="Нет статусов проектов" />;;

  const handleProjectClick = (jiraUrl: string | undefined) => {
    if (jiraUrl) {
      window.open(jiraUrl, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <Row gutter={[16, 16]}>
      {data.map((p) => {
        const { color, icon } = getStatusConfig(p.status);
        const isError = p.status === 'error';
        const isWarning = p.status === 'warning';

        return (
          <Col xs={24} sm={12} xl={6} key={p.id}>
            <Card
              className={s.projectCard}
              style={{ borderTop: `4px solid ${color}` }}
            >
              <div className={s.cardHeader}>
                <Title level={5} className={s.projectTitle}>
                  {p.name}
                  {p.jira_url && (
                    <ArrowRightOutlined
                      className={s.arrow}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleProjectClick(p.jira_url);
                      }}
                    />
                  )}
                </Title>
                {icon}
              </div>

              <div className={s.statsGrid}>
                {/* Загрузка */}
                <div className={s.statItem}>
                  <div className={s.statValue} style={{ color: isError ? '#FF4D4F' : '#3460DC' }}>
                    {p.stats.workload}%
                  </div>
                  <div className={s.statLabel}>Загрузка</div>
                </div>

                {/* Ревью */}
                <div className={s.statItem}>
                  <div className={s.statValue}>{p.stats.reviewTime}</div>
                  <div className={s.statLabel}>Ревью</div>
                </div>

                {/* Баги */}
                <div className={s.statItem}>
                  <div className={s.statValue}>{p.stats.bugs}</div>
                  <div className={s.statLabel}>Баги</div>
                </div>

                {/* PR */}
                <div className={s.statItem}>
                  <div className={s.statValue} style={{ color: isError ? '#FF4D4F' : isWarning ? '#FAAD14' : '#3460DC' }}>
                    {p.stats.prCount}
                  </div>
                  <div className={s.statLabel}>PR</div>
                </div>

                {/* Коммиты */}
                <div className={s.statItem}>
                  <div className={s.statValue}>{p.stats.commits}</div>
                  <div className={s.statLabel}>Коммиты</div>
                </div>

                {/* SLA */}
                <div className={s.statItem}>
                  <div className={s.statValue} style={{ color: isError ? '#FAAD14' : '#3460DC' }}>
                    {p.stats.sla}%
                  </div>
                  <div className={s.statLabel}>SLA</div>
                </div>
              </div>
            </Card>
          </Col>
        );
      })}
    </Row>
  );
};
