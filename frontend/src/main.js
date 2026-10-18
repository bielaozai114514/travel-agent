import { createApp } from 'vue' // 导入 Vue 核心函数：创建 App 实例
import './style.css' // 导入全局样式（空文件，后续可加全局样式）
import App from './App.vue' // 导入根组件 App.vue

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import pinia from './pinia' // 状态管理（存储全局数据，比如用户令牌）
import router from './router' // 路由（页面跳转）

const app = createApp(App) // 创建 App 实例（Vue 项目的核心对象）

// 注册 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

// 使用插件（把 UI 库、路由、状态管理挂载到 App 上）
app.use(ElementPlus)
app.use(pinia)
app.use(router)

// 挂载 App 到页面（把 App 组件渲染到 index.html 的 #app 元素中）
app.mount('#app')