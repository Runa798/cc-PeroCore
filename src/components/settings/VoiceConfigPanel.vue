<template>
  <div class="flex flex-col h-full max-w-7xl mx-auto p-6 overflow-hidden">
    <!-- 顶部头部区域 (增强质感) -->
    <div class="flex-none mb-6">
      <PCard
        glass
        soft3d
        overflow-visible
        class="!p-5 !px-8 rounded-[2rem] relative group/vtoolbar z-30"
      >
        <!-- 背景装饰 ✨ -->
        <div
          class="absolute -right-20 -top-20 w-40 h-40 bg-sky-400/5 blur-[60px] rounded-full pointer-events-none group-hover/vtoolbar:bg-sky-400/10 transition-all duration-1000"
        ></div>

        <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4 relative z-10">
          <div class="flex items-center gap-3">
            <div
              class="p-2.5 bg-sky-50 rounded-2xl text-sky-500 border border-sky-100 shadow-sm shadow-sky-200/20 group-hover/vtoolbar:scale-110 group-hover/vtoolbar:rotate-6 transition-all duration-500"
            >
              <PixelIcon name="mic" size="md" />
            </div>
            <div>
              <h2 class="text-lg font-bold text-slate-800 flex items-center gap-2">
                语音功能配置
                <span
                  class="text-[10px] font-normal text-slate-400 tracking-widest uppercase ml-1 opacity-40 group-hover/vtoolbar:opacity-80 transition-opacity"
                  ># Voice Config</span
                >
              </h2>
              <p class="text-[11px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                管理语音识别 (STT) 与语音合成 (TTS) 引擎
                <span class="group-hover/vtoolbar:animate-pulse">🎙️ 🐾</span>
              </p>
            </div>
          </div>

          <PButton
            variant="primary"
            size="sm"
            class="!rounded-xl shadow-md shadow-sky-400/10 hover:scale-105 active:scale-95 transition-all mb-0.5"
            @click="openEditor(null)"
          >
            <div class="flex items-center gap-1.5 px-1">
              <PixelIcon name="plus" size="xs" />
              <span>添加新配置</span>
            </div>
          </PButton>
        </div>
      </PCard>
    </div>

    <!-- 主要内容区域 -->
    <div class="flex-1 overflow-y-auto custom-scrollbar pr-2">
      <!-- Tabs (现代化设计) -->
      <div class="flex gap-2 p-1 bg-sky-100/30 rounded-2xl w-fit mb-8 border border-sky-100/50">
        <button
          class="flex items-center gap-2 px-6 py-2.5 text-sm font-bold transition-all duration-300 rounded-xl active:scale-95"
          :class="
            activeTab === 'stt'
              ? 'bg-white text-sky-600 shadow-sm shadow-sky-200/50 ring-1 ring-sky-200 soft-3d-shadow'
              : 'text-slate-500 hover:text-sky-500 hover:bg-white/50'
          "
          @click="activeTab = 'stt'"
        >
          <PixelIcon name="mic" size="sm" />
          <span>语音识别 (STT)</span>
        </button>
        <button
          class="flex items-center gap-2 px-6 py-2.5 text-sm font-bold transition-all duration-300 rounded-xl active:scale-95"
          :class="
            activeTab === 'tts'
              ? 'bg-white text-sky-600 shadow-sm shadow-sky-200/50 ring-1 ring-sky-200 soft-3d-shadow'
              : 'text-slate-500 hover:text-sky-500 hover:bg-white/50'
          "
          @click="activeTab = 'tts'"
        >
          <PixelIcon name="headphones" size="sm" />
          <span>语音合成 (TTS)</span>
        </button>
      </div>

      <!-- STT 内容 -->
      <div v-if="activeTab === 'stt'" class="space-y-6">
        <div
          v-if="sttConfigs.length === 0"
          class="flex flex-col items-center justify-center py-20 text-slate-400 bg-white/40 glass-effect rounded-[2.5rem] border border-sky-100 border-dashed soft-3d-shadow"
        >
          <div class="w-20 h-20 bg-sky-50 rounded-full flex items-center justify-center mb-6">
            <PixelIcon name="mic" size="xl" class="text-sky-300" />
          </div>
          <p class="mb-6 text-sm font-medium">暂无语音识别配置</p>
          <PButton variant="secondary" @click="openEditor(null)"> 立即添加 🐾 </PButton>
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          <PCard
            v-for="config in sttConfigs"
            :key="config.id"
            glass
            soft3d
            hoverable
            class="group/vcard !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden flex flex-col"
            :class="[
              config.is_active
                ? 'border-sky-300 bg-sky-50/50 ring-1 ring-sky-200'
                : 'border-sky-100/30 hover:shadow-sky-100/50'
            ]"
          >
            <!-- 背景装饰 ✨ -->
            <div
              class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-all duration-700 opacity-10 group-hover/vcard:opacity-30"
              :class="config.is_active ? 'bg-sky-400' : 'bg-sky-200'"
            ></div>

            <div class="flex-1 flex flex-col relative z-10">
              <div class="flex justify-between items-start mb-5">
                <div
                  class="w-14 h-14 rounded-2xl flex items-center justify-center text-white shadow-lg transition-transform duration-500 group-hover/vcard:scale-110 group-hover/vcard:rotate-6"
                  :class="
                    config.is_active
                      ? 'bg-gradient-to-br from-sky-400 to-sky-600 shadow-sky-200/50'
                      : 'bg-gradient-to-br from-slate-300 to-slate-400 shadow-slate-200/50 opacity-60'
                  "
                >
                  <PixelIcon name="mic" size="lg" />
                </div>
                <div
                  v-if="config.is_active"
                  class="flex items-center gap-1.5 px-3 py-1 bg-sky-500 text-white text-[10px] font-black uppercase tracking-widest rounded-full shadow-sm shadow-sky-200 soft-3d-shadow"
                >
                  <PixelIcon name="check" size="xs" />
                  <span>Active</span>
                </div>
              </div>

              <h3
                class="font-black text-slate-800 text-lg mb-2 truncate group-hover/vcard:text-sky-600 transition-colors"
                :title="config.name"
              >
                {{ config.name }}
              </h3>

              <div class="flex flex-wrap gap-2 mt-auto">
                <span
                  class="px-2.5 py-1 bg-white/60 text-slate-500 text-[10px] font-bold uppercase tracking-wider rounded-lg border border-sky-100/50"
                >
                  {{ config.provider }}
                </span>
                <span
                  v-if="config.model"
                  class="px-2.5 py-1 bg-sky-100/50 text-sky-600 text-[10px] font-bold uppercase tracking-wider rounded-lg border border-sky-100/50"
                >
                  {{ config.model }}
                </span>
              </div>
            </div>

            <div class="mt-6 pt-5 border-t border-sky-100/30 flex justify-between items-center">
              <PButton
                v-if="!config.is_active"
                size="sm"
                variant="ghost"
                class="!text-[10px] !font-black !px-4 hover:bg-sky-50"
                @click="activateConfig(config)"
              >
                启用 ENABLE
              </PButton>
              <div v-else></div>

              <div class="flex gap-2">
                <PTooltip content="编辑配置">
                  <button
                    class="p-2 text-slate-400 hover:text-sky-500 hover:bg-sky-50 rounded-xl transition-all active:scale-90"
                    @click="openEditor(config)"
                  >
                    <PixelIcon name="pencil" size="sm" />
                  </button>
                </PTooltip>
                <PTooltip content="删除配置">
                  <button
                    class="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-xl transition-all active:scale-90 disabled:opacity-30 disabled:cursor-not-allowed"
                    :disabled="config.is_active"
                    @click="deleteConfig(config)"
                  >
                    <PixelIcon name="trash" size="sm" />
                  </button>
                </PTooltip>
              </div>
            </div>
          </PCard>
        </div>
      </div>

      <!-- TTS 内容 -->
      <div v-if="activeTab === 'tts'" class="space-y-6">
        <!-- TTS Banner (增强质感) -->
        <PCard
          glass
          soft3d
          class="!p-6 flex items-center justify-between !rounded-[2.5rem] relative overflow-hidden group/tbanner border-sky-100/50"
          :class="{ 'opacity-80 grayscale-[0.5]': !ttsEnabled }"
        >
          <div
            class="absolute -right-20 -top-20 w-60 h-60 bg-sky-400/5 blur-[80px] rounded-full pointer-events-none transition-all duration-1000 group-hover/tbanner:bg-sky-400/10"
          ></div>

          <div class="flex items-center gap-6 relative z-10">
            <div
              class="w-16 h-16 rounded-full bg-gradient-to-br from-sky-400 to-sky-600 flex items-center justify-center text-white shadow-xl shadow-sky-200 transition-transform duration-500 group-hover/tbanner:scale-110 group-hover/tbanner:rotate-12"
            >
              <PixelIcon :name="ttsEnabled ? 'headphones' : 'volume-x'" size="xl" />
            </div>
            <div>
              <div class="text-xl font-black text-slate-800 mb-1 flex items-center gap-2">
                全局语音合成开关
                <span class="text-[10px] text-sky-400 font-mono tracking-widest uppercase"
                  ># Global TTS</span
                >
              </div>
              <div class="text-sm text-slate-500 flex items-center gap-1.5 font-medium">
                {{ ttsEnabled ? '当前已开启，助手将通过语音回复您' : '当前已关闭，助手将保持静默' }}
                <span v-if="ttsEnabled" class="animate-pulse">✨ 🔊</span>
              </div>
            </div>
          </div>

          <div
            class="flex items-center gap-3 px-4 py-2 bg-sky-50/50 rounded-2xl border border-sky-100 relative z-10"
          >
            <span class="text-xs font-black text-slate-400 uppercase tracking-widest">{{
              ttsEnabled ? 'ON' : 'OFF'
            }}</span>
            <PSwitch v-model="ttsEnabled" @update:model-value="toggleTTSMode" />
          </div>
        </PCard>

        <div
          v-if="ttsConfigs.length === 0"
          class="flex flex-col items-center justify-center py-20 text-slate-400 bg-white/40 glass-effect rounded-[2.5rem] border border-sky-100 border-dashed soft-3d-shadow"
        >
          <div class="w-20 h-20 bg-sky-50 rounded-full flex items-center justify-center mb-6">
            <PixelIcon name="headphones" size="xl" class="text-sky-300" />
          </div>
          <p class="mb-6 text-sm font-medium">暂无语音合成配置</p>
          <PButton variant="secondary" @click="openEditor(null)"> 立即添加 🐾 </PButton>
        </div>
        <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          <PCard
            v-for="config in ttsConfigs"
            :key="config.id"
            glass
            soft3d
            hoverable
            class="group/vcard !p-6 !rounded-[2rem] transition-all duration-500 overflow-hidden flex flex-col"
            :class="[
              config.is_active
                ? 'border-sky-300 bg-sky-50/50 ring-1 ring-sky-200'
                : 'border-sky-100/30 hover:shadow-sky-100/50'
            ]"
          >
            <!-- 背景装饰 ✨ -->
            <div
              class="absolute -right-10 -top-10 w-24 h-24 blur-[40px] rounded-full pointer-events-none transition-all duration-700 opacity-10 group-hover/vcard:opacity-30"
              :class="config.is_active ? 'bg-sky-400' : 'bg-sky-200'"
            ></div>

            <div class="flex-1 flex flex-col relative z-10">
              <div class="flex justify-between items-start mb-5">
                <div
                  class="w-14 h-14 rounded-2xl flex items-center justify-center text-white shadow-lg transition-transform duration-500 group-hover/vcard:scale-110 group-hover/vcard:rotate-6"
                  :class="
                    config.is_active
                      ? 'bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-emerald-200/50'
                      : 'bg-gradient-to-br from-slate-300 to-slate-400 shadow-slate-200/50 opacity-60'
                  "
                >
                  <PixelIcon name="headphones" size="lg" />
                </div>
                <div
                  v-if="config.is_active"
                  class="flex items-center gap-1.5 px-3 py-1 bg-emerald-500 text-white text-[10px] font-black uppercase tracking-widest rounded-full shadow-sm shadow-emerald-200 soft-3d-shadow"
                >
                  <PixelIcon name="check" size="xs" />
                  <span>Active</span>
                </div>
              </div>

              <h3
                class="font-black text-slate-800 text-lg mb-2 truncate group-hover/vcard:text-emerald-600 transition-colors"
                :title="config.name"
              >
                {{ config.name }}
              </h3>

              <div class="flex flex-wrap gap-2 mt-auto">
                <span
                  class="px-2.5 py-1 bg-white/60 text-slate-500 text-[10px] font-bold uppercase tracking-wider rounded-lg border border-sky-100/50"
                >
                  {{ config.provider }}
                </span>
                <span
                  v-if="config.model"
                  class="px-2.5 py-1 bg-amber-100/50 text-amber-600 text-[10px] font-bold uppercase tracking-wider rounded-lg border border-amber-100/50"
                >
                  {{ config.model }}
                </span>
              </div>
            </div>

            <div class="mt-6 pt-5 border-t border-sky-100/30 flex justify-between items-center">
              <PButton
                v-if="!config.is_active"
                size="sm"
                variant="ghost"
                class="!text-[10px] !font-black !px-4 hover:bg-sky-50"
                @click="activateConfig(config)"
              >
                启用 ENABLE
              </PButton>
              <div v-else></div>

              <div class="flex gap-2">
                <PTooltip content="编辑配置">
                  <button
                    class="p-2 text-slate-400 hover:text-sky-500 hover:bg-sky-50 rounded-xl transition-all active:scale-90"
                    @click="openEditor(config)"
                  >
                    <PixelIcon name="pencil" size="sm" />
                  </button>
                </PTooltip>
                <PTooltip content="删除配置">
                  <button
                    class="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-xl transition-all active:scale-90 disabled:opacity-30 disabled:cursor-not-allowed"
                    :disabled="config.is_active"
                    @click="deleteConfig(config)"
                  >
                    <PixelIcon name="trash" size="sm" />
                  </button>
                </PTooltip>
              </div>
            </div>
          </PCard>
        </div>
      </div>
    </div>

    <!-- 编辑器对话框 -->
    <PModal
      v-model="showEditor"
      :title="editingConfig.id ? '编辑配置' : '添加新配置'"
      width="600px"
      overflow-visible
    >
      <div class="space-y-6">
        <!-- 类型选择 -->
        <div class="space-y-3 relative z-40">
          <label
            class="text-xs font-black text-slate-400 uppercase tracking-widest flex items-center gap-2"
          >
            <PixelIcon name="layers" size="xs" />
            配置类型 TYPE
          </label>
          <div class="flex p-1 bg-slate-100/50 rounded-2xl w-full border border-slate-100">
            <button
              class="flex-1 flex items-center justify-center gap-2 py-3 text-sm font-bold transition-all duration-300 rounded-2xl"
              :class="
                editingConfig.type === 'stt'
                  ? 'bg-white text-sky-600 shadow-sm ring-1 ring-slate-200/50'
                  : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'
              "
              :disabled="!!editingConfig.id"
              @click="editingConfig.type = 'stt'"
            >
              <PixelIcon name="mic" size="sm" /> 语音识别 (STT)
            </button>
            <button
              class="flex-1 flex items-center justify-center gap-2 py-3 text-sm font-bold transition-all duration-300 rounded-2xl"
              :class="
                editingConfig.type === 'tts'
                  ? 'bg-white text-sky-600 shadow-sm ring-1 ring-slate-200/50'
                  : 'text-slate-400 hover:text-slate-600 hover:bg-white/50'
              "
              :disabled="!!editingConfig.id"
              @click="editingConfig.type = 'tts'"
            >
              <PixelIcon name="headphones" size="sm" /> 语音合成 (TTS)
            </button>
          </div>
        </div>

        <!-- 名称 -->
        <div class="relative z-30">
          <PInput
            v-model="editingConfig.name"
            label="配置名称 NAME"
            placeholder="给这个配置起个名字喵~ (例如: 我的本地模型)"
            icon="pencil"
          />
        </div>

        <!-- 服务商 -->
        <div class="relative z-20">
          <PSelect
            v-model="editingConfig.provider"
            label="服务提供商 PROVIDER"
            icon="server"
            class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
            :options="
              editingConfig.type === 'stt'
                ? [
                    { label: 'Local Whisper (本地)', value: 'local_whisper' },
                    { label: 'OpenAI Compatible (云端)', value: 'openai_compatible' }
                  ]
                : [
                    { label: 'Edge TTS (免费云端)', value: 'edge_tts' },
                    { label: 'OpenAI Compatible (云端)', value: 'openai_compatible' }
                  ]
            "
          />
        </div>

        <!-- OpenAI 兼容配置 -->
        <Transition
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="opacity-0 -translate-y-4"
          enter-to-class="opacity-100 translate-y-0"
        >
          <div
            v-if="editingConfig.provider === 'openai_compatible'"
            class="bg-sky-50/50 rounded-3xl p-6 border border-sky-100/50 space-y-5 relative z-10 overflow-hidden group/api"
          >
            <div
              class="absolute -right-10 -top-10 w-32 h-32 bg-sky-400/5 blur-3xl rounded-full pointer-events-none group-hover/api:bg-sky-400/10 transition-all duration-700"
            ></div>

            <h4
              class="text-xs font-black text-sky-600 uppercase tracking-widest flex items-center gap-2"
            >
              <PixelIcon name="settings" size="xs" />
              API 设置 API SETTINGS
            </h4>

            <PInput
              v-model="editingConfig.api_base"
              label="Base URL"
              placeholder="https://api.openai.com/v1"
              icon="link"
              variant="white"
            />

            <PInput
              v-model="editingConfig.api_key"
              label="API Key"
              type="password"
              placeholder="sk-..."
              icon="key"
              variant="white"
            />

            <div class="space-y-2">
              <div class="flex gap-3 items-end">
                <PInput
                  v-model="editingConfig.model"
                  label="Model ID"
                  placeholder="例如: whisper-1"
                  icon="cpu"
                  variant="white"
                  class="flex-1"
                />
                <PButton
                  size="sm"
                  variant="secondary"
                  class="!rounded-2xl h-[46px] px-6 shadow-sm border-slate-200"
                  :disabled="isFetchingRemote"
                  @click="fetchRemoteModels"
                >
                  <div class="flex items-center gap-2">
                    <PixelIcon
                      name="refresh"
                      size="xs"
                      :animation="isFetchingRemote ? 'spin' : ''"
                    />
                    <span>获取</span>
                  </div>
                </PButton>
              </div>

              <Transition
                enter-active-class="transition duration-200 ease-out"
                enter-from-class="opacity-0 scale-95"
                enter-to-class="opacity-100 scale-100"
              >
                <PSelect
                  v-if="remoteModels.length > 0"
                  v-model="editingConfig.model"
                  icon="list"
                  variant="white"
                  class="!rounded-2xl shadow-lg shadow-black/30 backdrop-blur-md"
                  :options="remoteModels.map((m) => ({ label: m, value: m }))"
                  placeholder="选择检测到的模型"
                />
              </Transition>
            </div>
          </div>
        </Transition>

        <!-- JSON 配置 -->
        <div class="space-y-3">
          <PTextarea
            v-model="editingConfig.config_json"
            label="高级参数 ADVANCED CONFIG (JSON)"
            icon="code"
            rows="4"
            placeholder="{}"
            class="font-mono text-xs"
          />
          <div
            class="flex items-start gap-2.5 p-3 bg-slate-50 rounded-2xl border border-slate-100 text-[10px] text-slate-400 leading-relaxed group/info"
          >
            <PixelIcon
              name="info"
              size="xs"
              class="mt-0.5 text-sky-400 group-hover/info:scale-110 transition-transform"
            />
            <div v-if="editingConfig.type === 'stt'">
              <span class="font-bold text-slate-500">示例:</span> {"device": "cpu", "compute_type":
              "int8"}
            </div>
            <div v-else>
              <span class="font-bold text-slate-500">示例:</span> {"voice": "zh-CN-XiaoyiNeural",
              "rate": "+15%"}
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <PButton variant="ghost" class="!rounded-2xl !px-6" @click="showEditor = false">
          取消 CANCEL
        </PButton>
        <PButton
          variant="primary"
          class="!rounded-2xl !px-8 shadow-lg shadow-sky-200"
          :disabled="isSaving"
          @click="saveConfig"
        >
          <div class="flex items-center gap-2">
            <div
              v-if="isSaving"
              class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"
            ></div>
            <span>{{ isSaving ? '保存中...' : '保存配置 SAVE' }}</span>
          </div>
        </PButton>
      </template>
    </PModal>

    <PModal v-model="deleteDialog.visible" title="确认删除喵？" width="400px">
      <div class="flex flex-col items-center text-center space-y-4 py-4 relative">
        <!-- 危险警告动画 ⚠️ -->
        <div class="relative group/trash">
          <div
            class="absolute inset-0 bg-rose-500/20 blur-2xl rounded-full scale-150 opacity-0 group-hover/trash:opacity-100 transition-opacity duration-700"
          ></div>
          <div
            class="w-20 h-20 bg-gradient-to-br from-rose-50 to-rose-100 rounded-[2rem] flex items-center justify-center text-rose-500 shadow-inner relative z-10 group-hover/trash:scale-110 group-hover/trash:-rotate-6 transition-all duration-500"
          >
            <PixelIcon name="trash" size="lg" />
          </div>
        </div>

        <div class="space-y-2">
          <p class="text-slate-700 font-black text-lg">确定要删除此语音配置吗喵？</p>
          <p class="text-xs text-slate-400 leading-relaxed px-4">
            此操作会将配置信息从本地持久化存储中移除，<br />
            <span class="text-rose-400 font-bold underline decoration-rose-200 underline-offset-4"
              >操作不可撤销</span
            >，请三思哦~ 🐾
          </p>
        </div>
      </div>
      <template #footer>
        <PButton variant="ghost" class="!rounded-2xl !px-6" @click="deleteDialog.visible = false">
          点错了喵
        </PButton>
        <PButton
          variant="primary"
          class="!bg-rose-500 hover:!bg-rose-600 !border-rose-500 shadow-lg shadow-rose-200 !rounded-2xl !px-8"
          @click="confirmDelete"
        >
          狠心删除 DELETE
        </PButton>
      </template>
    </PModal>

    <PModal v-model="alertDialog.visible" :title="alertDialog.title" width="420px">
      <div class="flex flex-col items-center text-center space-y-5 py-6">
        <div
          class="w-20 h-20 bg-gradient-to-br from-sky-50 to-sky-100 rounded-[2rem] flex items-center justify-center text-sky-500 shadow-inner group/info-icon"
        >
          <PixelIcon name="info" size="lg" class="group-hover/info-icon:animate-bounce" />
        </div>
        <div class="space-y-2 px-4">
          <h4 class="text-slate-800 font-black text-lg">{{ alertDialog.title || '系统提示' }}</h4>
          <p class="text-sm text-slate-500 font-medium leading-relaxed whitespace-pre-wrap">
            {{ alertDialog.message }}
          </p>
        </div>
      </div>
      <template #footer>
        <PButton
          variant="primary"
          class="w-full !rounded-2xl !py-3 shadow-lg shadow-sky-200"
          @click="alertDialog.visible = false"
        >
          知道啦喵~ GOT IT
        </PButton>
      </template>
    </PModal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PixelIcon from '../ui/PixelIcon.vue'
