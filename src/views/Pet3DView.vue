<template>
  <div class="pet-3d-container">
    <!-- 3D 角色组件 -->
    <BedrockAvatar
      ref="avatarRef"
      :is-dragging="isDragging"
      :manifest-path="currentManifestPath || undefined"
      @pet="onPet"
      @hover-start="onHoverStart"
      @hover-end="onHoverEnd"
    />

    <!-- UI 覆盖层 -->
    <div class="ui-overlay" @mouseenter="onUIEnter" @mouseleave="onUILeave">
      <!-- 通知管理器 -->
      <PetNotificationManager ref="notificationManager" />

      <!-- 状态标签 (左上角) -->
      <transition name="fade">
        <div
          v-show="showInput"
          class="status-tags"
          :style="{ transform: `scale(${uiScale})`, transformOrigin: 'top left' }"
        >
          <div class="status-tag mood" :title="'情绪: ' + moodText">❤️ {{ moodText }}</div>
          <div class="status-tag vibe" :title="'氛围: ' + vibeText">✨ {{ vibeText }}</div>
          <div class="status-tag mind" :title="'内心: ' + mindText">💭 {{ mindText }}</div>
        </div>
      </transition>

      <div class="ui-scalable-wrapper" :style="{ transform: `scale(${uiScale})` }">
        <!-- 悬浮触发器 (光球) -->
        <div
          class="floating-trigger"
          :class="{ active: showInput }"
          style="-webkit-app-region: no-drag"
          @click.stop="toggleUI"
          @mouseenter="onUIEnter"
          @mouseleave="onUILeave"
        >
          <div class="trigger-core">
            <div class="pulse-ring"></div>
            <div class="core-dot"></div>
          </div>
        </div>

        <!-- 输入覆盖层 -->
        <div v-show="showInput" class="input-overlay" @mouseenter="onUIEnter">
          <input
            ref="inputRef"
            v-model="userInput"
            :placeholder="isWorkMode ? '工作模式下已禁用输入' : `跟 ${currentAgentName} 对话...`"
            class="chat-input"
            :disabled="isThinking || isWorkMode"
            style="-webkit-app-region: no-drag"
            @keyup.enter="sendMessage"
          />
        </div>

        <!-- 头像工具 -->
        <!-- 角色工具 -->
        <div
          v-show="showInput"
          class="pet-tools"
          style="-webkit-app-region: no-drag"
          @mouseenter="onUIEnter"
        >
          <button
            class="tool-btn"
            title="外观设置"
            :class="{ active: showAppearanceMenu }"
            @click.stop="toggleAppearanceMenu"
          >
            🎨
          </button>
          <button class="tool-btn" title="重载" @click.stop="reloadPet">🔄</button>
          <button class="tool-btn" title="调整大小" @click.stop="toggleWindowSize">📏</button>
          <button
            class="tool-btn voice-btn"
            :class="{
              active: voiceMode !== 0,
              'mode-vad': voiceMode === 1,
              'mode-ptt': voiceMode === 2
            }"
            :title="voiceModeTitle"
            @click.stop="cycleVoiceMode"
          >
            {{ voiceModeIcon }}
          </button>
          <button
            class="tool-btn"
            :title="displayMode === 'bubble' ? '切换到歌词模式' : '切换到气泡模式'"
            @click.stop="toggleDisplayMode"
          >
            {{ displayMode === 'bubble' ? '🎤' : '🫧' }}
          </button>
          <button class="tool-btn" title="聊天" @click.stop="openChatWindow">💬</button>
          <button class="tool-btn" title="面板" @click.stop="openDashboard">⚙️</button>
          <button class="tool-btn" title="最小化到托盘" @click.stop="minimizeToTray">➖</button>
        </div>

        <!-- PTT 悬浮按钮 (体素风格) -->
        <transition name="fade">
          <div
            v-if="voiceMode === 2"
            class="ptt-voxel-container"
            style="-webkit-app-region: no-drag"
            @mousedown.stop="startPTT"
            @mouseup.stop="stopPTT"
            @mouseleave.stop="stopPTT"
          >
            <div
              class="ptt-voxel-btn"
              :class="{ recording: isPTTRecording }"
              title="按住 Alt+Shift+V 说话"
            >
              <span class="ptt-icon">🎙️</span>
              <span v-if="isPTTRecording" class="ptt-text">正在聆听...</span>
            </div>
          </div>
        </transition>

        <!-- 外观菜单 (体素风格) -->
        <transition name="fade">
          <div
            v-if="showAppearanceMenu && showInput"
            class="appearance-menu"
            @mouseenter="onUIEnter"
          >
            <div class="menu-header">
              <span>外观控制</span>
              <button class="close-mini-btn" @click="showAppearanceMenu = false">×</button>
            </div>

            <div class="menu-section">
              <div class="menu-label">角色选择</div>
              <div class="character-grid">
                <button
                  v-for="model in availableModels"
                  :key="model.asset_id"
                  class="char-btn"
                  :class="{ active: isModelActive(model) }"
                  :title="
                    model.source === 'workshop' ? `Workshop: ${model.workshop_id}` : model.source
                  "
                  @click="selectModel(model)"
                >
                  {{ model.display_name }}
                  <span v-if="model.source === 'workshop'" class="workshop-badge">W</span>
                  <span v-else-if="model.source === 'local'" class="local-badge">L</span>
                </button>
              </div>
              <div v-if="availableModels.length === 0" class="no-models-hint">加载中...</div>
            </div>

            <div
              v-if="avatarRef && avatarRef.clothingState && avatarRef.featureButtons"
              class="menu-section"
            >
              <div class="menu-label">服装部件</div>
              <label v-for="btn in avatarRef.featureButtons" :key="btn.id" class="voxel-checkbox">
                <input
                  v-model="avatarRef.clothingState[btn.id]"
                  type="checkbox"
                  @change="avatarRef.updateClothing()"
                />
                <span class="checkmark"></span>
                {{ btn.label }}
              </label>
            </div>

            <div
              v-if="avatarRef && avatarRef.animList && avatarRef.animList.length > 0"
              class="menu-section"
            >
              <div class="menu-label">动作调试</div>
              <select class="voxel-select" @change="(e) => avatarRef.setAnimation(e.target.value)">
                <option value="">-- 选择动作 --</option>
                <option value="__NONE__">-- 无动画 --</option>
                <option v-for="anim in avatarRef.animList" :key="anim" :value="anim">
                  {{ anim }}
                </option>
              </select>
            </div>
          </div>
        </transition>

        <!-- 移除了 mode="out-in" 以允许快速点击时立即替换 -->
        <transition name="bubble-fade">
          <div
            v-if="displayMode === 'bubble' && (currentText || isThinking)"
            :key="bubbleKey"
            class="bubble"
            :class="{ expanded: isBubbleExpanded }"
            :style="{ top: bubbleTop, left: bubbleLeft }"
          >
            <div class="bubble-content" :class="{ 'cursor-pointer': isThinking }" @mousedown.stop>
              <template v-if="isThinking">
                <div class="thinking-container" @click="stopCurrentTask">
                  <span class="thinking-text">{{ thinkingMessage }}</span>
                  <div v-if="reactTurn > 0" class="react-badge">ReAct: {{ reactTurn }}</div>
                  <div class="interrupt-hint">点击强行中断</div>
                </div>
              </template>
              <template v-else>
                <div ref="bubbleScrollArea" class="bubble-scroll-area">
                  <div
                    v-for="(segment, index) in parsedBubbleContent"
                    :key="index"
                    class="bubble-segment"
                  >
                    <span v-if="segment.type === 'text'">{{ segment.content }}</span>
                    <span v-else-if="segment.type === 'action'" class="action-text"
                      >*{{ segment.content }}*</span
                    >
                    <div v-else-if="segment.type === 'thinking'" class="thinking-block">
                      <div class="thinking-label">💭 思考过程</div>
                      <div class="thinking-content">{{ segment.content }}</div>
                    </div>
                  </div>
                </div>
                <div
                  v-if="isContentOverflowing"
                  class="bubble-expand-btn"
                  @click.stop="toggleBubbleExpand"
                  @mousedown.stop
                >
                  {{ isBubbleExpanded ? '收起' : '展开' }}
                </div>
              </template>
            </div>
            <div class="bubble-tail"></div>
          </div>
        </transition>
      </div>
    </div>

    <!-- 歌词模式覆盖层 -->
    <LyricOverlay
      v-if="displayMode === 'lyric'"
      :text="filteredLyricText"
      :is-thinking="isThinking"
      :thinking-message="thinkingMessage"
    />

    <!-- 文件搜索模态框 -->
    <FileSearchModal v-model:visible="showFileModal" :files="foundFiles" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import BedrockAvatar from '../components/avatar/BedrockAvatar.vue'
