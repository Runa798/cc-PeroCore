<template>
  <div
    class="absolute inset-0 flex overflow-hidden pixel-bg-moe font-sans pixel-ui pixel-grid-overlay"
  >
    <!-- 环境光与粒子 -->
    <div
      class="absolute inset-0 pointer-events-none transition-all duration-1000 z-0 opacity-40"
      :style="ambientLightStyle"
    ></div>
    <div class="absolute inset-0 pointer-events-none z-0 overflow-hidden">
      <div
        v-for="p in particles"
        :key="p.id"
        class="absolute animate-float-slow opacity-30"
        :style="p.style"
      >
        <PixelIcon :name="p.icon" :size="p.size" class="text-moe-pink/40" />
      </div>
    </div>

    <!-- 侧边栏 -->
    <aside
      class="w-64 flex flex-col h-full border-r-2 border-moe-cocoa/10 bg-white/40 backdrop-blur-md transition-all duration-300 z-20 relative"
    >
      <!-- 像素阴影线 -->
      <div
        class="absolute right-[-2px] top-0 bottom-0 w-[2px] bg-moe-cocoa/5 pointer-events-none"
      ></div>

      <!-- 搜索 -->
      <div class="px-4 pb-4 pt-2 flex-shrink-0">
        <div class="relative group">
          <input
            type="text"
            placeholder="搜索助手..."
            class="w-full bg-white/60 text-moe-cocoa text-xs pl-9 pr-3 py-2.5 focus:outline-none focus:bg-white transition-all pixel-border-moe border-moe-cocoa/20 focus:border-moe-pink/50 placeholder-moe-cocoa/40"
          />
          <PixelIcon
            name="search"
            size="xs"
            class="absolute left-3 top-2.5 text-moe-cocoa/40 group-hover:text-moe-pink transition-colors"
          />
        </div>
      </div>

      <!-- 助手列表 -->
      <div class="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-3 space-y-2 pb-2">
        <div class="flex items-center justify-between px-2 py-1.5 mb-1">
          <div
            class="text-[10px] font-bold text-moe-cocoa/50 uppercase tracking-widest flex items-center gap-1"
          >
            AGENTS <span class="w-1 h-1 bg-moe-pink animate-pulse"></span>
          </div>
          <PTooltip content="刷新列表" placement="top">
            <button
              class="p-1.5 bg-white pixel-border-moe hover:bg-moe-pink/10 text-moe-cocoa/40 hover:text-moe-pink transition-all press-effect"
              @click="loadAgents"
            >
              <PixelIcon name="refresh" size="xs" :animation="isLoading ? 'spin' : ''" />
            </button>
          </PTooltip>
        </div>

        <div v-if="errorMsg" class="px-3 py-2 text-xs text-moe-pink bg-white/80 pixel-border-moe">
          {{ errorMsg }}
        </div>

        <div
          v-if="agents.length === 0 && !isLoading && !errorMsg"
          class="px-2 py-8 text-center text-xs text-moe-cocoa/40 flex flex-col items-center gap-2"
        >
          <PixelIcon name="ghost" size="md" class="opacity-50" />
          <span>暂无助手 (No Agents)</span>
        </div>

        <div
          v-for="agent in agents"
          :key="agent.id"
          class="flex items-center gap-3 p-2 transition-all duration-200 group cursor-pointer relative hover:translate-x-1"
          :class="[
            activeAgentId === agent.id
              ? 'bg-white/80 pixel-border-moe'
              : 'hover:bg-white/50 border border-transparent hover:border-moe-pink/20'
          ]"
          @click="switchAgent(agent)"
        >
          <!-- 活跃指示器 -->
          <div
            v-if="activeAgentId === agent.id"
            class="absolute left-0 top-2 bottom-2 w-1 bg-moe-pink"
          ></div>

          <div class="relative">
            <div
              class="w-10 h-10 flex items-center justify-center text-white font-bold text-sm transition-transform duration-300 group-hover:scale-110 group-hover:rotate-6"
              :class="[
                activeAgentId === agent.id
                  ? 'bg-moe-pink pixel-border-moe shadow-sm'
                  : 'bg-moe-sky pixel-border-moe'
              ]"
            >
              {{ agent.name ? agent.name[0].toUpperCase() : '?' }}
            </div>
            <div v-if="activeAgentId === agent.id" class="absolute -bottom-1 -right-1">
              <PixelIcon name="sparkle" size="xs" class="text-moe-yellow drop-shadow-sm" />
            </div>
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between">
              <span
                class="text-sm font-bold truncate transition-colors"
                :class="activeAgentId === agent.id ? 'text-moe-pink' : 'text-moe-cocoa/80'"
                >{{ agent.name }}</span
              >
            </div>
            <div
              class="text-[10px] truncate font-mono"
              :class="activeAgentId === agent.id ? 'text-moe-pink/60' : 'text-moe-cocoa/40'"
            >
              {{ activeAgentId === agent.id ? 'ONLINE' : 'STANDBY' }}
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="p-3 border-t-2 border-moe-cocoa/5 bg-white/20 relative flex-shrink-0">
        <div class="absolute top-[-2px] left-3 right-3 h-[2px] bg-white/50"></div>
        <button
          class="w-full flex items-center justify-center gap-2 px-3 py-2 pixel-btn-moe-pink group"
          @click="openStronghold"
        >
          <PixelIcon name="users" size="sm" class="group-hover:scale-110 transition-transform" />
          <span class="text-xs font-black tracking-widest">进入据点</span>
        </button>
      </div>
    </aside>

    <!-- 主聊天区 -->
    <div class="flex-1 flex flex-col relative z-10 overflow-hidden">
      <!-- 头部 -->
      <header
        class="h-14 px-6 flex items-center justify-between border-b-2 border-moe-cocoa/5 bg-white/30 backdrop-blur-md"
      >
        <div class="flex items-center gap-3">
          <div class="p-1.5 bg-moe-pink/10 text-moe-pink">
            <PixelIcon name="chat" size="sm" />
          </div>
          <span class="text-lg font-black text-moe-cocoa tracking-wide">
            {{ activeAgentName }}
          </span>
          <span
            class="px-2 py-0.5 text-[10px] font-bold border bg-moe-pink/5 text-moe-pink border-moe-pink/20 pixel-border-moe"
          >
            CONNECTED
          </span>
        </div>
        <div class="flex items-center gap-3">
          <PTooltip content="通知">
            <button
              class="p-2 hover:bg-white/50 text-moe-cocoa/40 hover:text-moe-pink transition-colors"
            >
              <PixelIcon name="info" size="sm" />
            </button>
          </PTooltip>
          <PTooltip content="设置">
            <button
              class="p-2 hover:bg-white/50 text-moe-cocoa/40 hover:text-moe-pink transition-colors"
            >
              <PixelIcon name="settings" size="sm" />
            </button>
          </PTooltip>
        </div>
      </header>

      <!-- 聊天组件 -->
      <ChatInterface
        v-if="activeAgentId"
        :key="'direct-' + activeAgentId"
        :work-mode="false"
        class="flex-1"
        mode="direct"
        :target-id="activeAgentId"
        :agent-name="activeAgentName"
      />
      <div v-else class="flex-1 flex flex-col items-center justify-center text-moe-cocoa/30 gap-4">
        <div class="p-6 bg-white/30 pixel-border-moe animate-pulse">
          <PixelIcon name="chat" size="3xl" class="text-moe-pink/20" />
        </div>
        <div class="text-center">
          <p class="font-bold text-lg text-moe-cocoa/60">等待连接...</p>
          <p class="text-xs mt-1">请从左侧选择一个助手开始聊天</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { invoke } from '@/utils/ipcAdapter'
