import { app, shell, BrowserWindow, Tray, Menu, nativeImage, ipcMain, screen, session } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import iconPath from '../../resources/icon.png?asset'

let tray: Tray | null = null
let mainWindow: BrowserWindow | null = null
let authWindow: BrowserWindow | null = null

// URL для сайта (большие страницы)
const WEBSITE_URL = is.dev
  ? 'https://frontend-aa.website.yandexcloud.net/dashboard'
  : 'https://frontend-aa.website.yandexcloud.net';

// URL бекенда
const BACKEND_URL = 'https://89.169.165.170.nip.io';
console.log(`[MAIN] Backend URL: ${BACKEND_URL}`);
console.log(`[MAIN] Website URL: ${WEBSITE_URL}`);

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

  await ses.cookies.remove('http://localhost:8000', 'session_token').catch(() => {});
  await ses.cookies.remove('https://localhost:8000', 'session_token').catch(() => {});
  await ses.cookies.remove(BACKEND_URL, 'session_token').catch(() => {});

  await ses.cookies.set({
    url: BACKEND_URL,
    name: 'session_token',
    value: '',
    secure: BACKEND_URL.startsWith('https'),
    httpOnly: true,
    sameSite: 'lax'
  }).catch(err => console.error('Cookie setup error:', err));

  console.log(`Session configured for ${BACKEND_URL}`);
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

  authWindow.loadURL(`${BACKEND_URL}/auth/login`);

  authWindow.on('ready-to-show', () => {
    authWindow?.show();
  });

  authWindow.webContents.on('will-redirect', async (event, navigationUrl) => {
    console.log('[Auth] Redirecting to:', navigationUrl);

    if (navigationUrl.includes(WEBSITE_URL) || navigationUrl.includes('/dashboard')) {
      event.preventDefault();

      const cookies = await session.defaultSession.cookies.get({ url: BACKEND_URL });
      const sessionCookie = cookies.find(c => c.name === 'session_token');

      if (sessionCookie && sessionCookie.value) {
        console.log('[Auth] Session token obtained!');
        mainWindow?.webContents.send('auth-success', sessionCookie.value);
        authWindow?.close();
        authWindow = null;
        mainWindow?.reload();
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

  mainWindow.webContents.on('did-finish-load', async () => {
    console.log('[MAIN] Page loaded, checking authentication...');
    const cookies = await session.defaultSession.cookies.get({ url: BACKEND_URL });
    const sessionCookie = cookies.find(c => c.name === 'session_token');
    if (sessionCookie && sessionCookie.value) {
      console.log('[MAIN] ✅ User already authenticated');
      mainWindow?.webContents.send('auth-success', sessionCookie.value);
    } else {
      console.log('[MAIN] ❌ No token, user needs to login');
      mainWindow?.webContents.send('auth-logout');
    }
  });

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

  ipcMain.handle('start-login', async () => {
    console.log('[IPC] Starting login flow');
    createAuthWindow();
    return { success: true };
  });

  ipcMain.handle('get-session-token', async () => {
    try {
      const cookies = await session.defaultSession.cookies.get({ url: BACKEND_URL });
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
    mainWindow.loadURL(WEBSITE_URL)
  }
}

function createTray(): void {
  const trayIcon = nativeImage.createFromPath(iconPath)
  tray = new Tray(trayIcon)

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Перейти на сайт', click: () => shell.openExternal(WEBSITE_URL) },
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