import PetNotificationManager from '@/components/ui/PetNotificationManager.vue'
import FileSearchModal from '../components/modals/FileSearchModal.vue'
import LyricOverlay from '../components/chat/LyricOverlay.vue'
import { invoke, listen } from '@/utils/ipcAdapter'
import { API_BASE } from '../config'
import { gatewayClient } from '../api/gateway'

const isElectron = window.electron !== undefined

// 可用模型列表
const availableModels = ref([])
const currentModel = ref(null)

// 默认不传递 manifestPath，让 BedrockAvatar 使用其内部默认逻辑进行初次加载
const currentManifestPath = ref('')
const currentText = ref('主人，我在桌面等你很久啦！')
const isBubbleExpanded = ref(false)
const bubbleKey = ref(0)
const bubbleTop = ref('15%')
const bubbleLeft = ref('50%')
const avatarRef = ref(null)
let bubbleTimer = null

// 模型选择相关函数
const isModelActive = (model) => {
  if (!currentManifestPath.value && model.asset_id.includes('rossi')) {
    return true
  }
  return (
    currentManifestPath.value &&
    (currentManifestPath.value === model.path ||
      currentManifestPath.value.includes(model.display_name))
  )
}

const selectModel = async (model) => {
  currentModel.value = model
  // 使用绝对路径
  if (isElectron) {
    try {
      const loadPath = await invoke('get-model-load-path', model)
      currentManifestPath.value = loadPath
      console.log(`[Pet3DView] 选择模型: ${model.display_name}, 路径: ${loadPath}`)
    } catch (e) {
      console.warn('[Pet3DView] 获取模型路径失败:', e)
      currentManifestPath.value = model.path
    }
  } else {
    currentManifestPath.value = model.path
  }
}

// 调试 refs

const isContentOverflowing = ref(false)
const bubbleScrollArea = ref(null)
const thinkingMessage = ref('努力思考中...')

const uiScale = ref(1)

const updateScale = () => {
  const minDim = Math.min(window.innerWidth, window.innerHeight)
  // 基准尺寸 800px
  let s = minDim / 800
  // 限制缩放范围 [0.5, 1.3]
  s = Math.min(Math.max(s, 0.5), 1.3)
  uiScale.value = s
}

// --- 状态管理 (第一阶段) ---
const currentAgentName = ref('Pero')
const moodText = ref(localStorage.getItem('ppc.mood') || '开心')
const vibeText = ref(localStorage.getItem('ppc.vibe') || '轻松')
const mindText = ref(localStorage.getItem('ppc.mind') || '发呆')
const isWorkMode = ref(false)
const displayMode = ref(localStorage.getItem('ppc.display_mode') || 'bubble') // bubble | lyric
const voiceMode = ref(parseInt(localStorage.getItem('ppc.voice_mode') || '0'))
const isThinking = ref(false)
const reactTurn = ref(0) // 当前 ReAct 轮数
const isPTTRecording = ref(false) // PTT 状态
const isSpeaking = ref(false) // TTS 状态
// const voiceWs = ref(null); // 已弃用
const audioContext = ref(null)
const mediaStream = ref(null)
const scriptProcessor = ref(null)
const currentAudioSource = ref(null)
const audioQueue = ref([])
const isAudioPlaying = ref(false)
const lipSyncFrame = ref(null)
const analyser = ref(null)
let isStartingPTT = false
let isSpeakingState = false
let audioBuffer = []
let lastRmsUpdate = 0
const VAD_THRESHOLD = 0.01
let silenceStart = Date.now()

const showInput = ref(false)
const userInput = ref('')
const inputRef = ref(null)
const showFileModal = ref(false)
const foundFiles = ref([])
const showAppearanceMenu = ref(false)
const localTexts = ref({})
const notificationManager = ref(null)

const parsedBubbleContent = computed(() => {
  const text = currentText.value || ''
  if (!text) return []

  const segments = []
  // [兼容性保留] 正则包含 Monologue 以兼容历史数据展示，2024-02 之后的新消息将不再产生此标签
  const regex =
    /(?:【(Thinking|Error|Reflection|Monologue)[:：]?\s*([\s\S]*?)】)|(?:\n|^)\s*\*([\s\S]+?)\*|(?:\n|^)\s*(Thought|Action)[:：]\s*([\s\S]+?)(?=\n\s*(?:Thought|Action)[:：]|\n\s*\*|【(?:Thinking|Error|Reflection|Monologue)|$)|(?:<(nit(?:-[a-zA-Z0-9-]+)?)>[\s\S]*?<\/\6>)|(?:\[\[\[NIT_CALL\]\]\][\s\S]*?\[\[\[NIT_END\]\]\])/gi

  let lastIndex = 0
  let match

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const normalText = text.substring(lastIndex, match.index)
      if (normalText.trim()) {
        segments.push({ type: 'text', content: normalText })
      }
    }

    if (match[1] !== undefined) {
      const type = match[1].toLowerCase()
      segments.push({ type: type === 'thinking' ? 'thinking' : type, content: match[2].trim() })
    } else if (match[3] !== undefined) {
      segments.push({ type: 'action', content: match[3].trim() })
    } else if (match[4] !== undefined) {
      const type = match[4].toLowerCase() === 'thought' ? 'thinking' : 'action'
      segments.push({ type, content: match[5].trim() })
    }

    lastIndex = regex.lastIndex
  }

  if (lastIndex < text.length) {
    const normalText = text.substring(lastIndex)
    if (normalText.trim()) {
      segments.push({ type: 'text', content: normalText })
    }
  }

  return segments.filter((s) => s.type === 'text' || s.type === 'action')
})

const filteredLyricText = computed(() => {
  return parsedBubbleContent.value
    .map((s) => (s.type === 'action' ? `*${s.content}*` : s.content))
    .join(' ')
    .trim()
})

const checkOverflow = () => {
  if (bubbleScrollArea.value) {
    const el = bubbleScrollArea.value
    isContentOverflowing.value = el.scrollHeight > 210

    if (!isContentOverflowing.value) {
      isBubbleExpanded.value = false
    }
  }
}

watch(
  parsedBubbleContent,
  async () => {
    await nextTick()
    checkOverflow()
  },
  { deep: true }
)

// 气泡自动消失逻辑
watch([currentText, isThinking], ([newText, newThinking]) => {
  if (bubbleTimer) {
    clearTimeout(bubbleTimer)
    bubbleTimer = null
  }

  // 只有在非思考状态且有文字时，才启动自动消失定时器
  if (newText && !newThinking) {
    // 根据文字长度调整停留时间 (5s - 30s)
    const duration = Math.min(Math.max(5000, newText.length * 200), 30000)

    bubbleTimer = setTimeout(() => {
      currentText.value = ''
      isBubbleExpanded.value = false
      bubbleTimer = null
    }, duration)
  }
})

const toggleBubbleExpand = () => {
  isBubbleExpanded.value = !isBubbleExpanded.value
  nextTick(() => {
    checkOverflow()
  })
}

const voiceModeIcon = computed(() => {
  if (voiceMode.value === 0) return '🔇'
  if (voiceMode.value === 1) return '🎙️'
  return '🖱️'
})

const voiceModeTitle = computed(() => {
  if (voiceMode.value === 0) return '语音对话: 已关闭'
  if (voiceMode.value === 1) return '语音对话: 自动感应 (VAD)'
  return '语音对话: 按住说话 (PTT)'
})

// --- 语音和 PTT 逻辑 ---

