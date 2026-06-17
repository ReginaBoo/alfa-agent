import { app, shell, BrowserWindow, Tray, Menu, nativeImage, ipcMain, screen, session } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import iconPath from '../../resources/icon.png?asset'

let tray: Tray | null = null
let mainWindow: BrowserWindow | null = null
let authWindow: BrowserWindow | null = null
let URL = 'http://localhost:5173/dashboard'

declare global {
  namespace Electron {
    interface App {
      isQuitting?: boolean
    }
  }
}

// Настройка сессии для сохранения cookie
async function setupSession(): Promise<void> {
  const ses = session.defaultSession;

  await ses.cookies.set({
    url: 'http://localhost:8000',
    name: 'session_token',
    value: '',
    secure: false,
    httpOnly: true,
    sameSite: 'lax'
  }).catch(err => console.error('Cookie setup error:', err));

  await ses.cookies.set({
    url: 'https://localhost:8000',
    name: 'session_token',
    value: '',
    secure: true,
    httpOnly: true,
    sameSite: 'lax'
  }).catch(err => console.error('Cookie setup error:', err));

  console.log('Session configured for cookie persistence');
}

// Функция для создания окна авторизации
function createAuthWindow(): void {
  if (authWindow) {
    authWindow.focus();
    return;
  }

  authWindow = new BrowserWindow({
    width: 900,
    height: 700,
    icon: iconPath,
    parent: mainWindow || undefined,
    modal: true,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  });

  // Загружаем страницу логина
  authWindow.loadURL('http://localhost:8000/auth/login');

  authWindow.on('ready-to-show', () => {
    authWindow?.show();
  });

  // Перехватываем редирект с code
  authWindow.webContents.on('will-redirect', async (event, navigationUrl) => {
    console.log('[Auth] Redirecting to:', navigationUrl);

    // Проверяем, что редирект на страницу dashboard (после успешного логина)
    if (navigationUrl.includes('http://localhost:5173/dashboard')) {
      event.preventDefault();

      // Получаем session_token из cookies
      const cookies = await session.defaultSession.cookies.get({ url: 'http://localhost:8000' });
      const sessionCookie = cookies.find(c => c.name === 'session_token');

      if (sessionCookie && sessionCookie.value) {
        console.log('[Auth] Session token obtained:', sessionCookie.value.substring(0, 20) + '...');

        // Отправляем токен в renderer процесс
        mainWindow?.webContents.send('auth-success', sessionCookie.value);

        // Закрываем окно авторизации
        authWindow?.close();
        authWindow = null;
      }
    }
  });

  authWindow.on('closed', () => {
    authWindow = null;
  });
}

function createWindow(): void {
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width, height } = primaryDisplay.workAreaSize
  const windowWidth = 320
  const windowHeight = 520

  const x = width - windowWidth - 5
  const y = height - windowHeight - 5

  mainWindow = new BrowserWindow({
    width: windowWidth,
    height: windowHeight,
    x: x,
    y: y,
    show: false,
    icon: iconPath,
    autoHideMenuBar: true,
    alwaysOnTop: true,
    frame: false,
    transparent: true,
    hasShadow: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      webSecurity: false,
      allowRunningInsecureContent: is.dev,
      partition: 'persist:main'
    }
  })

  mainWindow.webContents.session.cookies.get({})
    .then(cookies => {
      console.log('Existing cookies:', cookies);
    })
    .catch(err => console.error('Error getting cookies:', err));

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault()
      mainWindow?.hide()
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  ipcMain.on('window-minimize', () => {
    mainWindow?.minimize()
  })

  ipcMain.on('window-close', () => {
    mainWindow?.hide()
  })

  ipcMain.handle('get-cookie', async (_event, url: string, name) => {
    try {
      const cookies = await session.defaultSession.cookies.get({ url });
      const cookie = cookies.find(c => c.name === name);
      console.log(`[IPC] get-cookie ${name}:`, cookie?.value);
      return cookie ? cookie.value : null;
    } catch (error) {
      console.error('[IPC] Error getting cookie:', error);
      return null;
    }
  });

  ipcMain.handle('get-all-cookies', async (_event, url: string) => {
    try {
      const cookies = await session.defaultSession.cookies.get({ url });
      console.log('[IPC] get-all-cookies:', cookies);
      return cookies;
    } catch (error) {
      console.error('[IPC] Error getting all cookies:', error);
      return [];
    }
  });


  // Обработчик для запуска авторизации из renderer
  ipcMain.handle('start-login', async () => {
    console.log('[IPC] Starting login flow');
    createAuthWindow();
    return { success: true };
  });

  ipcMain.handle('get-session-token', async () => {
    try {
      const cookies = await session.defaultSession.cookies.get({ url: 'http://localhost:8000' });
      const sessionCookie = cookies.find(c => c.name === 'session_token');
      console.log('[IPC] get-session-token:', sessionCookie?.value);
      return sessionCookie?.value || null;
    } catch (error) {
      console.error('[IPC] Error getting session token:', error);
      return null;
    }
  });

  ipcMain.handle('logout', async () => {
    console.log('[MAIN] logout IPC received ');

    await session.defaultSession.clearStorageData({
      storages: ['cookies']
    });

    mainWindow?.webContents.send('auth-logout');

    console.log('[MAIN] auth-logout sent to renderer');
  });

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function createTray(): void {
  const trayIcon = nativeImage.createFromPath(iconPath)
  tray = new Tray(trayIcon)

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Перейти на сайт', click: () => shell.openExternal(URL) },
    {
      label: 'Чат', click: () => {
        mainWindow?.webContents.send('open-tab', 'chat');
        mainWindow?.show();
      }
    },
    { type: 'separator' },
    {
      label: 'Выйти',
      click: () => {
        (app as any).isQuitting = true
        app.quit()
      }
    }
  ])

  tray.setToolTip('Alfa Agent')
  tray.setContextMenu(contextMenu)

  tray.on('click', () => {
    if (mainWindow?.isVisible()) {
      mainWindow.hide()
    } else {
      mainWindow?.show()
    }
  })
}

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.electron')

  await setupSession();

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  ipcMain.on('ping', () => console.log('pong'))

  createWindow()
  createTray()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})



app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
