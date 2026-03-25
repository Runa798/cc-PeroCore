export const AGENT_NAME: string = 'Peropero'
export const AGENT_AVATAR_TEXT: string = 'P'
export const APP_TITLE: string = '萌动链接：PeroperoChat！'

// 后端连接配置 — 单一来源，所有组件统一引用
// Electron 模式: 直连 localhost:9120
// 浏览器模式: 走 Vite proxy (相对路径)
const isElectronEnv = typeof window !== 'undefined' && !!window.electron
export const API_HOST: string = isElectronEnv ? 'http://localhost:9120' : ''
export const API_BASE: string = `${API_HOST}/api`
export const WS_BASE: string = isElectronEnv
  ? 'ws://localhost:9120'
  : `${window?.location?.protocol === 'https:' ? 'wss:' : 'ws:'}//${window?.location?.host || 'localhost'}`