import PModal from '../ui/PModal.vue'
import PCard from '../ui/PCard.vue'
import PButton from '../ui/PButton.vue'
import PSwitch from '../ui/PSwitch.vue'
import PInput from '../ui/PInput.vue'
import PSelect from '../ui/PSelect.vue'
import PTextarea from '../ui/PTextarea.vue'
import PTooltip from '../ui/PTooltip.vue'

import { API_BASE } from '@/config'
const activeTab = ref('stt')
const configs = ref([])
const showEditor = ref(false)
const isSaving = ref(false)
const editingConfig = ref({})
const remoteModels = ref([])
const isFetchingRemote = ref(false)
const ttsEnabled = ref(true)

// 对话框状态
const deleteDialog = ref({ visible: false, config: null })
const alertDialog = ref({ visible: false, title: '', message: '' })

const showAlert = (title, message) => {
  alertDialog.value = { visible: true, title, message }
}

const sttConfigs = computed(() => configs.value.filter((c) => c.type === 'stt'))
const ttsConfigs = computed(() => configs.value.filter((c) => c.type === 'tts'))

const fetchTTSMode = async () => {
  try {
    const res = await fetch(`${API_BASE}/config/tts`)
    if (res.ok) {
      const data = await res.json()
      ttsEnabled.value = data.enabled
    }
  } catch (e) {
    console.error('获取 TTS 模式错误:', e)
  }
}

