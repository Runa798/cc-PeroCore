import path from 'path'
import os from 'os'
import fs from 'fs'

export const isElectron = !!process.versions.electron

let appUserData: string
let appPath: string
let appExe: string

/**
 * 便携模式检测。
 * 如果 exe 同目录下存在 `.portable` 标记文件，则为便携模式：
 * - 数据存储在 exe 同目录的 `data/` 文件夹中
 * - 不依赖 %APPDATA% 或系统用户目录
 *
 * Setup 安装版/Steam 版不会有此文件，仍走默认的 userData 路径。
 */
function detectPortableMode(exePath: string): boolean {
  try {
    const exeDir = path.dirname(exePath)
    const markerPath = path.join(exeDir, '.portable')
    return fs.existsSync(markerPath)
  } catch {
    return false
  }
}

if (isElectron) {
  // 动态 require 以避免在纯 Node.js 中运行时出现问题
  // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
  const { app } = require('electron')
  appPath = app.getAppPath()
  appExe = app.getPath('exe')

  if (detectPortableMode(appExe)) {
    // 便携模式：数据根目录 = exe 同级目录
    appUserData = path.dirname(appExe)
    console.log(`[Env] 检测到便携模式，数据目录: ${appUserData}`)
  } else if (!app.isPackaged) {
    // 开发模式：数据统一存放在项目的 backend/ 目录下
    // 这样 paths.data = {project}/backend/data/ 与 Python 后端数据位于同一目录
    const projectRoot = path.resolve(__dirname, '../../..')   // dist-electron/main -> electron -> 项目根
    appUserData = path.join(projectRoot, 'backend')
    console.log(`[Env] 开发模式，数据目录: ${appUserData}/data/`)
  } else {
    // 标准发行模式（Setup 安装/Steam）：使用 %APPDATA%/萌动链接：PeroperoChat！/
    appUserData = app.getPath('userData')
  }
} else {
  // CLI / Docker 环境
  const HOME = os.homedir()
  // 默认为 ~/.perocore 或遵循环境变量
  appUserData = process.env.PERO_USER_DATA || path.join(HOME, '.perocore')
  appPath = process.cwd()
  appExe = process.execPath

  // 确保目录在 CLI 模式下存在
  try {
    if (!fs.existsSync(appUserData)) {
      fs.mkdirSync(appUserData, { recursive: true })
    }
  } catch (e) {
    console.warn('[Env] 创建用户数据目录失败:', e)
  }
}

export const isPackaged = isElectron ? getApp().isPackaged : process.env.NODE_ENV === 'production'
export const isDev = !isPackaged
export const isPortable = isElectron && isPackaged && detectPortableMode(appExe)

// 远程后端 URL (用于 WSL/Docker 开发模式)
// 设置 PERO_BACKEND_URL=http://172.21.254.166:9120 跳过本地后端启动
export const remoteBackendUrl = process.env.PERO_BACKEND_URL || ''
export const isRemoteBackend = !!remoteBackendUrl

/**
 * 系统默认的用户数据目录（%APPDATA%/...）。
 * 无论当前模式如何，始终指向 Windows 系统用户目录。
 * 用于 Logger 的双写：开发模式下日志同时存在项目目录 + 系统目录。
 */
export const systemUserData: string = isElectron
  ? (() => { try { return require('electron').app.getPath('userData') } catch { return appUserData } })()
  : appUserData

export const paths = {
  userData: appUserData,
  app: appPath,
  exe: appExe,
  resources: isElectron ? process.resourcesPath : appPath, // CLI 的后备方案
  data: path.join(appUserData, 'data'),
  logs: path.join(appUserData, 'data', 'logs')
}

/**
 * Electron app 对象的安全包装器。
 * 如果未在 Electron 中运行，则返回 null。
 */
export function getApp() {
  if (isElectron) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
    return require('electron').app
  }
  return null
}

import { ipcRegistry } from './ipcRegistry'

/**
 * Electron ipcMain 的安全包装器。
 * 如果未在 Electron 中运行，则返回模拟对象或 null。
 */
export function getIpcMain() {
  if (isElectron) {
    // eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
    return require('electron').ipcMain
  }
  // 连接到 CLI 模式的 IpcRegistry
  return {
    handle: (channel: string, listener: any) => {
      ipcRegistry.registerHandler(channel, listener)
    },
    on: (channel: string, listener: any) => {
      ipcRegistry.registerListener(channel, listener)
    },
    emit: (channel: string, ...args: any[]) => {
      ipcRegistry.emit(channel, ...args)
    },
    // 移除监听器存根
    removeListener: () => {},
    removeHandler: () => {}
  }
}
