<template>
  <div>
    <div
      :class="[
        'flex items-center py-1.5 cursor-pointer whitespace-nowrap transition-all duration-200 pixel-border-sm-transparent mx-1',
        isSelected
          ? 'bg-moe-pink/10 text-moe-pink font-bold pixel-border-sm-moe'
          : 'text-slate-400 hover:bg-moe-sky/10 hover:text-slate-200 hover:pixel-border-sm-moe-light'
      ]"
      :style="{ paddingLeft: level * 12 + 8 + 'px' }"
      @click="toggle"
      @contextmenu.prevent.stop="$emit('contextmenu', { event: $event, item })"
    >
      <!-- 图标 -->
      <span v-if="item.type === 'directory'" class="mr-2 flex-shrink-0 opacity-90">
        <PixelIcon v-if="isOpen" name="folder-open" size="xs" class="text-moe-yellow" />
        <PixelIcon v-else name="folder" size="xs" class="text-moe-yellow/80" />
      </span>
      <span v-else class="mr-2 flex-shrink-0 opacity-90">
        <PixelIcon v-if="item.name.endsWith('.py')" name="code" size="xs" class="text-moe-sky" />
        <PixelIcon
          v-else-if="item.name.endsWith('.json')"
          name="file"
          size="xs"
          class="text-moe-yellow"
        />
        <PixelIcon
          v-else-if="item.name.endsWith('.md')"
          name="book"
          size="xs"
          class="text-moe-pink"
        />
        <PixelIcon v-else name="file" size="xs" class="text-slate-500" />
      </span>

      <!-- 名称 -->
      <span class="truncate text-xs">{{ item.name }}</span>
    </div>

    <!-- 子项 -->
    <div
      v-if="isOpen && item.type === 'directory'"
      class="mt-0.5 border-l-2 border-moe-pink/10 ml-3 pl-1"
    >
      <div v-if="loading" class="pl-4 py-1 text-[10px] text-moe-pink animate-pulse">扫描中...</div>
      <FileTreeItem
        v-for="child in children"
        :key="child.path"
        :item="child"
        :level="level + 1"
        @select="$emit('select', $event)"
        @contextmenu="$emit('contextmenu', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import PixelIcon from '../ui/PixelIcon.vue'
import { API_BASE } from '@/config'

const props = defineProps({
  item: { type: Object, default: () => ({}) },
  level: { type: Number, default: 0 }
})
// ... 其余脚本保持不变，但需要检查导入

const emit = defineEmits(['select', 'contextmenu'])

const isOpen = ref(false)
const children = ref([])
const loading = ref(false)
const isSelected = ref(false) // TODO: 与父级同步

const toggle = async () => {
  if (props.item.type === 'directory') {
    if (!isOpen.value && children.value.length === 0) {
      loading.value = true
      try {
        const res = await fetch(
          `${API_BASE}/ide/files?path=${encodeURIComponent(props.item.path)}`
        )
        if (res.ok) {
          children.value = await res.json()
        }
      } catch (e) {
        console.error('加载目录失败', e)
      } finally {
        loading.value = false
      }
    }
    isOpen.value = !isOpen.value
  } else {
    emit('select', props.item)
  }
}
</script>
