<template>
  <div class="relative w-screen h-screen overflow-hidden bg-transparent">
    <!-- 自定义标题栏 (始终可见，处理拖拽和窗口控制) -->
    <CustomTitleBar
      v-if="isElectron()"
      :is-work-mode="isWorkMode"
      :show-mode-toggle="!isWorkMode"
      :title="APP_TITLE"
      @toggle-mode="toggleMode"
    />

    <!-- 视图容器 (满屏或排除标题栏) -->
    <div
      :class="[
        'absolute left-0 right-0 bottom-0 overflow-hidden pixel-ui pixel-grid-overlay transition-colors duration-500',
        isWorkMode ? 'bg-[#1e293b]' : 'bg-[#fffcf9]'
      ]"
      :style="{
        top: isElectron() ? '32px' : '0',
        height: isElectron() ? 'calc(100% - 32px)' : '100%'
      }"
    >
      <Transition name="fade-slide">
        <KeepAlive>
          <component
            :is="currentView"
            :key="isWorkMode ? 'work' : 'chat'"
            class="w-full h-full absolute inset-0"
            :is-ready="isSessionReady"
            @exit="handleWorkExit"
            @start-work="isWorkMode = true"
          />
        </KeepAlive>
      </Transition>
    </div>

    <!-- 阻断性警告对话框 -->
    <CustomDialog
      v-model:visible="showErrorDialog"
      type="alert"
      title="模式冲突"
      :message="errorMessage"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { emit, isElectron } from '@/utils/ipcAdapter'
import { APP_TITLE } from '../config'
import CustomTitleBar from '../components/layout/CustomTitleBar.vue'
import CustomDialog from '../components/ui/CustomDialog.vue'
import ChatModeView from './ChatModeView.vue'
import WorkModeView from './WorkModeView.vue'

const isWorkMode = ref(false)
const showErrorDialog = ref(false)
const isSessionReady = ref(false)
const errorMessage = ref('')

import { API_HOST as API_BASE } from '@/config'

// 在 Electron 中，窗口管理通过 IPC 由主进程处理
// 主进程 (windows/manager.ts) 应该处理 'close' 事件以隐藏窗口
onMounted(async () => {
  // 可选：通知主进程前端已准备就绪
  // await invoke('main_window_ready')
})

const currentView = computed(() => (isWorkMode.value ? WorkModeView : ChatModeView))

const toggleMode = async () => {
  // 检查我们是否试图进入工作模式
  if (!isWorkMode.value) {
    try {
      const configRes = await fetch(`${API_BASE}/api/config/lightweight_mode`)
      if (configRes.ok) {
        const config = await configRes.json()
        if (config.enabled) {
          console.warn('[工作模式] 被前端预检查阻止：轻量模式已启用')
          errorMessage.value = '无法进入工作模式。检测到以下模式正在运行：轻量模式。请先关闭它们。'
          showErrorDialog.value = true
          return
        }
      }
    } catch (e) {
      console.warn('[工作模式] 预检查失败，交由后端处理:', e)
    }
  }
  isWorkMode.value = !isWorkMode.value
}

// 监听模式变化并广播到系统 (例如用于 PetView 隔离)
watch(isWorkMode, async (newVal) => {
  await emit('work-mode-changed', { is_work_mode: newVal })

  if (newVal) {
    // 进入工作模式
    isSessionReady.value = false
    try {
      const res = await fetch(`${API_BASE}/api/ide/work_mode/enter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_name: 'Coding Session' })
      })
      if (!res.ok) throw new Error('进入工作会话失败')
      const data = await res.json()

      if (data.message && data.message.startsWith('Error')) {
        // 被后端检查阻止
        console.warn('[工作模式] 被阻止:', data.message)
        errorMessage.value = data.message.replace('Error: ', '')
        showErrorDialog.value = true
        isWorkMode.value = false // 恢复状态
        return
      }

      console.log('[工作模式] 已进入:', data.message)
      // 添加少量延迟以保证 UI 过渡平滑
      setTimeout(() => {
        isSessionReady.value = true
      }, 500)
    } catch (e) {
      console.error('[IDE] 进入工作模式失败:', e)
      if (window.$notify) {
        window.$notify('进入工作模式失败，部分功能可能受限喵~', 'warning', '工作模式异常')
      }
      // 即使失败也标记就绪，以便显示 UI
      isSessionReady.value = true
    }
  } else {
    // 退出工作模式 - 会话清理已由 handleWorkExit 或 Abort 处理
    isSessionReady.value = false
  }
})

const handleWorkExit = async (save) => {
  try {
    if (save) {
      console.log('工作会话正在完成...')
      await fetch(`${API_BASE}/api/ide/work_mode/exit`, { method: 'POST' })
    } else {
      console.log('工作会话正在中止...')
      await fetch(`${API_BASE}/api/ide/work_mode/abort`, { method: 'POST' })
    }
  } catch (e) {
    console.error('同步工作会话退出失败:', e)
  }
  isWorkMode.value = false
}
</script>

<style>
/* 同时过渡 (重叠) */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(20px) scale(0.98);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-20px) scale(0.98);
}
</style>