const cycleVoiceMode = async () => {
  if (isWorkMode.value) {
    currentText.value = '(工作模式下已禁用语音功能)'
    return
  }

  const nextMode = (voiceMode.value + 1) % 3
  voiceMode.value = nextMode
  localStorage.setItem('ppc.voice_mode', nextMode.toString())

  // 在气泡中显示模式变更
  if (nextMode === 0) {
    currentText.value = '语音对话: 已关闭'
    stopVoiceMode()
  } else if (nextMode === 1) {
    currentText.value = '切换到: 自动感应 (VAD)'
  } else {
    currentText.value = '切换到: 按住说话 (PTT)'
  }
  isBubbleExpanded.value = true
  bubbleKey.value++

  if (nextMode !== 0) {
    // 如果还没开启麦克风，则开启
    // if (!voiceWs.value) { // WS 检查已移除
    await startVoiceMode()
    // }
  }
}

const startVoiceMode = async () => {
  console.log('[语音] 正在启动语音模式...')
  try {
    // 0. 确保 AudioContext 存在并激活
    if (!audioContext.value || audioContext.value.state === 'closed') {
      audioContext.value = new (window.AudioContext || window.webkitAudioContext)()
    }
    if (audioContext.value.state === 'suspended') {
      await audioContext.value.resume()
    }

    // 1. 获取麦克风权限
    mediaStream.value = await navigator.mediaDevices.getUserMedia({ audio: true })

    // 检查音频轨道
    const audioTracks = mediaStream.value.getAudioTracks()
    if (audioTracks.length === 0) {
      throw new Error('媒体流中未找到音频轨道')
    }
    console.log('[语音] 已获得麦克风权限:', audioTracks[0].label)

    // 2. Gateway 连接 (假设已经连接，只需注册监听器)
    // 监听来自后端的语音更新请求
    gatewayClient.on('action:voice_update', handleVoiceUpdateRequest)

    // 监听来自后端的音频流 (TTS)
    gatewayClient.on('stream', handleAudioStream)

    console.log('语音网关监听器已注册')
    // 在气泡中显示连接成功
    currentText.value = `语音连接成功: ${voiceModeTitle.value}`
    isBubbleExpanded.value = true
    bubbleKey.value++

    // 3. 开始录音处理
    startRecording()
  } catch (err) {
    console.error('启动语音模式失败:', err)
  }
}

const stopVoiceMode = () => {
  // 移除监听器
  gatewayClient.off('action:voice_update', handleVoiceUpdateRequest)
  gatewayClient.off('stream', handleAudioStream)

  if (mediaStream.value) {
    mediaStream.value.getTracks().forEach((track) => track.stop())
    mediaStream.value = null
  }

  if (audioContext.value) {
    audioContext.value.close()
    audioContext.value = null
  }
}

const startRecording = () => {
  audioContext.value = new (window.AudioContext || window.webkitAudioContext)()
  const source = audioContext.value.createMediaStreamSource(mediaStream.value)

  // 使用 ScriptProcessorNode 处理音频流 (已废弃但广泛支持)
  scriptProcessor.value = audioContext.value.createScriptProcessor(4096, 1, 1)

  source.connect(scriptProcessor.value)
  scriptProcessor.value.connect(audioContext.value.destination)

  scriptProcessor.value.onaudioprocess = (e) => {
    if (voiceMode.value === 0) return

    // 如果正在思考或正在说话，直接忽略新的语音输入
    if (isThinking.value || isSpeaking.value) {
      return
    }

    const inputData = e.inputBuffer.getChannelData(0)

    // --- 模式 2: 按住说话 (PTT) ---
    if (voiceMode.value === 2) {
      if (isPTTRecording.value) {
        audioBuffer.push(new Float32Array(inputData))
      }
      return
    }

    // --- 模式 1: 自动感应 (VAD) ---
    // 1. 计算音量 (RMS)
    let sum = 0
    for (let i = 0; i < inputData.length; i++) {
      sum += inputData[i] * inputData[i]
    }
    const rms = Math.sqrt(sum / inputData.length)

    // 调试日志：每秒输出一次当前音量
    if (Date.now() - lastRmsUpdate > 1000) {
      // console.log('当前麦克风音量 (RMS):', rms.toFixed(4), '阈值:', VAD_THRESHOLD)
      lastRmsUpdate = Date.now()
    }

    // 2. VAD 逻辑
    if (rms > VAD_THRESHOLD) {
      silenceStart = Date.now()
      if (!isSpeakingState) {
        console.log('检测到语音 (音量:', rms.toFixed(4), ')')
        isSpeakingState = true
        audioBuffer = [] // 清空 buffer
      }
      // 收集音频数据
      audioBuffer.push(new Float32Array(inputData))
    } else {
      if (isSpeakingState) {
        // 如果静音超过 1000ms，认为一句话结束
        if (Date.now() - silenceStart > 1000) {
          console.log('语音结束，正在发送缓冲区...')
          isSpeakingState = false
          sendAudioBuffer()
        } else {
          // 短暂静音，继续收集
          audioBuffer.push(new Float32Array(inputData))
        }
      }
    }
  }
}

const startPTT = async () => {
  if (voiceMode.value !== 2) return
  if (isPTTRecording.value || isStartingPTT) return

  isStartingPTT = true
  try {
    if (isThinking.value || isSpeaking.value) {
      console.log('PTT 已忽略: Pero 正忙', {
        isThinking: isThinking.value,
        isSpeaking: isSpeaking.value
      })
      return
    }

    // 确保 AudioContext 已激活
    if (audioContext.value && audioContext.value.state === 'suspended') {
      await audioContext.value.resume()
    }

    isPTTRecording.value = true
    isSpeakingState = true
    audioBuffer = []
    console.log('PTT 已启动')
  } finally {
    isStartingPTT = false
  }
}

const stopPTT = () => {
  if (!isPTTRecording.value) return
  isPTTRecording.value = false
  isSpeakingState = false
  console.log('PTT 结束，正在发送缓冲区...')
  sendAudioBuffer()
}

const sendAudioBuffer = () => {
  if (audioBuffer.length === 0) return

  // 1. 合并 buffer
  const length = audioBuffer.length * 4096
  const merged = new Float32Array(length)
  let offset = 0
  for (const chunk of audioBuffer) {
    merged.set(chunk, offset)
    offset += chunk.length
  }

  // 2. 转换为 WAV
  const wavBlob = encodeWAV(merged, audioContext.value.sampleRate)

  // 3. 发送音频流 (通过 Gateway)
  const reader = new FileReader()
  reader.onloadend = () => {
    if (reader.result) {
      const uint8Array = new Uint8Array(reader.result)
      console.log('[Voice] 发送语音流，大小:', uint8Array.length)
      gatewayClient
        .sendStream('master', uint8Array, 'audio/wav')
        .catch((err) => console.error('[Voice] 发送语音失败:', err))
    }
  }
  reader.readAsArrayBuffer(wavBlob)

  audioBuffer = []
}

const encodeWAV = (samples, sampleRate) => {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)

  const writeString = (view, offset, string) => {
    for (let i = 0; i < string.length; i++) {
      view.setUint8(offset + i, string.charCodeAt(i))
    }
  }

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + samples.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, samples.length * 2, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    let s = Math.max(-1, Math.min(1, samples[i]))
    s = s < 0 ? s * 0x8000 : s * 0x7fff
    view.setInt16(offset, s, true)
    offset += 2
  }

  return new Blob([view], { type: 'audio/wav' })
}

const stopCurrentTask = async () => {
  if (!isThinking.value) return

  try {
    const res = await fetch(`${API_BASE}/task/voice_session/stop`, { method: 'POST' })
    if (res.ok) {
      console.log('[Pet3DView] 任务中断请求已发送')
      notificationManager.value?.add('已请求强行中断本次对话', 'warning', '任务控制')
      // 乐观更新
      isThinking.value = false
      reactTurn.value = 0
    }
  } catch (e) {
    console.error('[Pet3DView] 中断任务失败:', e)
  }
}

