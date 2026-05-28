import axios from 'axios';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export interface User {
  id: string;
  email: string;
  name?: string;
  avatarUrl?: string;
}

export interface AuthStatus {
  isAuthenticated: boolean;
  user?: User;
}

const authApi = {
  // Проверка текущей авторизации
  checkAuth: async (): Promise<AuthStatus> => {
    try {
      const response = await axios.get(`${BACKEND_URL}/api/auth/me`, {
        withCredentials: true,
      });

      return {
        isAuthenticated: true,
        user: response.data,
      };
    } catch (error: any) {
      if (error.response?.status === 401) {
        return { isAuthenticated: false };
      }
      // Сетевая ошибка — тоже считаем неавторизованным
      return { isAuthenticated: false };
    }
  },

  // Получить URL для OAuth логина
  getLoginUrl: (): string => {
    return `${BACKEND_URL}/api/auth/login`;
  },

  // Логаут (опционально)
  logout: async (): Promise<void> => {
    try {
      await axios.post(`${BACKEND_URL}/api/auth/logout`, {}, {
        withCredentials: true,
      });
    } catch (error) {
      console.error('Logout error:', error);
    }
  },
};

export default authApi;
