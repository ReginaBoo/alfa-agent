import { useState, useEffect } from 'react';
import { dashboardApi } from '../api/dashboardApi';
import { GanttProjectResponse, DashboardPeriod, InsightItem, CycleTimeData, TeamWorkloadData, TeamFocusData } from '../types/dashboard';

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

export const useProjectTeamWorkload = (id: string, period: string) => {
  const [data, setData] = useState<TeamWorkloadData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getProjectTeamWorkload(id, period);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить загруженность команды');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [id, period]);

  return { data, isLoading, error };
};

export const useProjectTeamFocus = (id: string, period: string) => {
  const [data, setData] = useState<TeamFocusData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getProjectTeamFocus(id, period);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить фокус команды');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [id, period]);

  return { data, isLoading, error };
};