// 处理语音更新请求 (状态、文本等)
const handleVoiceUpdateRequest = (req) => {
  const params = req.params || {}
  const type = params.type
  const content = params.content
  const message = params.message
  const turnCount = params.turn_count

  if (type === 'status') {
    if (content === 'listening') {
      stopAudioPlayback(true)
      isThinking.value = true
      thinkingMessage.value = '正在听主人说话...'
      currentText.value = ''
    } else if (content === 'thinking') {
      isThinking.value = true
      thinkingMessage.value = message || '努力思考中...'
      if (turnCount !== undefined) {
        reactTurn.value = parseInt(turnCount)
      }
      currentText.value = ''
    } else if (content === 'speaking') {
      isThinking.value = false
      thinkingMessage.value = '努力思考中...'
      reactTurn.value = 0
    } else if (content === 'idle') {
      isThinking.value = false
      thinkingMessage.value = '努力思考中...'
      reactTurn.value = 0
    }
  } else if (type === 'transcription') {
    console.log('用户说:', content)
  } else if (type === 'text_response') {
    if (content) {
      currentText.value = content
      isThinking.value = false
      thinkingMessage.value = '努力思考中...'
      bubbleKey.value++
    }
  } else if (type === 'error') {
    console.error('语音错误:', content)
    notificationManager.value?.add(content, 'error', '语音错误')
    isThinking.value = false
    currentText.value = ''
  }
}

// 处理音频流 (TTS)
const handleAudioStream = (stream) => {
  if (stream.data) {
    playAudio(stream.data)
  }
}

// 移除了 handleVoiceMessage (旧版 WS)

const stopAudioPlayback = (clearQueue = false) => {
  stopLipSync() // 立即停止口型同步
  if (clearQueue) {
    audioQueue.value = []
    isAudioPlaying.value = false
  }

  if (currentAudioSource.value) {
    try {
      currentAudioSource.value.stop()
    } catch {
      // 忽略
    }
    currentAudioSource.value = null
  }
  isSpeaking.value = false
}

const playAudio = async (base64Audio) => {
  if (!base64Audio) return
  audioQueue.value.push(base64Audio)
  if (!isAudioPlaying.value) {
    processAudioQueue()
  }
}

const startLipSync = (analyserNode) => {
  if (lipSyncFrame.value) cancelAnimationFrame(lipSyncFrame.value)

  const update = () => {
    if (!isSpeaking.value || !analyserNode) {
      if (avatarRef.value && avatarRef.value.setLipSync) {
        avatarRef.value.setLipSync(0)
      }
      return
    }

    const dataArray = new Uint8Array(analyserNode.frequencyBinCount)
    analyserNode.getByteFrequencyData(dataArray)

    // 计算相关频段（人声范围）的平均音量
    let sum = 0
    const startBin = 2 // 跳过极低频
    const endBin = 32 // 约 0-2.7kHz
    for (let i = startBin; i < endBin; i++) {
      sum += dataArray[i]
    }
    const average = sum / (endBin - startBin)

    // 归一化 (0-255 -> 0-1) 并应用增益
    const volume = Math.min(1.0, (average / 255) * 3.0)

    if (avatarRef.value && avatarRef.value.setLipSync) {
      avatarRef.value.setLipSync(volume)
    }

    lipSyncFrame.value = requestAnimationFrame(update)
  }
  update()
}

const stopLipSync = () => {
  if (lipSyncFrame.value) {
    cancelAnimationFrame(lipSyncFrame.value)
    lipSyncFrame.value = null
  }
  if (avatarRef.value && avatarRef.value.setLipSync) {
    avatarRef.value.setLipSync(0)
  }
}

const processAudioQueue = async () => {
  if (audioQueue.value.length === 0) {
    isAudioPlaying.value = false
    isSpeaking.value = false
    return
  }

  isAudioPlaying.value = true
  const audioData = audioQueue.value.shift()
  isSpeaking.value = true

  let ctx = audioContext.value

  if (!ctx || ctx.state === 'closed') {
    ctx = new (window.AudioContext || window.webkitAudioContext)()
    audioContext.value = ctx
  }

  if (ctx.state === 'suspended') {
    try {
      await ctx.resume()
    } catch (e) {
      console.warn('[Pero] 恢复 AudioContext 失败:', e)
    }
  }

  try {
    let arrayBuffer
    if (typeof audioData === 'string') {
      // Base64 字符串回退
      const binaryString = window.atob(audioData)
      const len = binaryString.length
      const bytes = new Uint8Array(len)
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }
      arrayBuffer = bytes.buffer
    } else if (audioData instanceof Uint8Array) {
      // 来自 Protobuf 的 Uint8Array
      arrayBuffer = new Uint8Array(audioData).buffer
    } else {
      throw new Error('未知音频数据类型')
    }

    const audioBuffer = await ctx.decodeAudioData(arrayBuffer)

    const source = ctx.createBufferSource()
    source.buffer = audioBuffer
    currentAudioSource.value = source

    // 创建分析器用于口型同步
    const analyserNode = ctx.createAnalyser()
    analyserNode.fftSize = 256
    analyser.value = analyserNode

    source.connect(analyserNode)
    analyserNode.connect(ctx.destination)

    source.start(0)
    startLipSync(analyserNode)

    source.onended = () => {
      currentAudioSource.value = null
      stopLipSync()
      source.disconnect()
      analyserNode.disconnect()
      processAudioQueue()
    }
  } catch (e) {
    console.error('[Pero] 音频解码错误:', e)
    processAudioQueue()
  }
}

// --- 全局按键处理 ---

const handleGlobalKeyDown = (e) => {
  if (isWorkMode.value) return

  // 1. Alt + V 切换语音模式
  if (e.altKey && !e.shiftKey && e.code === 'KeyV') {
    e.preventDefault()
    cycleVoiceMode()
    return
  }

  // 2. Alt + Shift + V 按键说话
  if (
    e.altKey &&
    e.shiftKey &&
    e.code === 'KeyV' &&
    voiceMode.value === 2 &&
    !isPTTRecording.value
  ) {
    e.preventDefault()
    startPTT()
  }
}

const handleGlobalKeyUp = (e) => {
  if (isWorkMode.value) return

  if (e.code === 'KeyV' && voiceMode.value === 2 && isPTTRecording.value) {
    stopPTT()
  }
}

// --- Agent 逻辑 ---
const fetchActiveAgent = async () => {
  try {
    const res = await fetch(`${API_BASE}/agents`)
    if (res.ok) {
      const agents = await res.json()
      const active = agents.find((a) => a.is_active)
      if (active) {
        currentAgentName.value = active.name
      }
    }
  } catch (e) {
    console.error('获取活跃 Agent 失败:', e)
  }
}

// --- 生命周期 & IPC ---
let unlistenFunctions = []

const setIgnoreMouse = (ignore) => {
  if (window._lastIgnoreState === ignore) return
  window._lastIgnoreState = ignore
  invoke('set_ignore_mouse', ignore).catch((e) => console.error('set_ignore_mouse 失败', e))
}

const onHoverStart = () => {
  setIgnoreMouse(false)
}

const onHoverEnd = () => {
  if (!isDragging.value) {
    setIgnoreMouse(true)
  }
}

const onUIEnter = () => {
  setIgnoreMouse(false)
}

const onUILeave = () => {
  if (!isDragging.value) {
    setIgnoreMouse(true)
  }
}

// 拖拽状态
let startX = 0
let startY = 0
const isDragging = ref(false)

const onMouseDown = (e) => {
  if (e.button !== 0) return

  startX = e.screenX
  startY = e.screenY

  const onMouseMove = (moveEvent) => {
    const movedX = Math.abs(moveEvent.screenX - startX)
    const movedY = Math.abs(moveEvent.screenY - startY)

    if (!isDragging.value && (movedX > 5 || movedY > 5)) {
      isDragging.value = true
      // 通知主进程开始拖拽
      const offsetX = e.screenX - window.screenX
      const offsetY = e.screenY - window.screenY

      if (window.electron && window.electron.send) {
        window.electron.send('window-drag-start', { offsetX, offsetY })
      } else {
        invoke('window-drag-start', { offsetX, offsetY }).catch(() => {})
      }
    }
  }

  const onMouseUp = () => {
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)

    if (isDragging.value) {
      isDragging.value = false

      if (window.electron && window.electron.send) {
        window.electron.send('window-drag-end')
      } else {
        invoke('window-drag-end').catch(() => {})
      }

      setIgnoreMouse(false)
    }
  }

  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

