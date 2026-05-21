import { useState, useEffect } from 'react';
import { dashboardApi } from '../api/dashboardApi'; // Корректный путь к вашему API файлу
import { GanttProjectResponse, DashboardPeriod } from '../types/dashboard';

export const useProjectTasks = (projectId: string, period: DashboardPeriod) => {
  const [data, setData] = useState<GanttProjectResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!projectId) return;

    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await dashboardApi.getProjectTasks(projectId, period);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Не удалось загрузить задачи'));
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [projectId, period]); // Хук реагирует и на смену периода, и на смену проекта!

  return { data, isLoading, error };
};