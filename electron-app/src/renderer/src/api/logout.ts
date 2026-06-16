import { setAuthToken } from '../api/client';
import api from '../api/client';

export const logout = async () => {
  try {
    await api.post('/logout');
  } catch { }

  setAuthToken(null);
  localStorage.removeItem('session_token');

  console.log('[LOGOUT] before electron call');

  if (window.electron?.logout) {
    console.log('[LOGOUT] calling electron.logout()');

    await window.electron.logout();

    console.log('[LOGOUT] electron.logout() finished');
  } else {
    console.log('[LOGOUT] electron.logout NOT available');
  }

  delete api.defaults.headers.common['X-Session-Token'];

  window.location.href = '/login';
};