onMounted(async () => {
  fetchActiveAgent()
  loadLocalTexts()

  // 扫描可用的 3D 模型
  if (isElectron) {
    try {
      const models = await invoke('scan-3d-models')
      availableModels.value = models || []
      console.log(`[Pet3DView] 扫描到 ${models.length} 个模型`)
    } catch (e) {
      console.warn('[Pet3DView] 扫描模型失败:', e)
    }
  }

  // 初始获取 Pet 状态 (与后端同步)
  const fetchPetState = async () => {
    try {
      const res = await fetch(`${API_BASE}/pet/state`)
      if (res.ok) {
        const state = await res.json()
        if (state.mood) {
          moodText.value = state.mood
          localStorage.setItem('ppc.mood', state.mood)
        }
        if (state.vibe) {
          vibeText.value = state.vibe
          localStorage.setItem('ppc.vibe', state.vibe)
        }
        if (state.mind) {
          mindText.value = state.mind
          localStorage.setItem('ppc.mind', state.mind)
        }

        // 同步交互文本
        if (state.click_messages_json) {
          try {
            const clickData = JSON.parse(state.click_messages_json)
            let curTexts = localTexts.value || {}
            // 类似 state_update 的合并逻辑
            if (clickData.head)
              curTexts['click_head_01'] = Array.isArray(clickData.head)
                ? clickData.head[0]
                : clickData.head
            if (clickData.chest)
              curTexts['click_chest_01'] = Array.isArray(clickData.chest)
                ? clickData.chest[0]
                : clickData.chest
            if (clickData.body)
              curTexts['click_body_01'] = Array.isArray(clickData.body)
                ? clickData.body[0]
                : clickData.body
            if (clickData.default)
              curTexts['click_messages_01'] = Array.isArray(clickData.default)
                ? clickData.default[0]
                : clickData.default
            localTexts.value = { ...curTexts }
          } catch {
            // 忽略
          }
        }
      }
    } catch (e) {
      console.warn('[Pet3DView] 获取初始状态失败:', e)
    }
  }

  // 立即获取，然后定期轮询作为备份
  fetchPetState()
  setInterval(fetchPetState, 30000) // 30s polling fallback

  // 1. 初始鼠标穿透
  await invoke('set_ignore_mouse', true)

  // 绑定拖拽监听器
  window.addEventListener('mousedown', onMouseDown)

  // 绑定键盘监听器
  window.addEventListener('keydown', handleGlobalKeyDown)
  window.addEventListener('keyup', handleGlobalKeyUp)

  // ... 其余监听器 ...
  // 后端日志 -> 思考气泡
  const unlistenLog = await listen('backend-log', (event) => {
    console.log('[Backend]', event.payload)
    // 简单逻辑：如果日志包含 "Thinking"，则显示
    if (typeof event.payload === 'string' && event.payload.includes('Thinking')) {
      currentText.value = '正在思考...'
      isThinking.value = true
    }
  })
  unlistenFunctions.push(unlistenLog)

  // 状态更新
  const unlistenMood = await listen('update-mood', (event) => {
    moodText.value = event.payload
    localStorage.setItem('ppc.mood', event.payload)
  })
  unlistenFunctions.push(unlistenMood)

  const unlistenVibe = await listen('update-vibe', (event) => {
    vibeText.value = event.payload
    localStorage.setItem('ppc.vibe', event.payload)
  })
  unlistenFunctions.push(unlistenVibe)

  const unlistenMind = await listen('update-mind', (event) => {
    mindText.value = event.payload
    localStorage.setItem('ppc.mind', event.payload)
  })
  unlistenFunctions.push(unlistenMind)

  // 工作模式
  const unlistenWorkMode = await listen('work-mode-changed', (event) => {
    isWorkMode.value = event.payload.is_work_mode
    if (isWorkMode.value) {
      currentText.value = '进入工作模式 (Session Isolated)'
    } else {
      currentText.value = '工作辛苦啦！'
    }
  })
  unlistenFunctions.push(unlistenWorkMode)

  // 聊天同步（助手回复）
  const unlistenChat = await listen('sync-chat-to-pet', (event) => {
    if (isWorkMode.value) return
    const { role, content } = event.payload
    if (role === 'assistant') {
      currentText.value = content
      isThinking.value = false
      // 触发气泡展开
      isBubbleExpanded.value = true
      bubbleKey.value++
    }
  })
  unlistenFunctions.push(unlistenChat)

  // 文件搜索
  const unlistenSearch = await listen('file-search-result', (event) => {
    foundFiles.value = event.payload
    showFileModal.value = true
  })
  unlistenFunctions.push(unlistenSearch)

  // 状态更新（来自 Gateway）
  gatewayClient.on('action:agent_changed', async () => {
    console.log('[Pet3DView] 检测到助手变更，正在刷新状态...')

    // 1. 刷新当前助手名称
    await fetchActiveAgent()

    // 2. 刷新宠物状态 (心情, 氛围, 想法)
    await fetchPetState()

    // 3. 重新加载交互文本
    await loadLocalTexts()

    // 4. 通知用户
    currentText.value = `(已切换为 ${currentAgentName.value})`
    isThinking.value = false
    isBubbleExpanded.value = true
    bubbleKey.value++

    // 短暂延迟后自动隐藏气泡
    setTimeout(() => {
      if (currentText.value.includes('(已切换为')) {
        currentText.value = ''
        isBubbleExpanded.value = false
      }
    }, 3000)
  })

  gatewayClient.on('action:state_update', (data) => {
    // Gateway 发出完整的 ActionRequest 对象，所以实际数据在 'params' 中
    // GatewayClient emits: this.emit(`action:${envelope.request.actionName}`, envelope.request);
    const params = data.params || data

    // 1. 基础状态
    if (params.mood) {
      moodText.value = params.mood
      localStorage.setItem('ppc.mood', params.mood)
    }
    if (params.vibe) {
      vibeText.value = params.vibe
      localStorage.setItem('ppc.vibe', params.vibe)
    }
    if (params.mind) {
      mindText.value = params.mind
      localStorage.setItem('ppc.mind', params.mind)
    }

    // 2. 交互消息 (点击/空闲/返回)
    let curTexts = {}
    const storageKey = `ppc.waifu.texts.${currentAgentName.value || 'Pero'}`

    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) curTexts = JSON.parse(saved)
    } catch {
      // 忽略
    }

    let updated = false

    // 处理点击消息
    if (params.click_messages) {
      let clickData = params.click_messages
      if (typeof clickData === 'string') {
        try {
          clickData = JSON.parse(clickData)
        } catch {
          // 忽略
        }
      }

      if (typeof clickData === 'object') {
        // 将简单格式 { "body": ["msg1"] } 合并为 waifu-tips 格式
        if (clickData.head) {
          curTexts['click_head_01'] = Array.isArray(clickData.head)
            ? clickData.head[0]
            : clickData.head
        }
        if (clickData.chest) {
          curTexts['click_chest_01'] = Array.isArray(clickData.chest)
            ? clickData.chest[0]
            : clickData.chest
        }
        if (clickData.body) {
          curTexts['click_body_01'] = Array.isArray(clickData.body)
            ? clickData.body[0]
            : clickData.body
        }
        updated = true
      }
    }

    // 处理空闲消息
    if (data.idle_messages) {
      let msgs = data.idle_messages
      if (typeof msgs === 'string') {
        try {
          msgs = JSON.parse(msgs)
        } catch {
          // 忽略
        }
      }

      if (Array.isArray(msgs)) {
        msgs.forEach((msg, i) => {
          curTexts[`idleMessages_0${i + 1}`] = msg
        })
        updated = true
      }
    }

    if (updated) {
      localStorage.setItem(storageKey, JSON.stringify(curTexts))
      localTexts.value = curTexts
      console.log('[Pet3DView] 通过 Gateway 更新了交互文本:', curTexts)
    }
  })

  // 提醒触发 (来自 Gateway)
  gatewayClient.on('action:reminder_trigger', (params) => {
    const content = params.content || '提醒时间到！'

    // 1. 显示气泡
    currentText.value = `⏰ ${content}`
    isBubbleExpanded.value = true
    bubbleKey.value++

    // 2. 播放音效 / TTS
    if (voiceMode.value !== 0) {
      // 使用浏览器原生 TTS 进行即时反馈
      if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(content)
        // 尝试寻找中文语音
        const voices = window.speechSynthesis.getVoices()
        const zhVoice = voices.find((v) => v.lang.includes('zh'))
        if (zhVoice) utterance.voice = zhVoice
        window.speechSynthesis.speak(utterance)
      }
    }

    // 3. 桌面通知（原生）
    if (window.electron && window.electron.send) {
      window.electron.send('show-notification', { title: 'Pero 提醒', body: content })
    }
  })

  // 全局鼠标追踪 (修复角色在窗口外时不跟随鼠标的问题)
  if (window.electron && window.electron.on) {
    const cleanupMouse = window.electron.on('global-mouse-move', (_event, { x, y }) => {
      const winW = window.innerWidth
      const winH = window.innerHeight

      // 1. 直接更新 Avatar (比事件分发更可靠)
      if (avatarRef.value && avatarRef.value.setGlobalMouse) {
        avatarRef.value.setGlobalMouse(x, y)
      }

      // 2. 分发事件给其他监听器 (回退)
      // 仅在窗口边界外分发以避免重复事件
      if (x < 0 || x > winW || y < 0 || y > winH) {
        const mouseEvent = new MouseEvent('mousemove', {
          clientX: x,
          clientY: y,
          bubbles: true,
          cancelable: true,
          view: window
        })
        window.dispatchEvent(mouseEvent)
      }
    })
    unlistenFunctions.push(cleanupMouse)
  } else {
    console.warn('未找到 window.electron，全局鼠标追踪已禁用')
  }
})

