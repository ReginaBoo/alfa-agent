import { contextBridge, shell, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', {
      ...electronAPI,
      openExternal: (url: string) => shell.openExternal(url),
      // Получить токен из cookie
      getSessionToken: async () => {
        return await ipcRenderer.invoke('get-session-token');
      },
      // Запустить авторизацию
      startLogin: async () => {
        return await ipcRenderer.invoke('start-login');
      },
      // Слушать успешную авторизацию
      onAuthSuccess: (callback: (token: string) => void) => {
        ipcRenderer.on('auth-success', (_event, token) => callback(token));
      },
      logout: async () => {
        return await ipcRenderer.invoke('logout');
      },
      onLogout: (callback: () => void) => {
        ipcRenderer.on('auth-logout', callback);
      },
    })
  } catch (error) {
    console.error(error)
  }
}

