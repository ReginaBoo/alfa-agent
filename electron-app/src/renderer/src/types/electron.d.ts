export { };

declare global {
  interface Window {
    electron?: {
      openExternal: (url: string) => Promise<void>;
      getCookie: (url: string, name: string) => Promise<string | null>;
      getAllCookies: (url: string) => Promise<any[]>;
      startLogin: () => Promise<void>;
      onAuthSuccess: (callback: (token: string) => void) => void;
      removeAuthListener: () => void;
      getSessionToken: () => Promise<string | null>;
      logout: () => Promise<void>;
      onLogout: (callback: () => void) => void;
    };
  }
}
