<template>
  <div class="relative h-full w-full overflow-hidden pixel-bg-moe pixel-ui pixel-grid-overlay">
    <CustomTitleBar v-if="isElectron()" title="Stronghold" :show-mode-toggle="false" />

    <!-- 环境光效果 -->
    <div class="absolute inset-0 pointer-events-none z-0 opacity-30">
      <div
        class="absolute top-0 left-1/4 w-96 h-96 bg-moe-pink/20 blur-[120px] rounded-full animate-pulse"
      ></div>
      <div
        class="absolute bottom-0 right-1/4 w-96 h-96 bg-moe-sky/20 blur-[120px] rounded-full animate-pulse"
        style="animation-delay: 1s"
      ></div>
    </div>

    <div
      :class="[
        'absolute inset-0 flex p-4 gap-4 z-10 transition-all duration-500',
        isElectron() ? 'top-8' : 'top-0'
      ]"
    >
      <!-- 左侧边栏：设施与房间 -->
      <aside
        class="w-72 flex flex-col bg-white/60 backdrop-blur-xl pixel-border-moe overflow-hidden shadow-2xl transition-all duration-300 hover:shadow-moe-pink/5"
      >
        <!-- 据点标题 -->
        <div class="p-5 border-b-2 border-moe-cocoa/5 bg-white/40 relative group">
          <div
            class="absolute top-0 left-0 w-1 h-full bg-moe-pink scale-y-0 group-hover:scale-y-100 transition-transform origin-top duration-300"
          ></div>
          <h2
            class="text-2xl font-black text-moe-cocoa flex items-center gap-3 tracking-tight font-moe"
          >
            <div class="p-2 bg-moe-pink/10 pixel-border-sm">
              <PixelIcon name="home" class="text-moe-pink animate-pixel-bounce" />
            </div>
            据点中心
          </h2>
          <div class="flex items-center gap-2 mt-2 ml-1">
            <span
              class="text-[9px] text-white bg-moe-cocoa px-2 py-0.5 font-black uppercase tracking-widest pixel-border-sm"
              >HQ-01</span
            >
            <span class="text-[10px] text-moe-cocoa/40 font-bold uppercase tracking-widest"
              >STRONGHOLD MGMT</span
            >
          </div>
        </div>

        <!-- 设施标签页 -->
        <div class="p-3 bg-moe-cocoa/5 border-b-2 border-moe-cocoa/5">
          <div class="flex gap-2 overflow-x-auto no-scrollbar pb-1">
            <button
              v-for="fac in facilities"
              :key="fac.id"
              class="flex-shrink-0 flex flex-col items-center justify-center w-16 h-16 transition-all pixel-border-moe group bouncy-hover"
              :class="
                currentFacility?.id === fac.id
                  ? 'bg-moe-pink text-white border-none shadow-lg shadow-moe-pink/20'
                  : 'bg-white/60 text-moe-cocoa/40 hover:bg-white/90 hover:text-moe-pink'
              "
              @click="selectFacility(fac)"
            >
              <PixelIcon :name="fac.icon || 'building'" size="sm" class="mb-1" />
              <span class="text-[9px] font-black truncate w-full px-1 text-center uppercase">{{
                fac.name
              }}</span>
            </button>
          </div>
        </div>

        <!-- 房间列表 -->
        <div class="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          <div class="flex items-center justify-between mb-4 px-1">
            <span
              class="text-[10px] font-black text-moe-cocoa/30 uppercase tracking-[0.2em] font-moe"
              >区域列表</span
            >
            <div class="h-[1px] flex-1 bg-moe-cocoa/10 ml-4"></div>
          </div>

          <div v-if="loading" class="py-12 flex flex-col items-center justify-center gap-4">
            <div class="relative">
              <div class="absolute inset-0 bg-moe-pink/20 blur-xl animate-pulse"></div>
              <PixelIcon
                name="loader"
                animation="spin"
                size="lg"
                class="text-moe-pink relative z-10"
              />
            </div>
            <span
              class="text-[10px] font-black text-moe-pink tracking-[0.3em] uppercase animate-pulse font-moe"
              >正在扫描据点...</span
            >
          </div>

          <template v-else>
            <div
              v-for="room in rooms"
              :key="room.id"
              class="relative group cursor-pointer transition-all duration-200 active:scale-[0.98]"
              @click="selectRoom(room)"
            >
              <div
                class="flex items-center gap-4 p-4 transition-all pixel-border-moe relative z-10"
                :class="
                  currentRoom?.id === room.id
                    ? 'bg-white shadow-lg -translate-y-1'
                    : 'bg-white/40 hover:bg-white/70 opacity-70 hover:opacity-100'
                "
              >
                <!-- 选择指示器 -->
                <div
                  v-if="currentRoom?.id === room.id"
                  class="absolute -left-1 top-4 bottom-4 w-1.5 bg-moe-pink shadow-[2px_0_8px_rgba(244,63,94,0.4)]"
                ></div>

                <div
                  class="p-2 transition-colors duration-300"
                  :class="currentRoom?.id === room.id ? 'text-moe-pink' : 'text-moe-cocoa/20'"
                >
                  <PixelIcon
                    :name="currentRoom?.id === room.id ? 'door-open' : 'door-closed'"
                    size="sm"
                  />
                </div>

                <div class="flex-1 min-w-0">
                  <div
                    class="font-black text-sm text-moe-cocoa truncate uppercase tracking-tight font-moe"
                  >
                    {{ room.name }}
                  </div>
                  <div
                    class="text-[9px] text-moe-cocoa/40 truncate font-bold mt-1 tracking-wider uppercase opacity-80"
                  >
                    {{ room.description || '据点环境探测中...' }}
                  </div>
                </div>

                <div v-if="currentRoom?.id === room.id" class="animate-pixel-bounce">
                  <PixelIcon name="sparkle" size="xs" class="text-moe-yellow" />
                </div>
              </div>

              <!-- 阴影层 -->
              <div
                v-if="currentRoom?.id === room.id"
                class="absolute inset-0 bg-moe-pink/10 blur-md -z-10"
              ></div>
            </div>
          </template>
        </div>
      </aside>

      <!-- 中间：聊天区域 -->
      <main
        class="flex-1 flex flex-col min-w-0 bg-white/40 backdrop-blur-xl relative pixel-border-moe overflow-hidden shadow-2xl group"
      >
        <!-- 角落装饰 -->
        <div
          class="absolute top-0 right-0 p-2 opacity-10 group-hover:opacity-30 transition-opacity pointer-events-none"
        >
          <PixelIcon name="sparkle" size="md" class="text-moe-pink" />
        </div>

        <div v-if="currentRoom" class="flex flex-col h-full relative z-10">
          <!-- 房间标题 -->
          <header
            class="bg-white/60 backdrop-blur-md border-b-2 border-moe-cocoa/5 px-8 py-5 flex justify-between items-center z-20 shadow-sm"
          >
            <div class="flex items-center gap-6">
              <div class="relative">
                <div
                  class="absolute inset-0 bg-moe-sky/20 blur-lg rounded-full animate-pulse"
                ></div>
                <div
                  class="w-12 h-12 bg-moe-sky text-white flex items-center justify-center pixel-border-moe relative z-10 shadow-lg shadow-moe-sky/20"
                >
                  <PixelIcon name="door-open" size="md" />
                </div>
              </div>
              <div>
                <h1
                  class="text-3xl font-black text-moe-cocoa flex items-center gap-4 tracking-tight font-moe"
                >
                  {{ currentRoom.name }}
                  <span
                    class="px-4 py-1 bg-moe-pink text-[10px] text-white font-black pixel-border-sm uppercase tracking-[0.2em] shadow-lg shadow-moe-pink/20"
                  >
                    {{ currentFacility?.name }}
                  </span>
                </h1>
                <p
                  class="text-[10px] text-moe-cocoa/40 font-black mt-2 uppercase tracking-[0.3em] flex items-center gap-2 opacity-80"
                >
                  <span class="w-2 h-2 bg-emerald-400 pixel-border-sm animate-pulse"></span>
                  据点通讯链路：已建立加密连接
                </p>
              </div>
            </div>

            <div class="flex items-center gap-4">
              <button
                class="w-10 h-10 flex items-center justify-center bg-white/80 text-moe-cocoa/30 hover:text-moe-pink transition-all pixel-border-moe bouncy-hover active:scale-90"
              >
                <PixelIcon name="settings" size="sm" />
              </button>
            </div>
          </header>

          <!-- 聊天界面容器 -->
          <div class="flex-1 relative p-4">
            <div class="absolute inset-0 bg-white/20 pointer-events-none"></div>
            <div
              class="h-full bg-white/40 backdrop-blur-sm pixel-border-moe overflow-hidden shadow-inner relative z-10"
            >
              <ChatInterface
                :key="currentRoom.id"
                mode="group"
                :target-id="currentRoom.id.toString()"
                :agent-name="currentRoom.name"
                :work-mode="false"
                class="h-full"
              />
            </div>
          </div>
        </div>

        <!-- 未选择房间状态 -->
        <div v-else class="flex flex-col items-center justify-center h-full relative z-10">
          <div class="relative mb-8 group/empty">
            <div
              class="absolute inset-0 bg-moe-pink/10 blur-[60px] group-hover/empty:blur-[80px] transition-all duration-1000"
            ></div>
            <div
              class="p-12 bg-white/60 pixel-border-moe animate-pixel-float relative z-10 shadow-2xl"
            >
              <PixelIcon
                name="building"
                size="3xl"
                class="text-moe-cocoa/10 group-hover/empty:text-moe-pink/20 transition-colors duration-700"
              />
            </div>
            <!-- 浮动闪光 -->
            <div
              class="absolute -top-4 -right-4 animate-pixel-bounce"
              style="animation-delay: 0.2s"
            >
              <PixelIcon name="sparkle" size="sm" class="text-moe-yellow/40" />
            </div>
            <div
              class="absolute -bottom-6 -left-4 animate-pixel-bounce"
              style="animation-delay: 0.5s"
            >
              <PixelIcon name="heart" size="sm" class="text-moe-pink/30" />
            </div>
          </div>
          <h3 class="text-3xl font-black text-moe-cocoa tracking-tight font-moe">
            请选择一个房间喵
          </h3>
          <p
            class="text-[10px] font-black mt-4 text-moe-cocoa/40 uppercase tracking-[0.4em] animate-pulse"
          >
            等待接入授权中...
          </p>
        </div>
      </main>

      <!-- 右侧边栏：房间信息与智能体 -->
      <aside
        class="w-80 bg-white/60 backdrop-blur-xl pixel-border-moe hidden xl:flex flex-col overflow-hidden shadow-2xl"
      >
        <!-- 顶部操作栏 -->
        <div
          class="p-5 border-b-2 border-moe-cocoa/5 bg-white/40 flex justify-between items-center relative group"
        >
          <div
            class="absolute bottom-0 left-0 h-0.5 bg-moe-yellow w-0 group-hover:w-full transition-all duration-500"
          ></div>
          <h3 class="font-black text-moe-cocoa/40 text-[10px] uppercase tracking-[0.3em] font-moe">
            系统监控中心
          </h3>
          <!-- 呼叫管家按钮 -->
          <button
            class="text-[10px] bg-moe-yellow text-white px-5 py-2.5 transition-all flex items-center gap-2 pixel-border-sm font-black bouncy-hover active:scale-95 shadow-lg shadow-moe-yellow/20 font-moe"
            @click="openButlerModal"
          >
            <PixelIcon name="bot" size="xs" />
            呼叫管家
          </button>
        </div>

        <!-- 房间环境 -->
        <div v-if="currentRoom" class="p-6 border-b-2 border-moe-cocoa/5 bg-moe-cocoa/[0.02]">
          <div class="flex items-center gap-3 mb-5">
            <div class="w-2 h-2 bg-moe-pink pixel-border-sm"></div>
            <h4 class="text-[10px] font-black text-moe-cocoa/60 uppercase tracking-widest font-moe">
              环境探测数据
            </h4>
          </div>
          <div
            class="bg-white/60 p-5 text-[10px] font-bold text-moe-cocoa/70 pixel-border-sm relative overflow-hidden group shadow-inner"
          >
            <!-- 扫描线效果 -->
            <div
              class="absolute inset-0 bg-gradient-to-b from-transparent via-moe-pink/[0.05] to-transparent h-2 w-full animate-[scanline_3s_linear_infinite] pointer-events-none"
            ></div>

            <div v-if="currentRoom.environment_json" class="space-y-3 relative z-10">
              <div
                v-for="(value, key) in JSON.parse(currentRoom.environment_json)"
                :key="key"
                class="flex justify-between items-center border-b border-moe-cocoa/5 pb-2 last:border-0"
              >
                <span class="text-moe-cocoa/40 uppercase tracking-tighter font-moe">{{ key }}</span>
                <span class="text-moe-pink font-black font-mono">{{ value }}</span>
              </div>
            </div>
            <div
              v-else
              class="text-moe-cocoa/20 text-center py-6 italic font-black uppercase tracking-widest font-moe"
            >
              无实时遥测数据喵
            </div>
          </div>
        </div>

        <!-- 智能体列表 -->
        <div class="flex-1 overflow-y-auto p-6 space-y-10 custom-scrollbar">
          <!-- 第一部分：本房间 -->
          <section>
            <div class="flex items-center justify-between mb-6">
              <h4
                class="text-[10px] font-black text-moe-cocoa/30 uppercase tracking-[0.2em] font-moe"
              >
                当前在线成员
              </h4>
              <span
                class="px-2 py-0.5 bg-green-400 text-white text-[8px] font-black pixel-border-sm animate-pulse"
                >LOCAL</span
              >
            </div>

            <div class="space-y-4">
              <template v-if="currentRoomAgents.length > 0">
                <div
                  v-for="agent in currentRoomAgents"
                  :key="agent.name"
                  class="flex items-center gap-4 p-3 bg-white/40 pixel-border-sm hover:bg-white transition-all duration-300 group hover:-translate-y-0.5 hover:shadow-lg hover:shadow-moe-pink/5"
                >
                  <div
                    class="w-12 h-12 bg-moe-pink text-white flex items-center justify-center pixel-border-sm group-hover:rotate-6 transition-transform shadow-lg shadow-moe-pink/10 overflow-hidden"
                  >
                    <img
                      v-if="agent.avatar"
                      :src="
                        agent.avatar.startsWith('/')
                          ? `${API_HOST}${agent.avatar}`
                          : agent.avatar
                      "
                      class="w-full h-full object-cover"
                      alt="Avatar"
                    />
                    <span v-else class="text-lg font-black font-moe">{{
                      agent.name[0].toUpperCase()
                    }}</span>
                  </div>
                  <div class="flex-1 min-w-0">
                    <div
                      class="text-xs font-black text-moe-cocoa uppercase tracking-tight truncate font-moe"
                    >
                      {{ agent.name }}
                    </div>
                    <div
                      class="text-[9px] text-green-500 font-black flex items-center gap-1.5 mt-1 uppercase tracking-tighter"
                    >
                      <span class="w-1.5 h-1.5 bg-green-500 animate-pulse pixel-border-sm"></span>
                      在此房间中
                    </div>
                  </div>
                </div>
              </template>
              <div
                v-else
                class="text-[10px] text-moe-cocoa/20 font-black uppercase tracking-widest py-8 text-center border-2 border-dashed border-moe-cocoa/10 pixel-border-sm font-moe"
              >
                目前没有探测到成员喵
              </div>
            </div>
          </section>

          <!-- 第二部分：据点全员 -->
          <section>
            <div class="flex items-center justify-between mb-6">
              <h4
                class="text-[10px] font-black text-moe-cocoa/30 uppercase tracking-[0.2em] font-moe"
              >
                据点成员名录
              </h4>
              <span class="px-2 py-0.5 bg-moe-sky text-white text-[8px] font-black pixel-border-sm"
                >REMOTE</span
              >
            </div>

            <div class="grid grid-cols-1 gap-3">
              <div
                v-for="agent in agentsStatus"
                :key="agent.name"
                class="flex items-center gap-3 p-3 bg-white/20 hover:bg-white/80 transition-all cursor-pointer pixel-border-sm group active:scale-95 hover:shadow-lg hover:shadow-moe-sky/5"
                @click="summonAgent(agent.name)"
              >
                <div
                  class="w-10 h-10 bg-moe-cocoa text-white flex items-center justify-center pixel-border-sm opacity-40 group-hover:opacity-100 transition-opacity overflow-hidden"
                >
                  <img
                    v-if="agent.avatar"
                    :src="
                      agent.avatar.startsWith('/')
                        ? `${API_HOST}${agent.avatar}`
                        : agent.avatar
                    "
                    class="w-full h-full object-cover"
                    alt="Avatar"
                  />
                  <span v-else class="text-sm font-black font-moe">{{
                    agent.name[0].toUpperCase()
                  }}</span>
                </div>
                <div class="flex-1 min-w-0">
                  <div
                    class="text-[10px] font-black text-moe-cocoa/60 group-hover:text-moe-pink transition-colors truncate uppercase font-moe"
                  >
                    {{ agent.name }}
                  </div>
                  <div
                    class="text-[8px] text-moe-cocoa/30 font-black flex items-center gap-1.5 mt-0.5 uppercase tracking-tighter"
                  >
                    <PixelIcon name="map-pin" size="xs" />
                    {{ agent.room_name }}
                  </div>
                </div>
                <PixelIcon
                  name="bot"
                  size="xs"
                  class="text-moe-pink opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </div>
            </div>
          </section>
        </div>

        <!-- 管家状态面板 -->
        <div
          class="p-6 bg-white/40 backdrop-blur-xl border-t-2 border-moe-cocoa/5 text-moe-cocoa relative overflow-hidden group"
        >
          <!-- 背景装饰 -->
          <div
            class="absolute -right-4 -bottom-4 opacity-5 group-hover:rotate-12 transition-transform duration-700 pointer-events-none"
          >
            <PixelIcon name="bot" size="3xl" />
          </div>

          <div class="flex items-center gap-3 mb-4 relative z-10">
            <div class="p-1.5 bg-moe-yellow/20 pixel-border-sm">
              <PixelIcon name="bot" size="xs" class="text-moe-yellow" />
            </div>
            <span
              class="text-[10px] font-black uppercase tracking-[0.2em] text-moe-cocoa/60 font-moe"
              >Butler System</span
            >
          </div>

          <div
            class="text-[10px] font-bold text-moe-cocoa/40 leading-relaxed mb-4 relative z-10 italic"
          >
            {{
              butlerConfig?.persona && !butlerConfig.persona.includes('persona.md')
                ? butlerConfig.persona
                : '据点管家系统已就绪，随时听候您的指令喵~'
            }}
          </div>

          <div
            class="flex items-center justify-between pt-4 border-t border-moe-cocoa/5 relative z-10"
          >
            <span class="text-[8px] font-black text-moe-cocoa/20 uppercase tracking-widest"
              >Core v4.2.0-moe</span
            >
            <div class="flex gap-1">
              <div class="w-1 h-1 bg-moe-yellow animate-pulse"></div>
              <div class="w-1 h-1 bg-moe-yellow animate-pulse" style="animation-delay: 0.2s"></div>
              <div class="w-1 h-1 bg-moe-yellow animate-pulse" style="animation-delay: 0.4s"></div>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- 呼叫管家弹窗 -->
    <transition name="modal">
      <div
        v-if="showButlerModal"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-moe-cocoa/40 backdrop-blur-md p-6"
        @click.self="showButlerModal = false"
      >
        <div
          class="bg-[#fffcf9] w-full max-w-lg shadow-[0_0_100px_rgba(45,27,30,0.3)] pixel-border-moe overflow-hidden animate-in"
        >
          <!-- 弹窗头部 -->
          <div
            class="p-8 border-b-2 border-moe-cocoa/5 bg-white relative flex justify-between items-center group"
          >
            <div class="absolute top-0 left-0 w-full h-1 bg-moe-yellow"></div>
            <div class="flex items-center gap-4">
              <div class="p-3 bg-moe-yellow/10 rounded-sm">
                <PixelIcon name="bot" size="md" class="text-moe-yellow animate-pixel-bounce" />
              </div>
              <div>
                <h3 class="text-2xl font-black text-moe-cocoa tracking-tighter">
                  BUTLER INTERFACE
                </h3>
                <p
                  class="text-[10px] text-moe-cocoa/30 font-black uppercase tracking-widest mt-0.5"
                >
                  据点智能管家指令终端
                </p>
              </div>
            </div>
            <button
              class="w-10 h-10 flex items-center justify-center text-moe-cocoa/20 hover:text-moe-pink transition-all bouncy-hover active:scale-90"
              @click="showButlerModal = false"
            >
              <PixelIcon name="close" size="sm" />
            </button>
          </div>

          <!-- 弹窗主体 -->
          <div class="p-10">
            <div class="relative group/input mb-8">
              <div class="absolute -top-3 left-4 px-2 bg-[#fffcf9] z-10">
                <span class="text-[10px] font-black text-moe-yellow uppercase tracking-widest"
                  >Input Directive</span
                >
              </div>
              <textarea
                v-model="butlerQuery"
                class="w-full h-48 bg-white/40 border-2 border-moe-cocoa/5 p-6 text-base font-bold focus:border-moe-yellow/30 resize-none placeholder-moe-cocoa/10 text-moe-cocoa focus:outline-none transition-all pixel-border-moe"
                placeholder="告诉管家你需要什么喵... 例如：&#10;“把客厅灯光调暗一点”&#10;“叫 Pero 过来”&#10;“建一个新房间叫‘书房’”"
                @keydown.enter.ctrl="submitButlerCall"
              ></textarea>
              <div
                class="absolute bottom-4 right-4 text-[9px] text-moe-cocoa/20 font-black tracking-widest pointer-events-none transition-opacity group-focus-within/input:opacity-0"
              >
                CTRL + ENTER TO SEND
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="flex justify-end gap-4">
              <button
                class="px-8 py-3 text-[10px] font-black text-moe-cocoa/40 hover:text-moe-cocoa/80 hover:bg-moe-cocoa/5 transition-all pixel-border-moe bouncy-hover active:scale-95 uppercase tracking-widest"
                @click="showButlerModal = false"
              >
                Abort
              </button>
              <button
                class="px-10 py-3 text-[10px] font-black bg-moe-yellow text-white shadow-xl shadow-moe-yellow/20 transition-all flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed pixel-border-moe bouncy-hover active:scale-95 uppercase tracking-widest"
                :disabled="!butlerQuery.trim() || callingButler"
                @click="submitButlerCall"
              >
                <PixelIcon v-if="callingButler" name="loader" size="xs" animation="spin" />
                <span v-else>Transmit Command</span>
              </button>
            </div>
          </div>

          <!-- 弹窗底部 -->
          <div class="px-8 py-4 bg-moe-cocoa/5 flex items-center gap-3">
            <div class="w-2 h-2 bg-moe-yellow rounded-full animate-pulse"></div>
            <span class="text-[9px] font-black text-moe-cocoa/20 uppercase tracking-[0.2em]"
              >Neural Link Established // Safe Mode Active</span
            >
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useStronghold } from '../composables/useStronghold'
import { isElectron } from '@/utils/ipcAdapter'
import { API_HOST } from '@/config'
import ChatInterface from '../components/chat/ChatInterface.vue'
import CustomTitleBar from '../components/layout/CustomTitleBar.vue'
import PixelIcon from '../components/ui/PixelIcon.vue'

