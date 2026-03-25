/**
 * useDashboard.ts
 * Dashboard 共享基础状态：API基地址、fetch工具、confirm弹窗、全局刷新
 */
import { ref } from 'vue'
import { invoke } from '@/utils/ipcAdapter'
import type {
  ConfirmOptions,
  ConfirmResult,
  OpenConfirmFn,
  ParticleItem,
  MenuGroup,
  ConnectionInfo,
  UpdateStatus
} from './types'

// ─── API 基础地址 ──────────────────────────────────────────────────────────────
export { API_BASE } from '@/config'

// ─── 带超时的 fetch 包装 ─────────────────────────────────────────────────────
export const fetchWithTimeout = async (
  url: string,
  options: RequestInit & { silent?: boolean } = {},
  timeout = 5000
): Promise<Response> => {
  const controller = new AbortController()
  const id = setTimeout(() => controller.abort(), timeout)
  const { silent, ...fetchOptions } = options
  try {
    const response = await fetch(url, { ...fetchOptions, signal: controller.signal })
    clearTimeout(id)
    return response
  } catch (error: unknown) {
    clearTimeout(id)
    const err = error as Error
    let errorMsg = err.message
    if (err.name === 'AbortError') {
      errorMsg = `请求超时 (${timeout}ms)`
    } else if (err.message === 'Failed to fetch') {
      errorMsg = '无法连接到后端服务。请检查后端是否已启动'
    } else if (err.message.includes('NetworkError')) {
      errorMsg = '网络连接错误'
    }
    if (!silent) {
      window.$notify(errorMsg, 'error')
      if (err.name !== 'AbortError') {
        console.warn(`[Fetch] 请求失败 ${url}:`, err.message)
      }
    }
    throw error
  }
}

// ─── LLM 错误信息格式化 ────────────────────────────────────────────────────────
export const formatLLMError = (error: unknown): string => {
  const err = error as Error
  if (err.name === 'AbortError') return '请求超时 (Timeout)'
  const msg = err.message || String(error)
  if (msg.includes('401') || msg.includes('invalid_api_key') || msg.includes('Incorrect API key'))
    return 'API Key 无效，请检查配置 (401 Unauthorized)'
  if (msg.includes('404') || msg.includes('model_not_found'))
    return '请求的模型不存在或端点错误 (404 Not Found)'
  if (msg.includes('429') || msg.includes('rate_limit') || msg.includes('insufficient_quota'))
    return '请求过于频繁或余额不足 (429 Rate Limit)'
  if (msg.includes('500') || msg.includes('internal_server_error'))
    return '服务商服务器内部错误 (500 Internal Server Error)'
  if (msg.includes('503') || msg.includes('service_unavailable'))
    return '服务暂时不可用 (503 Service Unavailable)'
  if (msg.includes('Failed to fetch')) return '无法连接到服务器，请检查网络 (Failed to fetch)'
  return msg
}

