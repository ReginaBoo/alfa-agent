import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Typography, Empty } from 'antd';
import { InfoCircleOutlined, FlagFilled, ArrowRightOutlined } from '@ant-design/icons';
import { ProjectStatsItem } from '../../../../types/dashboard';
import s from './ProjectStats.module.css';

const { Title } = Typography;

interface ProjectStatsProps {
  data: ProjectStatsItem[];
}

const getStatusConfig = (status: ProjectStatsItem['status']) => {
  switch (status) {
    case 'error':
      return { color: '#FF4D4F', icon: <InfoCircleOutlined style={{ color: '#FF4D4F' }} /> };
    case 'warning':
      return { color: '#FAAD14', icon: <FlagFilled style={{ color: '#FAAD14' }} /> };
    case 'success':
    default:
      return { color: '#F0F0F0', icon: null };
  }
};

export const ProjectStats = ({ data }: ProjectStatsProps) => {
  const navigate = useNavigate();
  const [currentPage, setCurrentPage] = useState(0);
  const [displayedPage, setDisplayedPage] = useState(0); // Which data is currently rendered
  const [isAnimating, setIsAnimating] = useState(false);
  const itemsPerPage = 6;

  if (!Array.isArray(data) || data.length === 0) {
    return <Empty description="Нет статусов проектов" />;
  }

  const totalPages = Math.ceil(data.length / itemsPerPage);

  // Slice based on the currently displayed data page
  const startIndex = displayedPage * itemsPerPage;
  const visibleData = data.slice(startIndex, startIndex + itemsPerPage);

  // Transition handler for smooth fade
  const handlePageChange = (newPageIndex: number) => {
    if (newPageIndex === currentPage || isAnimating) return;

    setCurrentPage(newPageIndex); // Update the active dot immediately for UI responsiveness
    setIsAnimating(true); // Start the fade-out

    // 1. Wait for cards to fade out completely (300ms transition time)
    setTimeout(() => {
      // 2. Change the actual data in the grid while it's invisible
      setDisplayedPage(newPageIndex);

      // 3. Force a quick browser reflow to ensure the new content is ready,
      // then turn off animation and fade in new content. Using a minimal delay
      // makes this feel like a clean, instant fade-in of the new state.
      setTimeout(() => {
        setIsAnimating(false);
      }, 50); // Small pause to allow data swap in DOM before fade-in re-triggers

    }, 300); // This must match the CSS transition duration
  };

  const handleProjectClick = (jiraUrl: string | undefined) => {
    if (jiraUrl) {
      window.open(jiraUrl, '_blank', 'noopener,noreferrer');
    }
  };

  const handleCardClick = (projectId: number | string | undefined) => {
    if (projectId) {
      navigate(`/project/${projectId}`);
    }
  };

  return (
    <div className={s.carouselContainer}>
      <div className={s.cardsRow}>
        {visibleData.map((p) => {
          const { color, icon } = getStatusConfig(p.status);
          const isError = p.status === 'error';
          const isWarning = p.status === 'warning';

          return (

            <Card
              className={s.projectCard}
              style={{ borderTop: `4px solid ${color}`, width: '100%' }}
              onClick={() => handleCardClick(p.project_id || p.id)}
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
                  <span className={s.noDataText}>Нет данных за период</span>
                </div>
              ) : (
                <div className={s.statsGrid}>
                  <div className={s.statItem}>
                    <div className={s.statValue} style={{ color: isError ? '#FF4D4F' : '#3460DC' }}>
                      {p.stats.workload}%
                    </div>
                    <div className={s.statLabel}>Загрузка</div>
                  </div>

                  <div className={s.statItem}>
                    <div className={s.statValue}>{p.stats.reviewTime}</div>
                    <div className={s.statLabel}>Ревью</div>
                  </div>

                  <div className={s.statItem}>
                    <div className={s.statValue}>{p.stats.bugs}</div>
                    <div className={s.statLabel}>Баги</div>
                  </div>

                  <div className={s.statItem}>
                    <div className={s.statValue} style={{ color: isError ? '#FF4D4F' : isWarning ? '#FAAD14' : '#3460DC' }}>
                      {p.stats.prCount}
                    </div>
                    <div className={s.statLabel}>PR</div>
                  </div>

                  <div className={s.statItem}>
                    <div className={s.statValue}>{p.stats.commits}</div>
                    <div className={s.statLabel}>Коммиты</div>
                  </div>

                  <div className={s.statItem}>
                    <div className={s.statValue} style={{ color: isError ? '#FAAD14' : '#3460DC' }}>
                      {p.stats.sla}%
                    </div>
                    <div className={s.statLabel}>SLA</div>
                  </div>
                </div>
              )}
            </Card>

          );
        })}
      </div>

      {
        totalPages > 1 && (
          <div className={s.customPagination}>
            {Array.from({ length: totalPages }).map((_, pageIndex) => (
              <button
                key={pageIndex}
                type="button"
                className={`${s.dot} ${currentPage === pageIndex ? s.activeDot : ''}`}
                onClick={() => handlePageChange(pageIndex)}
                aria-label={`Перейти к странице ${pageIndex + 1}`}
              />
            ))}
          </div>
        )
      }
    </div >
  );
};