onUnmounted(() => {
  if (bubbleTimer) {
    clearTimeout(bubbleTimer)
    bubbleTimer = null
  }
  unlistenFunctions.forEach((fn) => fn())
  unlistenFunctions = []
  window.removeEventListener('mousedown', onMouseDown)
  window.removeEventListener('resize', updateScale)
})

const toggleDisplayMode = () => {
  displayMode.value = displayMode.value === 'bubble' ? 'lyric' : 'bubble'
  localStorage.setItem('ppc.display_mode', displayMode.value)

  // 在气泡中显示提示
  if (displayMode.value === 'lyric') {
    currentText.value = '切换到: 悬浮歌词模式'
  } else {
    currentText.value = '切换到: 经典气泡模式'
  }
  isBubbleExpanded.value = false
  bubbleKey.value++
}

const toggleUI = () => {
  showInput.value = !showInput.value
  if (!showInput.value) {
    showAppearanceMenu.value = false
  }
}

const toggleAppearanceMenu = () => {
  showAppearanceMenu.value = !showAppearanceMenu.value
}

const loadLocalTexts = async () => {
  try {
    const response = await fetch('waifu-texts.json')
    const baseTexts = await response.json()
    const storageKey = `ppc.waifu.texts.${currentAgentName.value || 'default'}`
    let dynamicTexts = {}
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) dynamicTexts = JSON.parse(saved)
    } catch (e) {
      console.warn('从 localStorage 解析动态文本失败:', e)
    }
    localTexts.value = { ...baseTexts, ...dynamicTexts }
    console.log('本地文本已加载:', Object.keys(localTexts.value).length)
  } catch (err) {
    console.error('加载本地文本失败:', err)
    // 回退
    localTexts.value = {
      click_head_01: '嘿嘿，好痒呀~',
      click_head_02: '是在摸摸头吗？',
      click_body_01: '不要戳那里啦！',
      click_messages_01: '要牵手手吗？'
    }
  }
}

const getRandomLocalText = (category) => {
  if (!localTexts.value) return null

  // 查找以分类开头的键（如 'click_head'）
  const keys = Object.keys(localTexts.value).filter((k) => k.startsWith(category))
  if (keys.length === 0) return null

  const randomKey = keys[Math.floor(Math.random() * keys.length)]
  return localTexts.value[randomKey]
}

const onPet = (event) => {
  // console.log('Pet detected:', event);

  let text = null

  switch (event.type) {
    case 'head':
      text = getRandomLocalText('click_head')
      if (!text) text = '嘿嘿，好痒呀~'
      break
    case 'arm':
      text = getRandomLocalText('click_messages') // Generic interaction
      if (!text) text = '要牵手手吗？'
      break
    case 'body':
      // 先尝试胸部，再尝试身体
      text = getRandomLocalText('click_chest') || getRandomLocalText('click_body')
      if (!text) text = '不要戳那里啦！'
      break
    case 'leg':
      text = getRandomLocalText('click_body') || getRandomLocalText('click_messages')
      if (!text) text = '裙子不能掀！'
      break
    default:
      text = getRandomLocalText('click_messages')
  }

  // console.log('选中文本:', text);

  // 回退
  if (!text) {
    text = '嗯？'
  }

  // 即使文本相同也强制重新渲染以获得即时视觉反馈
  currentText.value = text
  isBubbleExpanded.value = true
  bubbleKey.value++

  // 随机垂直偏移 (12% 到 18%)
  const randomTop = 12 + Math.random() * 6
  bubbleTop.value = `${randomTop}%`

  // 随机水平偏移 (-10% 到 10%)
  // 因为使用了 translate(-50%, 0)，调整 margin-left 或 left 最简单
  // 用 calc 实现 left: 50% + offset
  // 实际上用像素做水平偏移更安全，避免窄气泡问题
  // 或者直接用百分比: -5% 到 5%
  const randomLeftPct = Math.random() * 10 - 5
  // 我们可以绑定 'left' 样式
  // 默认 left: 50%, transform: translateX(-50%)
  // 我们可以直接调整 left 百分比
  bubbleLeft.value = `${50 + randomLeftPct}%`
}

const sendMessage = async () => {
  if (!userInput.value.trim()) return
  if (isThinking.value) return

  const text = userInput.value
  userInput.value = ''
  isThinking.value = true
  currentText.value = '思考中...'

  try {
    await invoke('chat-message', { message: text })
  } catch (e) {
    console.error('发送消息失败:', e)
    isThinking.value = false
    notificationManager.value?.add('发送消息失败', 'error', '通信错误')
    currentText.value = ''
  }
}

// 监听后端回复
onMounted(async () => {
  // 监听 Gateway 消息（通过 IPC 或 WebSocket）
  // 假设后端通过 Gateway 广播 'action:text_response'
  gatewayClient.on('action:text_response', (data) => {
    const params = data.params || data
    const content = params.content

    if (content) {
      currentText.value = content
      isThinking.value = false
      isBubbleExpanded.value = true
      bubbleKey.value++
    }
  })

  // 监听状态更新
  gatewayClient.on('action:voice_update', (data) => {
    const params = data.params || data
    handleVoiceUpdateRequest(params)
  })

  // 监听 TTS 音频流
  gatewayClient.on('stream', handleAudioStream)

  // 初始化时连接 Gateway
  // (如果 App.vue 或其他地方已经连接，这里可能需要调整，但 GatewayClient 是单例或共享的吗？)
  // 假设 gatewayClient 是全局导入的单例

  // 初始化 UI 缩放
  window.addEventListener('resize', updateScale)
  updateScale()
})

const windowSizes = [
  { width: 600, height: 600 },
  { width: 800, height: 800 },
  { width: 1000, height: 1000 },
  { width: 1200, height: 1200 },
  { width: 500, height: 500 }
]
const currentSizeIndex = ref(0) // Default 600x600

const toggleWindowSize = async () => {
  // 递增索引并循环
  // 增加索引并循环
  currentSizeIndex.value = (currentSizeIndex.value + 1) % windowSizes.length
  const size = windowSizes[currentSizeIndex.value]
  console.log(
    `[Pet3DView] 切换窗口大小为: ${size.width}x${size.height} (索引: ${currentSizeIndex.value})`
  )

  try {
    await invoke('resize-pet-window', size)
  } catch (e) {
    console.error('[Pet3DView] 调整大小失败:', e)
  }
}

const reloadPet = () => {
  window.location.reload()
}

