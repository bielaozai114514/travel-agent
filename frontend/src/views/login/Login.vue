<template>
  <div class="login-container">
    <div class="login-card">
      <!-- Logo区域 -->
      <div class="login-header">
        <div class="logo-wrapper">
          <el-icon size="40" class="logo-icon"><Setting /></el-icon>
        </div>
        <h2 class="login-title">旅游助手</h2>
        <p class="login-subtitle">欢迎回来，请登录您的账号</p>
      </div>
      
      <!-- 登录表单 -->
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        size="large"
      >
        <el-form-item prop="email">
          <el-input
            v-model="loginForm.email"
            placeholder="请输入邮箱"
            :prefix-icon="User"
            clearable
            class="custom-input"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            clearable
            show-password
            class="custom-input"
          />
        </el-form-item>
        <el-form-item class="login-btn-group">
          <el-button
            type="primary"
            class="login-btn"
            @click="handleLogin"
            :loading="loading"
          >
            <el-icon class="btn-icon" v-if="!loading"><Right /></el-icon>
            <span>登 录</span>
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 底部信息 -->
      <div class="login-footer">
        <p class="footer-text">还没有账号？<a href="/register" class="register-link">去注册</a></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/pinia/userStore'
import { User, Lock, Setting, Right } from '@element-plus/icons-vue'

// 路由
const router = useRouter()
// 用户状态
const userStore = useUserStore()

// 加载状态
const loading = ref(false)
// 表单引用
const loginFormRef = ref(null)

// 登录表单
const loginForm = reactive({
  email: '',
  password: ''
})

// 表单校验规则
const loginRules = reactive({
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
})

/**
 * 处理登录
 */
const handleLogin = async () => {
  try {
    // 表单校验
    const valid = await loginFormRef.value.validate()
    if (!valid) return

    loading.value = true
    
    // 调用登录接口
    await userStore.login({
      email: loginForm.email,
      password: loginForm.password
    })

    // 获取用户信息以判断角色
    await userStore.fetchUserInfo()
    
    const userRoles = userStore.userInfo.roles || []
    const isAdmin = userRoles.some(role => role.name === 'admin')

    ElMessage.success('登录成功')
    
    // 根据角色跳转到不同页面
    if (isAdmin) {
      router.push('/admin')
    } else {
      router.push('/chat')
    }
  } catch (error) {
    console.error('登录失败：', error)
    ElMessage.error('登录失败，请检查邮箱或密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  width: 100%;
  height: 100vh;
  background: #f5f7fa;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
}

/* 登录卡片 */
.login-card {
  width: 420px;
  padding: 40px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  position: relative;
}

/* 登录头部 */
.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.logo-wrapper {
  width: 80px;
  height: 80px;
  background: #409eff;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 20px;
}

.logo-icon {
  color: #fff;
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px 0;
  letter-spacing: 1px;
}

.login-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

/* 登录表单 */
.login-form {
  margin-top: 24px;
}

:deep(.custom-input .el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  padding: 4px 15px;
  border: 1px solid #dcdfe6;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

:deep(.custom-input .el-input__wrapper:hover) {
  border-color: #c0c4cc;
}

:deep(.custom-input .el-input__wrapper.is-focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

:deep(.custom-input .el-input__inner) {
  height: 44px;
  font-size: 14px;
}

:deep(.custom-input .el-input__icon) {
  color: #909399;
  font-size: 16px;
}

.login-btn-group {
  margin-top: 32px;
  margin-bottom: 0;
}

.login-btn {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 2px;
  background: #409eff;
  border: none;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-btn:hover {
  background: #66b1ff;
}

.login-btn:active {
  background: #337ecc;
}

.btn-icon {
  font-size: 18px;
}

/* 登录底部 */
.login-footer {
  margin-top: 32px;
  text-align: center;
}

.footer-text {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.register-link {
  color: #409eff;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.register-link:hover {
  color: #66b1ff;
  text-decoration: underline;
}
</style>
