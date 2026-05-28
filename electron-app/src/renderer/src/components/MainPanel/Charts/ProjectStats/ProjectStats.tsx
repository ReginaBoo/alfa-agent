import { Row, Col, Card, Typography, Empty, Carousel } from 'antd';
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
    case 'success':
      return { color: '#459AFF' };
    default:
      return { color: '#F0F0F0', icon: null };
  }
};

const chunkArray = <T,>(arr: T[], size: number): T[][] => {
  const result: T[][] = [];

  for (let i = 0; i < arr.length; i += size) {
    result.push(arr.slice(i, i + size));
  }

  return result;
};
export const ProjectStats = ({ data }: ProjectStatsProps) => {
  if (!Array.isArray(data) || !data || data.length === 0) return <Empty description="Нет статусов проектов" />;;

  const handleProjectClick = (jiraUrl: string | undefined) => {
    if (jiraUrl) {
      window.open(jiraUrl, '_blank', 'noopener,noreferrer');
    }
  };
  const slides = chunkArray(data, 6);
  return (
    <Carousel dots arrows className={s.carousel}>
      {slides.map((group, slideIndex) => (
        <div key={slideIndex}>
          <Row gutter={[16, 16]}>
            {group.map((p, index) => {
              const { color, icon } = getStatusConfig(p.status);
              const isError = p.status === 'error';
              const isWarning = p.status === 'warning';

              return (
                <Col
                  xs={24}
                  sm={12}
                  xl={8}
                  key={`${p.id}-${index}`}
                  style={{ display: 'flex' }}
                >
                  <Card
                    className={s.projectCard}
                    style={{ borderTop: `4px solid ${color}` }}
                  >
                    <div className={s.cardHeader}>
                      <Title level={5} className={s.projectTitle}>
                        <span title={p.name}>{p.name}</span>

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

                    {p.noData ? (
                      <div className={s.noDataWrapper}>
                        <span className={s.noDataText}>
                          Нет данных за период
                        </span>
                      </div>
                    ) : (
                      <div className={s.statsGrid}>
                        <div className={s.statItem}>
                          <div
                            className={s.statValue}
                            style={{
                              color: isError ? '#FF4D4F' : '#3460DC',
                            }}
                          >
                            {p.stats.workload}%
                          </div>
                          <div className={s.statLabel}>Загрузка</div>
                        </div>

                        <div className={s.statItem}>
                          <div className={s.statValue}>
                            {p.stats.reviewTime}
                          </div>
                          <div className={s.statLabel}>Ревью</div>
                        </div>

                        <div className={s.statItem}>
                          <div className={s.statValue}>
                            {p.stats.bugs}
                          </div>
                          <div className={s.statLabel}>Баги</div>
                        </div>

                        <div className={s.statItem}>
                          <div
                            className={s.statValue}
                            style={{
                              color: isError
                                ? '#FF4D4F'
                                : isWarning
                                  ? '#FAAD14'
                                  : '#3460DC',
                            }}
                          >
                            {p.stats.prCount}
                          </div>
                          <div className={s.statLabel}>PR</div>
                        </div>

                        <div className={s.statItem}>
                          <div className={s.statValue}>
                            {p.stats.commits}
                          </div>
                          <div className={s.statLabel}>Коммиты</div>
                        </div>

                        <div className={s.statItem}>
                          <div
                            className={s.statValue}
                            style={{
                              color: isError ? '#FAAD14' : '#3460DC',
                            }}
                          >
                            {p.stats.sla}%
                          </div>
                          <div className={s.statLabel}>SLA</div>
                        </div>
                      </div>
                    )}
                  </Card>
                </Col>
              );
            })}
          </Row>
        </div>
      ))}
    </Carousel>
  );
};
