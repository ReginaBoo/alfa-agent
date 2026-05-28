import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  withCredentials: true,
});

// Добавляем токен из localStorage в каждый запрос
const token = localStorage.getItem('session_token');
if (token) {
  api.defaults.headers.common['X-Session-Token'] = token;
}

// Перехватчик для логирования
api.interceptors.request.use(config => {
  console.log(`📤 [API] ${config.method?.toUpperCase()} ${config.url}`);
  console.log(`   Headers:`, config.headers);
  return config;
});

export default api;
