import { Progress, Tooltip, Alert } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';
import s from './TeamWorkloadList.module.css';

interface TeamMember {
  id: string;
  name: string;
  workload: number;
}

const teamData: TeamMember[] = [
  { id: '1', name: 'Иван', workload: 115 },
  { id: '2', name: 'Анна', workload: 55 },
  { id: '3', name: 'Дмитрий', workload: 70 },
  { id: '4', name: 'Соня', workload: 24 },
];

export const TeamWorkloadList = () => {
  // Находим самого свободного сотрудника для совета
  const leastBusy = [...teamData].sort((a, b) => a.workload - b.workload)[0];

  return (
    <div className={s.card}>
      <div className={s.header}>
        <div className={s.titleGroup}>
          <h2 className={s.title}>ЗАГРУЖЕННОСТЬ КОМАНДЫ</h2>
          <Tooltip title="Процент загрузки на основе Story Points в Jira">
            <InfoCircleOutlined className={s.infoIcon} />
          </Tooltip>
        </div>
        <div className={s.jiraLabel}>
          JIRA<br />SP
        </div>
      </div>

      <div className={s.list}>
        {teamData.map((user) => (
          <div key={user.id} className={s.item}>
            <span className={s.name}>{user.name}</span>
            <div className={s.progressWrapper}>
              <Progress
                percent={user.workload}
                showInfo={false}
                strokeColor={user.workload > 100 ? '#ff4d4f' : '#4e73f8'}
                size={{ height: 10 }}
              />
            </div>
            <span className={s.percent}>{user.workload}%</span>
          </div>
        ))}
      </div>

      <div className={s.footer}>
        <Alert
          title={`${leastBusy.name} свободна. Можно передать ей задачу по фиксу багов`}
          type="info"
          showIcon={false}
          className={s.suggestionAlert}
        />
      </div>
    </div>
  );
};