import ChatInterface from '../components/chat/ChatInterface.vue'
import PixelIcon from '../components/ui/PixelIcon.vue'
import PTooltip from '../components/ui/PTooltip.vue'

const API_BASE = window.electron ? 'http://localhost:9120' : ''

// 状态
const agents = ref([])
const isLoading = ref(false)
const errorMsg = ref('')
const activeAgentId = ref(null)
const activeAgentName = ref('Pero')
const particles = ref([])

// 环境光逻辑
const ambientLightStyle = computed(() => {
  const color = { primary: 'rgba(125, 211, 252, 0.2)', secondary: 'rgba(153, 246, 228, 0.15)' }
  return {
    background: `radial-gradient(circle at 20% 30%, ${color.primary} 0%, transparent 70%),
                radial-gradient(circle at 80% 70%, ${color.secondary} 0%, transparent 70%)`,
    filter: 'blur(100px)',
    opacity: 0.8
  }
})

// 粒子效果逻辑
const initParticles = () => {
  particles.value = Array.from({ length: 8 }, (_, i) => ({
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

// 数据加载
const loadAgents = async () => {
  isLoading.value = true
  errorMsg.value = ''
  try {
    const resAll = await fetch(`${API_BASE}/api/agents`)
    if (!resAll.ok) throw new Error(`HTTP ${resAll.status}`)

    const allAgents = await resAll.json()
    agents.value = allAgents.filter((a) => a.is_enabled)

    const active = allAgents.find((a) => a.is_active)
    if (active) {
      activeAgentId.value = active.id
      activeAgentName.value = active.name
    } else if (agents.value.length > 0) {
      activeAgentId.value = agents.value[0].id
      activeAgentName.value = agents.value[0].name
    }
  } catch (e) {
    console.error('Failed to load agents', e)
    errorMsg.value = `加载失败: ${e.message}`
  } finally {
    isLoading.value = false
  }
}

const switchAgent = async (agent) => {
  activeAgentId.value = agent.id
  activeAgentName.value = agent.name

  try {
    await fetch(`${API_BASE}/api/agents/active`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: agent.id })
    })
  } catch (e) {
    console.error('切换助手失败', e)
  }
}

const openStronghold = async () => {
  try {
    await invoke('open_stronghold_window')
  } catch (e) {
    console.error('Failed to open stronghold window', e)
  }
}

onMounted(() => {
  loadAgents()
  initParticles()
  console.log('聊天模式已挂载')
  window.ipcRenderer?.send('resize-window', { width: 400, height: 600 })
})

onUnmounted(() => {
  console.log('聊天模式已卸载')
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(14, 165, 233, 0.2);
  border-radius: 0;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(14, 165, 233, 0.4);
}

.glass-effect {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
}

.pixel-border-sky {
  box-shadow:
    inset 1px 1px 0px 0px #ffffff,
    inset -1px -1px 0px 0px #bae6fd,
    1px 1px 0px 0px #0ea5e9,
    -1px -1px 0px 0px #ffffff,
    1px -1px 0px 0px #0ea5e9,
    -1px 1px 0px 0px #0ea5e9;
}

.pixel-border-pink {
  box-shadow:
    inset 1px 1px 0px 0px #ffffff,
    inset -1px -1px 0px 0px #fbcfe8,
    1px 1px 0px 0px #f43f5e,
    -1px -1px 0px 0px #ffffff,
    1px -1px 0px 0px #f43f5e,
    -1px 1px 0px 0px #f43f5e;
}

.pixel-border-sm {
  box-shadow:
    1px 1px 0px 0px rgba(0, 0, 0, 0.1),
    -1px -1px 0px 0px rgba(255, 255, 255, 0.8);
}

.press-effect:active {
  transform: translateY(2px);
  box-shadow: none !important;
}

.hover-pixel-bounce:hover {
  transform: translateY(-2px);
}
</style>
