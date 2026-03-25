export const AGENT_NAME: string = 'Peropero'
export const AGENT_AVATAR_TEXT: string = 'P'
export const APP_TITLE: string = '萌动链接：PeroperoChat！'

// 后端连接配置 — 单一来源，所有组件统一引用
// Electron + 远程后端: 使用 PERO_BACKEND_URL (如 http://172.21.254.166:9120)
// Electron + 本地后端: 直连 localhost:9120
// 浏览器模式: 走 Vite proxy (相对路径)
const isElectronEnv = typeof window !== 'undefined' && !!window.electron
const remoteUrl = isElectronEnv ? (window.electron?.backendUrl || '') : ''
export const API_HOST: string = isElectronEnv ? (remoteUrl || 'http://localhost:9120') : ''
export const API_BASE: string = `${API_HOST}/api`
export const WS_BASE: string = isElectronEnv
  ? (remoteUrl ? remoteUrl.replace('http', 'ws') : 'ws://localhost:9120')
  : `${window?.location?.protocol === 'https:' ? 'wss:' : 'ws:'}//${window?.location?.host || 'localhost'}`
