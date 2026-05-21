import { useState, useEffect } from 'react';
import { dashboardApi } from '../api/dashboardApi';
import { ProjectActivityItem, InsightItem, ProjectStatsItem, DashboardPeriod, LoadChartItem, ProjectItem } from '../types/dashboard';

// 1. Хук для активности проектов
export const useProjectActivity = (period: DashboardPeriod) => {
  const [data, setData] = useState<ProjectActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getProjectActivity(period);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить активность');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [period]);

  return { data, isLoading, error };
};

// 2. Хук для AI-инсайтов (не зависит от периода, запрашивается один раз)
export const useAIInsights = () => {
  const [data, setData] = useState<InsightItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getAIInsights();
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

// 3. Хук для статистики карточек проектов
export const useProjectStats = (period: DashboardPeriod) => {
  const [data, setData] = useState<ProjectStatsItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getProjectStats(period);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить статистику');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [period]);

  return { data, isLoading, error };
};

// 4. Хук для загруженности команд
export const useTeamsLoad = (period: DashboardPeriod) => {
  const [data, setData] = useState<LoadChartItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await dashboardApi.getTeamsLoad(period);
        setData(res);
      } catch (err: any) {
        setError(err.message || 'Не удалось загрузить данные загруженности');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, [period]);

  return { data, isLoading, error };
};


//Список проектов
export const useProjects = () => {
  const [data, setData] = useState<ProjectItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<any>(null);

  useEffect(() => {
    dashboardApi.getProjects()
      .then(res => setData(res))
      .catch(err => setError(err))
      .finally(() => setIsLoading(false));
  }, []);

  return { data, isLoading, error };
};