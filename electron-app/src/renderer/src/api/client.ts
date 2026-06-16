import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/',
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
  console.log(`   X-Session-Token:`, config.headers['X-Session-Token'] || 'NOT SET');
  return config;
});

export default api;
