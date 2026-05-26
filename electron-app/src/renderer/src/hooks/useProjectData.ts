import { useState, useEffect } from 'react';
import { dashboardApi } from '../api/dashboardApi'; // Корректный путь к вашему API файлу
import { GanttProjectResponse, DashboardPeriod, InsightItem, CycleTimeData } from '../types/dashboard';

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


export const useProjectAIInsights = (id: string) => {
  const [data, setData] = useState<InsightItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getProjectAIInsights(id);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить AI-выводы');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []); // Пустой массив — запрос только при монтировании дашборда

  return { data, isLoading, error };
};



export const useProjectCycleTime = (id: string, period: string) => {
  const [data, setData] = useState<CycleTimeData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Если id проекта еще не пришел (например, роутер не успел распарсить параметры), ничего не делаем
    if (!id) return;

    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        // Вызываем наш новый метод и передаем и id, и выбранный период
        const res = await dashboardApi.getProjectCycleTime(id, period);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить данные времени цикла');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [id, period]); // Хук перезапустится при изменении проекта или временного периода

  return { data, isLoading, error };
};