const {
  facilities,
  rooms,
  currentRoom,
  currentFacility,
  butlerConfig,
  agentsStatus,
  loading,
  fetchFacilities,
  fetchRooms,
  selectFacility,
  selectRoom,
  fetchButler,
  fetchAgentsStatus,
  callButler
} = useStronghold()

// 管家弹窗
const showButlerModal = ref(false)
const butlerQuery = ref('')
const callingButler = ref(false)

const openButlerModal = () => {
  butlerQuery.value = ''
  showButlerModal.value = true
}

const submitButlerCall = async () => {
  if (!butlerQuery.value.trim()) return

  callingButler.value = true
  try {
    await callButler(butlerQuery.value)
    showButlerModal.value = false
    butlerQuery.value = ''

    // 管家操作后刷新房间列表和环境
    if (currentFacility.value) {
      await fetchRooms(currentFacility.value.id)
    }
    // 同时重新获取当前房间以获得更新的环境 json
    if (currentRoom.value) {
      // 小技巧：重新选择房间以刷新数据
      const updatedRoom = rooms.value.find((r) => r.id === currentRoom.value.id)
      if (updatedRoom) {
        selectRoom(updatedRoom)
      }
    }
  } catch (e) {
    console.error(e)
    // 错误处理（可能是 toast）
  } finally {
    callingButler.value = false
  }
}