const toggleTTSMode = async (val) => {
  try {
    await fetch(`${API_BASE}/config/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: val })
    })
    // 成功不弹窗，失败弹窗
  } catch {
    showAlert('设置失败', '无法更新 TTS 模式设置')
    ttsEnabled.value = !val // 恢复原状
  }
}

const fetchConfigs = async () => {
  try {
    const res = await fetch(`${API_BASE}/voice-configs`)
    if (res.ok) {
      configs.value = await res.json()
    }
  } catch (e) {
    console.error('获取配置错误:', e)
  }
}

const fetchRemoteModels = async () => {
  try {
    if (!editingConfig.value.api_base) {
      showAlert('提示', '请先填写 Base URL')
      return
    }
    isFetchingRemote.value = true
    const res = await fetch(`${API_BASE}/models/remote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: editingConfig.value.api_key || '',
        api_base: editingConfig.value.api_base
      })
    })
    const data = await res.json()
    if (data.models && data.models.length > 0) {
      remoteModels.value = data.models
      // ElMessage.success(`成功获取 ${data.models.length} 个模型`)
    } else {
      showAlert('提示', '未能获取到模型列表，请检查配置')
    }
  } catch (e) {
    showAlert('错误', '获取模型失败: ' + e.message)
  } finally {
    isFetchingRemote.value = false
  }
}

