import axios from 'axios';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
console.log(`[Electron API] Backend URL: ${BACKEND_URL}`);

const electronApi = axios.create({
  baseURL: BACKEND_URL,
  withCredentials: true,
});

// Добавляем токен в заголовки, если он есть в localStorage
electronApi.interceptors.request.use(config => {
  const token = localStorage.getItem('session_token');
  if (token) {
    config.headers['X-Session-Token'] = token;
    console.log(`[Electron API] Adding token to headers`);
  }
  return config;
});

electronApi.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      console.log('[Electron API] Unauthorized, clearing token');
      localStorage.removeItem('session_token');
    }
    return Promise.reject(error);
  }
);

export default electronApi;
