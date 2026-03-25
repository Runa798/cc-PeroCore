<template>
  <div
    class="h-full flex flex-col text-slate-400 select-none bg-transparent"
    @click="closeContextMenu"
  >
    <!-- 工具栏与搜索 -->
    <div class="flex flex-col border-b border-moe-pink/20 bg-moe-pink/5">
      <!-- 操作按钮 -->
      <div class="px-3 py-2 flex justify-end items-center gap-1">
        <button
          class="p-1.5 hover:bg-moe-pink/10 pixel-border-sm-transparent hover:pixel-border-sm-moe text-slate-500 hover:text-moe-pink transition-all"
          title="新建文件"
          @click.stop="createFile(null)"
        >
          <PixelIcon name="plus" size="xs" />
        </button>
        <button
          class="p-1.5 hover:bg-moe-pink/10 pixel-border-sm-transparent hover:pixel-border-sm-moe text-slate-500 hover:text-moe-pink transition-all"
          title="新建文件夹"
          @click.stop="createFolder(null)"
        >
          <PixelIcon name="folder-plus" size="xs" />
        </button>
        <button
          class="p-1.5 hover:bg-moe-pink/10 pixel-border-sm-transparent hover:pixel-border-sm-moe text-slate-500 hover:text-moe-pink transition-all"
          title="刷新"
          @click.stop="refresh"
        >
          <PixelIcon name="refresh" size="xs" />
        </button>
      </div>

      <!-- 搜索输入框 -->
      <div class="px-3 pb-2">
        <div class="relative group">
          <PixelIcon
            name="search"
            size="xs"
            class="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-moe-pink transition-colors"
          />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索文件..."
            class="w-full bg-white/10 pixel-border-sm-dark py-1.5 pl-8 pr-2 text-xs text-slate-300 placeholder-slate-600 focus:outline-none focus:border-moe-pink/50 focus:bg-black/20 transition-all"
          />
        </div>
      </div>
    </div>

    <!-- 文件树 -->
    <div
      class="flex-1 overflow-y-auto custom-scrollbar px-2 py-2"
      @contextmenu.prevent="handleRootContextMenu"
    >
      <div
        v-if="loading"
        class="flex flex-col items-center justify-center h-20 gap-2 text-slate-600"
      >
        <PixelIcon name="refresh" size="sm" animation="spin" class="text-moe-pink" />
        <span class="text-xs font-bold pixel-font">加载中...</span>
      </div>
      <div
        v-else-if="filteredFiles.length === 0"
        class="flex flex-col items-center justify-center h-20 text-slate-600"
      >
        <span v-if="searchQuery" class="text-xs italic">无搜索结果</span>
        <span v-else class="text-xs italic">工作区为空</span>
      </div>
      <div
        v-else
        class="pb-4 min-h-full space-y-0.5"
        @contextmenu.prevent.stop="handleRootContextMenu"
      >
        <FileTreeItem
          v-for="item in filteredFiles"
          :key="item.path"
          :item="item"
          @select="onSelect"
          @contextmenu="handleItemContextMenu"
        />
      </div>
    </div>

    <!-- 上下文菜单 -->
    <ContextMenu
      :visible="contextMenu.visible"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :items="contextMenu.items"
      @close="closeContextMenu"
    />

    <CustomDialog
      v-model:visible="dialog.visible"
      :type="dialog.type"
      :title="dialog.title"
      :message="dialog.message"
      :default-value="dialog.defaultValue"
      :placeholder="dialog.placeholder"
      @confirm="handleDialogConfirm"
      @cancel="handleDialogCancel"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import PixelIcon from '../ui/PixelIcon.vue'
import FileTreeItem from './FileTreeItem.vue'
import ContextMenu from '../ui/ContextMenu.vue'
import CustomDialog from '../ui/CustomDialog.vue'

const emit = defineEmits(['file-selected'])
const files = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')

// 递归搜索函数
const filterTree = (nodes, query) => {
  if (!query) return nodes

  const lowerQuery = query.toLowerCase()

  return nodes.reduce((acc, node) => {
    // 检查当前节点是否匹配
    const matches = node.name.toLowerCase().includes(lowerQuery)

    // 如果是目录，检查子节点
    if (node.type === 'directory' && node.children) {
      const filteredChildren = filterTree(node.children, query)

      // 如果匹配或包含匹配的子节点，则包含该节点
      if (matches || filteredChildren.length > 0) {
        acc.push({
          ...node,
          // 如果节点匹配，保留所有子节点（可选，但通常过滤它们更好，除非"已展开"）
          // 这里我们选择严格过滤子节点以帮助查找特定文件
          children: filteredChildren
        })
      }
    } else if (matches) {
      // 如果是文件且匹配，则包含它
      acc.push(node)
    }

    return acc
  }, [])
}

const filteredFiles = computed(() => {
  return filterTree(files.value, searchQuery.value)
})

const contextMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  items: [],
  targetItem: null
})

// 对话框状态
const dialog = reactive({
  visible: false,
  type: 'alert',
  title: '',
  message: '',
  defaultValue: '',
  placeholder: '',
  resolve: null
})

