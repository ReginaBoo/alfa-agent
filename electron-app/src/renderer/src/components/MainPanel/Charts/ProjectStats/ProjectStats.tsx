import { Row, Col, Card, Typography } from 'antd';
import { InfoCircleOutlined, FlagFilled, ArrowRightOutlined } from '@ant-design/icons';
import s from './ProjectStats.module.css'; // Создадим этот файл ниже

const { Title } = Typography;

const projects = [
  { id: 1, name: 'Проект 1', color: '#FF4D4F', icon: <InfoCircleOutlined style={{ color: '#FF4D4F' }} /> },
  { id: 2, name: 'Проект 2', color: '#FAAD14', icon: <FlagFilled style={{ color: '#FAAD14' }} /> },
  { id: 3, name: 'Проект 3', color: '#F0F0F0', icon: null },
  { id: 4, name: 'Проект 4', color: '#F0F0F0', icon: null },
];

export const ProjectStats = () => {
  return (
    <Row gutter={[16, 16]}>
      {projects.map((p) => (
        <Col xs={24} sm={12} xl={6} key={p.id}>
          <Card
            className={s.projectCard}
            style={{ borderTop: `4px solid ${p.color}` }}
          >
            <div className={s.cardHeader}>
              <Title level={5} className={s.projectTitle}>
                {p.name} <ArrowRightOutlined className={s.arrow} />
              </Title>
              {p.icon}
            </div>

            <div className={s.statsGrid}>
              <div className={s.statItem}>
                <div className={s.statValue} style={{ color: p.id === 1 ? '#FF4D4F' : '#3460DC' }}>105%</div>
                <div className={s.statLabel}>Загрузка</div>
              </div>
              <div className={s.statItem}>
                <div className={s.statValue}>42ч</div>
                <div className={s.statLabel}>Ревью</div>
              </div>
              <div className={s.statItem}>
                <div className={s.statValue}>12</div>
                <div className={s.statLabel}>Баги</div>
              </div>
              <div className={s.statItem}>
                <div className={s.statValue} style={{ color: p.id === 1 ? '#FF4D4F' : p.id === 2 ? '#FAAD14' : '#3460DC' }}>12</div>
                <div className={s.statLabel}>PR</div>
              </div>
              <div className={s.statItem}>
                <div className={s.statValue}>120↑</div>
                <div className={s.statLabel}>Коммиты</div>
              </div>
              <div className={s.statItem}>
                <div className={s.statValue} style={{ color: p.id === 1 ? '#FAAD14' : '#3460DC' }}>72%</div>
                <div className={s.statLabel}>SLA</div>
              </div>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  );
};