const openChatWindow = () => {
  invoke('open_ide_window').catch(console.error)
}

const openDashboard = () => {
  invoke('open_dashboard').catch(console.error)
}

const minimizeToTray = () => {
  invoke('hide_pet_window').catch(console.error)
}
</script>

<style scoped>
/* 确保容器占满窗口并支持透明 */
.pet-3d-container {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  background: transparent; /* 对 Electron 透明窗口至关重要 */
  overflow: hidden;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  /* 使用像素字体或简洁无衬线字体 */
  font-family: 'Segoe UI', sans-serif;
}

.ui-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none; /* 让点击穿透到 3D 场景/桌面 */
  display: flex;
  justify-content: center;
  align-items: center;
}

.ui-scalable-wrapper {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  transform-origin: center center;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 角色选择网格 */
.character-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 8px;
}

.char-btn {
  background: #4a4a4a;
  border: 2px solid #000;
  box-shadow:
    inset -2px -2px #2a2a2a,
    inset 2px 2px #6a6a6a;
  color: #fff;
  padding: 6px 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.1s;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-btn:hover {
  background: #5a5a5a;
  transform: translateY(-1px);
}

.char-btn:active {
  box-shadow:
    inset 2px 2px #2a2a2a,
    inset -2px -2px #6a6a6a;
  transform: translateY(1px);
}

.char-btn.active {
  background: #3a7a3a;
  border-color: #2eeb2e;
  box-shadow:
    inset -2px -2px #1a4a1a,
    inset 2px 2px #5aba5a;
}

.workshop-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  font-size: 10px;
  background: #4a90d9;
  color: white;
  border-radius: 3px;
  vertical-align: middle;
}

.local-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  font-size: 10px;
  background: #d94a4a;
  color: white;
  border-radius: 3px;
  vertical-align: middle;
}

.no-models-hint {
  color: #888;
  font-size: 12px;
  text-align: center;
  padding: 8px;
}

/* 调整外观菜单高度以适应新内容 */
.appearance-menu {
  max-height: 80vh;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #555 #222;
}

.appearance-menu::-webkit-scrollbar {
  width: 6px;
}

.appearance-menu::-webkit-scrollbar-track {
  background: #222;
}

.appearance-menu::-webkit-scrollbar-thumb {
  background: #555;
  border: 1px solid #000;
}

/* 汉化已有注释 */
/* 气泡样式 */
.bubble {
  position: absolute;
  transform: translateX(-50%);

  /* 体素风格 */
  /* Voxel 风格 */
  background-color: rgba(20, 20, 20, 0.85);
  border: 2px solid #e0e0e0;
  border-radius: 4px;
  padding: 12px 16px;
  z-index: 100;
  max-width: 280px;

  /* 硬阴影 */
  /* 硬阴影 */
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.5);

  pointer-events: auto;
  animation: bubble-float 3s infinite ease-in-out;
  display: flex;
  flex-direction: column;
  transition: all 0.2s steps(4);

  color: #ffffff;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  line-height: 1.5;
  text-shadow: 1px 1px 0 #000;
}

.bubble:hover {
  transform: scale(1.02);
  background-color: rgba(30, 30, 30, 0.95);
  border-color: #ffffff;
  z-index: 110;
}

/* 像素尾巴 */
/* 像素风格尾巴 */
.bubble-tail {
  position: absolute;
  bottom: -6px;
  left: 50%;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid #e0e0e0;
}

.bubble-tail::after {
  content: '';
  position: absolute;
  top: -9px;
  left: -4px;
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 4px solid rgba(20, 20, 20, 0.85);
}

.bubble-content {
  cursor: pointer;
}

.bubble.expanded {
  max-height: 500px;
  overflow-y: auto;
}

.bubble.expanded::-webkit-scrollbar {
  width: 6px;
}
.bubble.expanded::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
}
.bubble.expanded::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 0;
  border: 1px solid #444;
}
.bubble.expanded::-webkit-scrollbar-thumb:hover {
  background: #aaa;
}

.bubble-scroll-area {
  max-height: 200px;
  overflow: hidden;
  transition: max-height 0.3s ease;
  position: relative;
}

.bubble.expanded .bubble-scroll-area {
  max-height: 500px;
  overflow-y: auto;
}

.bubble-expand-btn {
  font-size: 12px;
  color: #aaaaaa;
  text-align: center;
  margin-top: 8px;
  cursor: pointer;
  padding-top: 4px;
  border-top: 1px dashed #666;
  user-select: none;
  font-family: 'Consolas', monospace;
}

.bubble-expand-btn:hover {
  color: #ffffff;
  font-weight: bold;
}

.thinking-text {
  color: #aaaaaa;
  font-style: italic;
  display: flex;
  align-items: center;
  font-family: 'Consolas', monospace;
}

.thinking-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 4px;
}

.react-badge {
  background: #ff4757;
  color: white;
  font-size: 10px;
  padding: 2px 8px;
  border: 2px solid #000;
  box-shadow: 2px 2px 0px rgba(0, 0, 0, 0.5);
  font-weight: bold;
  text-transform: uppercase;
  margin-top: 4px;
  animation: react-pulse 1s infinite alternate;
}

.interrupt-hint {
  font-size: 10px;
  color: #888;
  margin-top: 4px;
  opacity: 0.8;
  font-family: 'Segoe UI', sans-serif;
}

.thinking-container:hover .interrupt-hint {
  color: #ff4757;
  opacity: 1;
  font-weight: bold;
}

@keyframes react-pulse {
  from {
    transform: scale(1);
    background: #ff4757;
  }
  to {
    transform: scale(1.05);
    background: #ff6b81;
  }
}

.thinking-text::after {
  content: '...';
  display: inline-block;
  width: 12px;
  animation: thinking-dots 1.5s infinite;
}

@keyframes thinking-dots {
  0% {
    content: '.';
  }
  33% {
    content: '..';
  }
  66% {
    content: '...';
  }
}

.thinking-block {
  margin: 12px 0;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  border: 1px solid #555;
  overflow: hidden;
}

.thinking-label {
  padding: 4px 8px;
  background: rgba(50, 50, 50, 0.5);
  font-size: 11px;
  font-weight: bold;
  color: #ccc;
  border-bottom: 1px solid #555;
  font-family: 'Consolas', monospace;
}

.thinking-content {
  padding: 8px;
  font-family: 'Consolas', monospace;
  font-size: 12px;
  color: #ddd;
  white-space: pre-wrap;
  background: rgba(0, 0, 0, 0.2);
}

.action-text {
  color: #aaddff;
  font-style: italic;
  font-size: 0.95em;
  margin: 0 2px;
}

@keyframes bubble-float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-4px);
  }
}

.bubble-fade-enter-active {
  transition: all 0.15s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.bubble-fade-leave-active {
  transition: opacity 0.1s ease-out;
  position: absolute;
}
.bubble-fade-enter-from {
  opacity: 0;
  transform: translateX(-50%) scale(0.8) translateY(10px);
}
.bubble-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) scale(1.1);
}

/* 状态标签（体素） */
/* 状态标签 (Voxel) */
.status-tags {
  position: absolute;
  left: 40px;
  top: 160px;
  /* transform: translate(-320px, -250px); 已移除，使用内联缩放 */
  display: flex;
  flex-direction: column;
  gap: 12px;
  perspective: 1000px;
  align-items: flex-start;
  pointer-events: auto;
}

.status-tag {
  background: rgba(20, 20, 20, 0.85);
  padding: 8px 14px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  color: #ffffff;
  border: 2px solid #e0e0e0;
  white-space: nowrap;
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.5);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
  cursor: default;
  font-family: 'Consolas', monospace;
  text-shadow: 1px 1px 0 #000;
}

.status-tag:hover {
  transform: translateX(5px);
  background: rgba(40, 40, 40, 0.95);
  box-shadow: 6px 6px 0px rgba(0, 0, 0, 0.6);
  z-index: 110;
  border-color: #ffffff;
}

.status-tag.mood {
  border-color: #ff88aa;
  color: #ffccdd;
}

.status-tag.vibe {
  border-color: #88ccff;
  color: #cceeff;
}

