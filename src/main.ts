import { createApp } from 'vue'
import { loader } from '@guolao/vue-monaco-editor'
import App from './App.vue'
import router from './router'
import './style.css'

// 配置 Monaco Editor 中文支持
loader.config({
  'vs/nls': {
    availableLanguages: {
      '*': 'zh-cn'
    }
  }
})

const app = createApp(App)

// 全局错误处理
app.config.errorHandler = (err: unknown, instance, info) => {
  const msg = err instanceof Error ? err.message : String(err)
  const stack = err instanceof Error ? err.stack?.split('\n').slice(0, 3).join('\n') : ''
  console.error('[Vue 错误]', err)
  console.error('[Vue 错误信息]', info)
  // 浏览器模式：在页面上显示错误便于调试
  if (!(window as any).electron) {
    const el = document.getElementById('vue-error-log') || (() => {
      const d = document.createElement('pre')
      d.id = 'vue-error-log'
      d.style.cssText = 'position:fixed;bottom:0;left:260px;right:0;max-height:150px;overflow:auto;background:#1a0000;color:#ff6b6b;font:11px monospace;padding:8px;z-index:99999;border-top:2px solid red'
      document.body.appendChild(d)
      return d
    })()
    el.textContent += `[${info}] ${msg}\n${stack}\n\n`
  }
}

app.use(router)
app.mount('#app')