// 辅助函数：通过文本快速召唤智能体
const summonAgent = (agentName) => {
  butlerQuery.value = `把 ${agentName} 叫到这里来`
  showButlerModal.value = true
}

// 计算属性：过滤当前房间中的智能体
const currentRoomAgents = computed(() => {
  if (!currentRoom.value || !agentsStatus.value) return []
  return agentsStatus.value.filter((a) => a.room_id === currentRoom.value.id)
})

// 定期轮询智能体状态
let pollTimer = null

onMounted(async () => {
  await fetchFacilities()
  await fetchButler()
  await fetchAgentsStatus()

  // 简单的状态更新轮询（每 5 秒）
  pollTimer = setInterval(fetchAgentsStatus, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
  }
})
</script>

<style scoped>
/* 萌系像素字体 🌸 */
.font-moe {
  font-family: 'ZCOOL KuaiLe', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* 自定义滚动条 - 适配萌动可可色 */
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(45, 27, 30, 0.1); /* 带透明度的萌可可色 */
  border-radius: 0;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: rgba(45, 27, 30, 0.2);
}

/* 隐藏滚动条但保留滚动功能 */
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* 简单的进场动画 */
@keyframes fadeInScale {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-in {
  animation: fadeInScale 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

/* 扫描线效果 */
@keyframes scanline {
  0% {
    transform: translateY(-100%);
  }
  100% {
    transform: translateY(1000%);
  }
}
</style>