const openEditor = (config) => {
  remoteModels.value = []
  if (config) {
    editingConfig.value = JSON.parse(JSON.stringify(config))
  } else {
    editingConfig.value = {
      type: activeTab.value,
      name: '',
      provider: activeTab.value === 'stt' ? 'local_whisper' : 'edge_tts',
      config_json: '{}',
      is_active: false
    }
  }
  showEditor.value = true
}

const saveConfig = async () => {
  try {
    isSaving.value = true
    // 验证 JSON
    try {
      JSON.parse(editingConfig.value.config_json || '{}')
    } catch {
      showAlert('错误', 'Config JSON 格式错误')
      return
    }

    const method = editingConfig.value.id ? 'PUT' : 'POST'
    const url = editingConfig.value.id
      ? `${API_BASE}/voice-configs/${editingConfig.value.id}`
      : `${API_BASE}/voice-configs`

    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editingConfig.value)
    })

    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || '保存失败')
    }

    await fetchConfigs()
    showEditor.value = false
  } catch (e) {
    showAlert('错误', e.message)
  } finally {
    isSaving.value = false
  }
}

const activateConfig = async (config) => {
  try {
    config.is_active = true
    const res = await fetch(`${API_BASE}/voice-configs/${config.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    if (!res.ok) throw new Error('切换失败')
    await fetchConfigs()
  } catch (e) {
    showAlert('错误', e.message)
  }
}

const deleteConfig = (config) => {
  deleteDialog.value = { visible: true, config }
}

const confirmDelete = async () => {
  const config = deleteDialog.value.config
  if (!config) return

  try {
    const res = await fetch(`${API_BASE}/voice-configs/${config.id}`, { method: 'DELETE' })
    if (!res.ok) throw new Error('删除失败')
    await fetchConfigs()
  } catch (e) {
    showAlert('错误', e.message)
  } finally {
    deleteDialog.value.visible = false
  }
}

onMounted(() => {
  fetchConfigs()
  fetchTTSMode()
})
</script>
