import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/pinia/userStore'
import { getToken } from '@/utils/auth'

// 基础布局组件（同步加载）
import Login from '@/views/login/Login.vue'
import Register from '@/views/login/Register.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import ChatLayout from '@/layouts/ChatLayout.vue'
import ChatView from '@/views/travel/chat/ChatView.vue'
import TripLayout from '@/layouts/TripLayout.vue'

// 路由规则
const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { title: '注册', requiresAuth: false }
  },
  // 旅游规划路由（用户入口）
  {
    path: '/',
    name: 'TripLayout',
    component: TripLayout,
    meta: { title: '旅游助手', requiresAuth: true, role: 'user' },
    redirect: '/trip',
    children: [
      {
        path: '/trip',
        name: 'TripHome',
        component: () => import('@/views/travel/trip/TripHome.vue'),
        meta: { title: '旅游助手', requiresAuth: true, role: 'user' }
      },
      {
        path: '/trip/result',
        name: 'TripResult',
        component: () => import('@/views/travel/trip/TripResult.vue'),
        meta: { title: '规划结果', requiresAuth: true, role: 'user' }
      },
      {
        path: '/trip/result/:id',
        name: 'TripResultWithId',
        component: () => import('@/views/travel/trip/TripResult.vue'),
        meta: { title: '规划详情', requiresAuth: true, role: 'user' }
      },
      {
        path: '/chat',
        name: 'Chat',
        component: ChatView,
        meta: { title: '对话', requiresAuth: true, role: 'user' }
      },
      {
        path: '/chat/:conversationId',
        name: 'ChatWithId',
        component: ChatView,
        meta: { title: '对话', requiresAuth: true, role: 'user' }
      },
      {
        path: '/guides',
        name: 'GuideList',
        component: () => import('@/views/travel/guide/GuideList.vue'),
        meta: { title: '旅游攻略', requiresAuth: true, role: 'user', scope: 'guides:read' }
      },
      {
        path: '/guide/create',
        name: 'GuideCreate',
        component: () => import('@/views/travel/guide/GuideEditor.vue'),
        meta: { title: '发布攻略', requiresAuth: true, role: 'user', scope: 'guides:write' }
      },
      {
        path: '/guide/edit/:id',
        name: 'GuideEdit',
        component: () => import('@/views/travel/guide/GuideEditor.vue'),
        meta: { title: '编辑攻略', requiresAuth: true, role: 'user', scope: 'guides:write' }
      },
      {
        path: '/guide/:id',
        name: 'GuideDetail',
        component: () => import('@/views/travel/guide/GuideDetail.vue'),
        meta: { title: '攻略详情', requiresAuth: true, role: 'user', scope: 'guides:read' }
      }
    ]
  },
  // 管理后台路由（管理员入口）
  {
    path: '/admin',
    name: 'AdminLayout',
    component: MainLayout,
    meta: { title: '管理后台', requiresAuth: true, role: 'admin' },
    redirect: '/admin/users',
    children: [
      {
        path: '/admin/users',
        name: 'UserList',
        component: () => import('@/views/admin/user/UserList.vue'),
        meta: { title: '用户管理', requiresAuth: true, role: 'admin', scope: 'users:read' }
      },
      {
        path: '/admin/roles',
        name: 'RoleList',
        component: () => import('@/views/admin/role/RoleList.vue'),
        meta: { title: '角色管理', requiresAuth: true, role: 'admin', scope: 'roles:read' }
      },
      {
        path: '/admin/permissions',
        name: 'PermissionList',
        component: () => import('@/views/admin/permission/PermissionList.vue'),
        meta: { title: '权限管理', requiresAuth: true, role: 'admin', scope: 'permissions:read' }
      },
      {
        path: '/admin/guides',
        name: 'AdminGuideList',
        component: () => import('@/views/admin/guide/GuideList.vue'),
        meta: { title: '攻略管理', requiresAuth: true, role: 'admin', scope: 'guides:admin' }
      },
      {
        path: '/admin/traces',
        name: 'AdminTraceList',
        component: () => import('@/views/admin/trace/TraceList.vue'),
        meta: { title: 'Trace 追踪', requiresAuth: true, role: 'admin' }
      },
      {
        path: '/admin/logs',
        name: 'AdminLogViewer',
        component: () => import('@/views/admin/log/LogViewer.vue'),
        meta: { title: '日志查看', requiresAuth: true, role: 'admin' }
      }
    ]
  },
  // 捕获所有未匹配路由
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 旅游助手`
  }

  // 不需要认证的路由
  if (!to.meta.requiresAuth) {
    next()
    return
  }

  // 检查token
  const token = getToken()
  if (!token) {
    next('/login')
    return
  }

  // 获取用户store
  const userStore = useUserStore()
  
  // 如果用户信息未加载，先获取用户信息
  if (!userStore.userInfo.id) {
    try {
      await userStore.fetchUserInfo()
    } catch (error) {
      // 获取用户信息失败，清除token并跳转到登录
      userStore.logout()
      next('/login')
      return
    }
  }

  // 检查角色权限
  const requiredRole = to.meta.role
  const userRoles = userStore.userInfo.roles || []
  const isAdmin = userRoles.some(role => role.name === 'admin')
  
  // 如果是管理员，可以访问所有页面
  if (isAdmin) {
    // 检查具体权限scope
    if (to.meta.scope && !userStore.hasPermission(to.meta.scope)) {
      next('/admin')
      return
    }
    next()
    return
  }

  // 普通用户只能访问user角色的页面
  if (requiredRole === 'admin') {
    // 普通用户尝试访问管理后台，重定向到对话页面
    next('/chat')
    return
  }

  // 检查具体权限scope
  if (to.meta.scope && !userStore.hasPermission(to.meta.scope)) {
    next('/')
    return
  }

  next()
})

export default router