const showDialog = ({ type, title, message, defaultValue = '', placeholder = '' }) => {
  return new Promise((resolve) => {
    dialog.type = type
    dialog.title = title
    dialog.message = message
    dialog.defaultValue = defaultValue
    dialog.placeholder = placeholder
    dialog.resolve = resolve
    dialog.visible = true
  })
}

const handleDialogConfirm = (value) => {
  if (dialog.resolve) {
    if (dialog.type === 'prompt') dialog.resolve(value)
    else dialog.resolve(true)
  }
  dialog.visible = false
}

const handleDialogCancel = () => {
  if (dialog.resolve) dialog.resolve(false) // false 表示确认取消，null/false 表示 prompt 取消
  dialog.visible = false
}

import { API_BASE as _API_BASE } from '@/config'
const API_BASE = `${_API_BASE}/ide`

const fetchFiles = async (path = null) => {
  try {
    const url = path ? `${API_BASE}/files?path=${encodeURIComponent(path)}` : `${API_BASE}/files`
    const res = await fetch(url)
    
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}))
      throw new Error(errData.detail || '无法获取文件列表')
    }
    
    return await res.json()
  } catch (e) {
    console.error('[FileExplorer] 获取文件列表失败:', e)
    throw e
  }
}

const refresh = async () => {
  loading.value = true
  error.value = null
  try {
    files.value = await fetchFiles()
  } catch (e) {
    error.value = e.message
    if (window.$notify) {
      window.$notify(e.message, 'error', '资源管理器异常')
    }
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

const onSelect = (fileNode) => {
  emit('file-selected', fileNode)
}

// --- 上下文菜单逻辑 ---

const closeContextMenu = () => {
  contextMenu.visible = false
}

const handleRootContextMenu = (e) => {
  contextMenu.x = e.clientX
  contextMenu.y = e.clientY
  contextMenu.targetItem = null // Root
  contextMenu.items = [
    { label: '新建文件', action: () => createFile(null) },
    { label: '新建文件夹', action: () => createFolder(null) },
    { type: 'separator' },
    { label: '刷新', action: refresh }
  ]
  contextMenu.visible = true
}

const handleItemContextMenu = (payload) => {
  // 处理来自 FileTreeItem 发出的 payload 格式
  const event = payload.event || payload
  const item = payload.item

  if (!event || !event.clientX) {
    console.error('无效的上下文菜单事件', payload)
    return
  }

  // 项目类型的安全检查
  const isDir = item && item.type === 'directory'

  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.targetItem = item

  contextMenu.items = [
    { label: '打开', action: () => onSelect(item), disabled: isDir },
    { type: 'separator' },
    { label: '新建文件', action: () => createFile(item), disabled: !isDir },
    { label: '新建文件夹', action: () => createFolder(item), disabled: !isDir },
    { type: 'separator' },
    { label: '重命名', action: () => renameItem(item) },
    { label: '删除', action: () => deleteItem(item) }
  ]
  contextMenu.visible = true
}

// --- 操作 ---

const createFile = async (parentItem) => {
  const name = await showDialog({
    type: 'prompt',
    title: '新建文件',
    placeholder: '请输入文件名',
    message: '请输入文件名:'
  })

  if (!name) return

  const parentPath = parentItem ? parentItem.path : ''
  const path = parentPath ? `${parentPath}/${name}` : name

  try {
    await fetch(`${API_BASE}/file/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, is_directory: false })
    })
    refresh()
  } catch (e) {
    showDialog({ type: 'alert', title: '错误', message: '创建文件失败: ' + e.message })
  }
}

const createFolder = async (parentItem) => {
  const name = await showDialog({
    type: 'prompt',
    title: '新建文件夹',
    placeholder: '请输入文件夹名',
    message: '请输入文件夹名:'
  })

  if (!name) return

  const parentPath = parentItem ? parentItem.path : ''
  const path = parentPath ? `${parentPath}/${name}` : name

  try {
    await fetch(`${API_BASE}/file/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, is_directory: true })
    })
    refresh()
  } catch (e) {
    showDialog({ type: 'alert', title: '错误', message: '创建文件夹失败: ' + e.message })
  }
}

const renameItem = async (item) => {
  const newName = await showDialog({
    type: 'prompt',
    title: '重命名',
    defaultValue: item.name,
    message: '请输入新名称:'
  })

  if (!newName || newName === item.name) return

  try {
    await fetch(`${API_BASE}/file/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: item.path, new_name: newName })
    })
    refresh()
  } catch (e) {
    showDialog({ type: 'alert', title: '错误', message: '重命名失败: ' + e.message })
  }
}

const deleteItem = async (item) => {
  const confirmed = await showDialog({
    type: 'confirm',
    title: '删除确认',
    message: `您确定要删除 '${item.name}' 吗？`
  })

  if (!confirmed) return

  try {
    await fetch(`${API_BASE}/file/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: item.path })
    })
    refresh()
  } catch (e) {
    showDialog({ type: 'alert', title: '错误', message: '删除失败: ' + e.message })
  }
}
</script>
