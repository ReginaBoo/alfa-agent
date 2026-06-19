import axios from 'axios';

// ВРЕМЕННО - для продакшена захардкодим URL
const BACKEND_URL = 'https://89.169.165.170.nip.io';
// const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
console.log(`[API] Backend URL: ${BACKEND_URL}`);

const api = axios.create({
  baseURL: BACKEND_URL + '/',
  withCredentials: true,
});

// Функция для установки токена
export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common['X-Session-Token'] = token;
    localStorage.setItem('session_token', token);
    console.log('✅ Auth token set in API headers');
  } else {
    delete api.defaults.headers.common['X-Session-Token'];
    localStorage.removeItem('session_token');
    console.log('❌ Auth token removed from API headers');
  }
};

// Инициализация при загрузке
const token = localStorage.getItem('session_token');
if (token) {
  setAuthToken(token);
}

// Перехватчик для логирования
api.interceptors.request.use(config => {
  console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  console.log(`   Backend: ${BACKEND_URL}`);
  console.log(`   X-Session-Token:`, config.headers['X-Session-Token'] || 'NOT SET');
  return config;
});

export default api;
