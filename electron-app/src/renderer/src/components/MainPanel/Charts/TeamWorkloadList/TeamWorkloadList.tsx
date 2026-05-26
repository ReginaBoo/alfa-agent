import { Progress, Tooltip, Alert } from 'antd';
import s from './TeamWorkloadList.module.css';
import { TeamMemberWorkload, WorkloadCalculationType } from '../../../../types/dashboard';

interface TeamWorkloadListProps {
  members: TeamMemberWorkload[];
  recommendation: string;
  calculationType: WorkloadCalculationType;
  balance: number;
}


const getWorkloadColor = (wi: number) => {
  if (wi < 0.2) return '#4E73F8';  // Недогруз — Спокойный Синий
  if (wi <= 0.6) return '#52C41A'; // Оптимально — Стабильный Зеленый
  if (wi <= 1.0) return '#FAAD14'; // Повышенная нагрузка — Оранжевый
  return '#FF4D4F';                // Перегруз — Критический Красный
};

export const TeamWorkloadList = ({
  members,
  recommendation
}: TeamWorkloadListProps) => {

  if (members.length === 0) return null;

  return (
    <div className={s.card}>
      <div className={s.list}>
        {members.map((user) => {
          const barColor = getWorkloadColor(user.workloadIndex);
          const realPercentage = Math.round(user.workloadIndex * 100);
          const displayProgress = Math.min(realPercentage, 100);

          return (
            <div key={user.id} className={s.item}>
              <div className={s.nameGroup}>
                <span className={s.name}>{user.name}</span>
              </div>

              <div className={s.progressWrapper}>
                <Tooltip title={`Индекс нагрузки (WI): ${user.workloadIndex.toFixed(2)}`}>
                  <Progress
                    percent={displayProgress}
                    showInfo={false}
                    strokeColor={barColor}
                    size={{ height: 10 }}
                  />
                </Tooltip>
              </div>

              <span className={s.percent} style={{ fontWeight: 500 }}>
                {realPercentage}%
              </span>
            </div>
          );
        })}
      </div>

      {recommendation && (
        <div className={s.footer}>
          <Alert title={recommendation} type="info" showIcon={false} className={s.suggestionAlert} />
        </div>
      )}
    </div>
  );
};