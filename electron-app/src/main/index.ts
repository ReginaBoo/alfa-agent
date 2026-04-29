import { app, shell, BrowserWindow, Tray, Menu, nativeImage, ipcMain, screen } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import iconPath from '../../resources/icon.png?asset'

let tray: Tray | null = null
let mainWindow: BrowserWindow | null = null
let URL = 'http://localhost:5173/'

declare global {
  namespace Electron {
    interface App {
      isQuitting?: boolean
    }
  }
}

function createWindow(): void {
  const primaryDisplay = screen.getPrimaryDisplay()
  const { width, height } = primaryDisplay.workAreaSize
  const windowWidth = 300
  const windowHeight = 500

  const x = width - windowWidth - 5
  const y = height - windowHeight - 5

  mainWindow = new BrowserWindow({
    width: windowWidth,
    height: windowHeight,
    x: x,
    y: y,
    show: false,
    autoHideMenuBar: true,
    alwaysOnTop: true,
    frame: false,
    transparent: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

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

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.electron')

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