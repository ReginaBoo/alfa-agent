/// <reference types="vite/client" />
declare global {
  interface Window {
    electron: ElectronAPI
    api: unknown
  }
}