// ─── useDashboard 组合式函数 ──────────────────────────────────────────────────
export function useDashboard() {
  // --- 全局 UI 状态 ---
  const currentTab = ref<string>('overview')
  const isBackendOnline = ref<boolean>(false)
  const isSaving = ref<boolean>(false)
  const isGlobalRefreshing = ref<boolean>(false)

  // --- 粒子背景 ---
  const particles = ref<ParticleItem[]>([])
  const initParticles = (): void => {
    particles.value = Array.from({ length: 12 }, (_, i) => ({
      id: i,
      style: {
        top: `${Math.random() * 100}%`,
        left: `${Math.random() * 100}%`,
        animationDelay: `${Math.random() * 5}s`,
        animationDuration: `${10 + Math.random() * 15}s`,
        willChange: 'transform, opacity'
      },
      icon: i % 2 === 0 ? 'sparkle' : 'heart',
      size: i % 3 === 0 ? 'sm' : 'xs'
    }))
  }

  // --- Confirm 弹窗 ---
  const showConfirmModal = ref<boolean>(false)
  const confirmModalTitle = ref<string>('')
  const confirmModalContent = ref<string>('')
  const confirmCallback = ref<(() => void) | null>(null)
  const confirmCancelCallback = ref<(() => void) | null>(null)
  const confirmType = ref<'warning' | 'info' | 'error' | 'success'>('warning')
  const isPrompt = ref<boolean>(false)
  const promptValue = ref<string>('')
  const promptPlaceholder = ref<string>('')

  const openConfirm: OpenConfirmFn = (
    title: string,
    content: string,
    options: ConfirmOptions = {}
  ): Promise<ConfirmResult> => {
    return new Promise((resolve, reject) => {
      confirmModalTitle.value = title
      confirmModalContent.value = content
      confirmType.value = (options.type as typeof confirmType.value) ?? 'warning'
      isPrompt.value = !!options.isPrompt
      promptValue.value = options.inputValue ?? ''
      promptPlaceholder.value = options.inputPlaceholder ?? ''

      confirmCallback.value = () => {
        resolve(
          isPrompt.value ? { value: promptValue.value, action: 'confirm' } : { action: 'confirm' }
        )
        showConfirmModal.value = false
      }
      confirmCancelCallback.value = () => {
        reject(new Error('User cancelled'))
        showConfirmModal.value = false
      }
      showConfirmModal.value = true
    })
  }

  const handleConfirm = (): void => {
    confirmCallback.value?.()
  }
  const handleCancel = (): void => {
    confirmCancelCallback.value?.()
  }

  // --- 图片查看器 ---
  const showImageViewer = ref<boolean>(false)
  const imageViewerList = ref<string[]>([])
  const imageViewerIndex = ref<number>(0)

  const openImageViewer = (imgs: string[], idx: number): void => {
    imageViewerList.value = imgs
    imageViewerIndex.value = idx
    showImageViewer.value = true
  }

  // --- App 版本 / 更新 ---
  const appVersion = ref<string>('0.8.0')
  const updateStatus = ref<UpdateStatus>({ type: 'idle' })
  const isCheckingUpdate = ref<boolean>(false)

  const checkForUpdates = async (): Promise<void> => {
    if (isCheckingUpdate.value) return
    isCheckingUpdate.value = true
    try {
      await invoke('check_update')
    } catch {
      window.$notify('检查更新失败', 'error')
      isCheckingUpdate.value = false
    }
  }

  const handleUpdateMessage = (data: UpdateStatus, openConfirmFn: OpenConfirmFn): void => {
    updateStatus.value = data
    switch (data.type) {
      case 'checking':
        isCheckingUpdate.value = true
        break
      case 'not-available':
        isCheckingUpdate.value = false
        window.$notify('当前已是最新版本', 'success')
        break
      case 'error':
        isCheckingUpdate.value = false
        window.$notify(`更新错误: ${data.error}`, 'error')
        break
      case 'available':
        isCheckingUpdate.value = false
        openConfirmFn('发现新版本', `检测到新版本 v${data.info?.version}，是否立即更新？`, {
          type: 'info'
        })
          .then(() => invoke('download_update'))
          .catch(() => {})
        break
      case 'downloaded':
        openConfirmFn('更新就绪', '更新已下载完毕，是否立即重启以安装？', { type: 'success' })
          .then(() => invoke('quit_and_install'))
          .catch(() => {})
        break
    }
  }

  // --- 连接二维码 ---
  const showQrModal = ref<boolean>(false)
  const connectionInfo = ref<ConnectionInfo | null>(null)
  const isLoadingConnection = ref<boolean>(false)

  const fetchConnectionInfo = async (): Promise<void> => {
    isLoadingConnection.value = true
    try {
      const res = await fetch(`${API_BASE}/connection/info`)
      if (res.ok) {
        connectionInfo.value = (await res.json()) as ConnectionInfo
        showQrModal.value = true
      } else {
        window.$notify('获取连接信息失败', 'error')
      }
    } catch {
      window.$notify('无法连接到后端服务', 'error')
    } finally {
      isLoadingConnection.value = false
    }
  }

  // --- 退出 ---
  const handleQuitApp = async (): Promise<void> => {
    try {
      await openConfirm(
        '退出 萌动链接：PeroperoChat！',
        '确定要关闭 Peropero 并退出所有相关程序吗？',
        {
          type: 'warning'
        }
      )
      await invoke('quit_app')
    } catch (e) {
      if ((e as Error).message !== 'User cancelled') console.error('Failed to quit app', e)
    }
  }

  // --- 标签选择 ---
  const handleTabSelect = (index: string): void => {
    if (currentTab.value === index) return
    currentTab.value = index
  }

  // --- 菜单结构 ---
  const menuGroups: MenuGroup[] = [
    {
      title: null,
      items: [
        { id: 'overview', label: '总览', icon: 'desktop' },
        { id: 'logs', label: '对话日志', icon: 'chat' },
        { id: 'memories', label: '核心记忆', icon: 'brain' },
        { id: 'tasks', label: '待办任务', icon: 'list' }
      ]
    },
    {
      title: 'CONFIGURATION',
      items: [
        { id: 'user_settings', label: '用户设定', icon: 'user' },
        { id: 'model_config', label: '模型配置', icon: 'settings' },
        { id: 'voice_config', label: '语音功能', icon: 'mic' },
        { id: 'mcp_config', label: 'MCP 配置', icon: 'terminal' }
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { id: 'napcat', label: 'NapCat 终端', icon: 'terminal' },
        { id: 'terminal', label: '系统终端', icon: 'desktop' },
        { id: 'system_reset', label: '危险区域', icon: 'alert', variant: 'danger' }
      ]
    }
  ]

  return {
    // 状态
    currentTab,
    isBackendOnline,
    isSaving,
    isGlobalRefreshing,
    particles,
    initParticles,
    // 确认弹窗
    showConfirmModal,
    confirmModalTitle,
    confirmModalContent,
    confirmCallback,
    confirmCancelCallback,
    confirmType,
    isPrompt,
    promptValue,
    promptPlaceholder,
    openConfirm,
    handleConfirm,
    handleCancel,
    // 图片查看器
    showImageViewer,
    imageViewerList,
    imageViewerIndex,
    openImageViewer,
    // 更新
    appVersion,
    updateStatus,
    isCheckingUpdate,
    checkForUpdates,
    handleUpdateMessage,
    // 连接
    showQrModal,
    connectionInfo,
    isLoadingConnection,
    fetchConnectionInfo,
    // 退出
    handleQuitApp,
    // 导航
    handleTabSelect,
    menuGroups
  }
}
