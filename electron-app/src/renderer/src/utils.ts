export const isElectron = !!(
  (window as any).electron ||
  navigator.userAgent.toLowerCase().includes(' electron/')
);