import axios from 'axios';

// ВРЕМЕННО - для продакшена
const BACKEND_URL = 'https://89.169.165.170.nip.io';
// const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

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
      return { isAuthenticated: false };
    }
  },

  getLoginUrl: (): string => {
    return `${BACKEND_URL}/api/auth/login`;
  },

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