.status-tag.mind {
  border-color: #88ffaa;
  color: #ccffdd;
  white-space: normal;
  max-width: 180px;
  word-break: break-all;
  line-height: 1.4;
  padding: 8px 12px;
  align-items: flex-start;
}

@keyframes float-tag {
  /* 体素风格减少浮动 */
  /* 减少 Voxel 风格的浮动 */
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-2px);
  }
}

/* 浮动触发器（体素方块） */
/* 悬浮触发器 (Voxel 立方体) */
.floating-trigger {
  position: absolute;
  left: 50%;
  top: 55%;
  transform: translate(140px, -50%);
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 100;
  pointer-events: auto;
}

.trigger-core {
  position: relative;
  width: 24px;
  height: 24px;
  transition: all 0.3s ease;
  animation: core-idle 4s infinite ease-in-out;
}

@keyframes core-idle {
  0% {
    transform: translateY(0) rotate(0deg);
  }
  25% {
    transform: translateY(-3px) rotate(15deg);
  }
  50% {
    transform: translateY(0) rotate(0deg);
  }
  75% {
    transform: translateY(3px) rotate(-15deg);
  }
  100% {
    transform: translateY(0) rotate(0deg);
  }
}

.core-dot {
  position: absolute;
  width: 100%;
  height: 100%;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 4px; /* 稍微更圆润 */
  transition: all 0.2s ease;
  box-shadow:
    0 0 15px rgba(255, 255, 255, 0.6),
    2px 2px 0px rgba(0, 0, 0, 0.3);
  border: 2px solid #fff;
}

.pulse-ring {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-radius: 4px;
  opacity: 0;
  animation: pulse-ring-smooth 2s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
  box-sizing: border-box;
}

@keyframes pulse-ring-smooth {
  0% {
    transform: scale(0.8) rotate(0deg);
    opacity: 0.8;
    border-width: 2px;
  }
  50% {
    opacity: 0.5;
  }
  100% {
    transform: scale(2.4) rotate(90deg);
    opacity: 0;
    border-width: 0px;
  }
}

.floating-trigger:hover .trigger-core {
  animation-play-state: paused;
  transform: scale(1.1) rotate(45deg);
}

.floating-trigger:hover .core-dot {
  background: #ffffff;
  transform: scale(1);
  box-shadow:
    0 0 20px rgba(255, 255, 255, 1),
    0 0 40px rgba(255, 255, 255, 0.6);
}

.floating-trigger.active .trigger-core {
  transform: rotate(45deg);
}

.floating-trigger.active .core-dot {
  background: #ff88aa;
  border-color: #ffccdd;
  box-shadow: 0 0 15px rgba(255, 136, 170, 0.6);
}

.floating-trigger.active .pulse-ring {
  border-color: rgba(255, 136, 170, 0.5);
  animation-duration: 1.5s;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.input-overlay {
  position: absolute;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  -webkit-app-region: no-drag;
  perspective: 1000px;
  pointer-events: auto;
}

.chat-input {
  background: rgba(20, 20, 20, 0.85);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: 2px solid #e0e0e0;
  border-radius: 4px;
  padding: 10px 16px;
  width: 240px;
  outline: none;
  font-size: 14px;
  font-weight: 500;
  color: #ffffff;
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.5);
  transition: all 0.2s;
  font-family: 'Consolas', monospace;
}

.chat-input::placeholder {
  color: #888;
  font-weight: 400;
}

.chat-input:focus {
  width: 280px;
  background: rgba(30, 30, 30, 0.95);
  border-color: #ffffff;
  box-shadow: 6px 6px 0px rgba(0, 0, 0, 0.6);
  transform: translateY(-2px);
  color: #ffffff;
}

.pet-tools {
  position: absolute;
  left: 50%;
  top: 55%;
  transform: translate(200px, -50%);
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(20, 20, 20, 0.7);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  padding: 8px;
  border-radius: 6px;
  -webkit-app-region: no-drag;
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.5);
  border: 2px solid #666;
  pointer-events: auto;
}

.tool-btn {
  background: rgba(40, 40, 40, 0.8);
  border: 2px solid #888;
  width: 38px;
  height: 38px;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  transition: all 0.15s;
  box-shadow: 2px 2px 0px rgba(0, 0, 0, 0.5);
  color: #ddd;
}

.tool-btn:hover,
.tool-btn.active {
  transform: translate(-1px, -1px);
  background: #555;
  border-color: #fff;
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.6);
  color: #fff;
}

.tool-btn:active {
  transform: translate(2px, 2px);
  box-shadow: 0px 0px 0px rgba(0, 0, 0, 0.5);
}

.voice-btn.active.mode-vad {
  color: #ff99cc;
  border-color: #ff99cc;
}

.voice-btn.active.mode-ptt {
  color: #5fb878;
  border-color: #5fb878;
}

/* 外观菜单 (体素风格) */
.appearance-menu {
  position: absolute;
  left: 50%;
  top: 55%;
  transform: translate(-320px, -50%);
  background: rgba(20, 20, 20, 0.95);
  border: 2px solid #fff;
  border-radius: 6px;
  padding: 12px;
  width: 200px;
  color: white;
  box-shadow: 6px 6px 0px rgba(0, 0, 0, 0.6);
  pointer-events: auto;
  font-family: 'Consolas', monospace;
  z-index: 101;
}

.menu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #444;
  font-weight: bold;
}

.close-mini-btn {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}
.close-mini-btn:hover {
  color: #fff;
}

.menu-section {
  margin-bottom: 12px;
}

.menu-label {
  font-size: 11px;
  color: #aaa;
  margin-bottom: 6px;
  text-transform: uppercase;
}

.voxel-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  cursor: pointer;
  font-size: 13px;
  user-select: none;
}

.voxel-checkbox input {
  display: none;
}

.voxel-checkbox .checkmark {
  width: 16px;
  height: 16px;
  background: #333;
  border: 2px solid #888;
  position: relative;
  display: inline-block;
  transition: all 0.1s;
}

.voxel-checkbox:hover .checkmark {
  border-color: #fff;
}

.voxel-checkbox input:checked + .checkmark {
  background: #ff88aa;
  border-color: #fff;
}

.voxel-checkbox input:checked + .checkmark::after {
  content: '';
  position: absolute;
  left: 4px;
  top: 1px;
  width: 4px;
  height: 8px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.voxel-select {
  width: 100%;
  padding: 6px;
  background: #333;
  border: 2px solid #888;
  color: white;
  font-family: inherit;
  cursor: pointer;
  outline: none;
}
.voxel-select:hover {
  border-color: #fff;
}

/* 按键说话按钮（体素） */
.ptt-voxel-container {
  position: absolute;
  left: 50%;
  bottom: 70px;
  top: auto;
  transform: translateX(-220px);
  z-index: 100;
  pointer-events: auto;
}

.ptt-voxel-btn {
  background: rgba(40, 40, 40, 0.9);
  border: 2px solid #888;
  border-radius: 50%;
  width: 64px;
  height: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.5);
  transition: all 0.1s;
  color: #ddd;
}

.ptt-voxel-btn:hover {
  transform: translate(-1px, -1px);
  background: #555;
  border-color: #fff;
  box-shadow: 6px 6px 0px rgba(0, 0, 0, 0.6);
  color: #fff;
}

.ptt-voxel-btn:active {
  transform: translate(2px, 2px);
  box-shadow: 0px 0px 0px rgba(0, 0, 0, 0.5);
}

.ptt-voxel-btn.recording {
  background: #ff4444;
  border-color: #ffcccc;
  color: white;
  animation: pulse-recording 1.5s infinite;
}

.ptt-icon {
  font-size: 24px;
  line-height: 1;
}

.ptt-text {
  font-size: 9px;
  margin-top: 4px;
  font-weight: bold;
  font-family: 'Consolas', monospace;
  letter-spacing: 1px;
}

@keyframes pulse-recording {
  0% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(255, 68, 68, 0.7);
  }
  70% {
    transform: scale(1.05);
    box-shadow: 0 0 0 10px rgba(255, 68, 68, 0);
  }
  100% {
    transform: scale(1);
    box-shadow: 0 0 0 0 rgba(255, 68, 68, 0);
  }
}
</style>
