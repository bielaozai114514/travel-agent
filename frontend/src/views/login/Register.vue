<template>
  <div class="login-container">
    <div class="login-card">
      <!-- Logo区域 -->
      <div class="login-header">
        <div class="logo-wrapper">
          <el-icon size="40" class="logo-icon"><Setting /></el-icon>
        </div>
        <h2 class="login-title">旅游助手</h2>
        <p class="login-subtitle">欢迎注册，创建您的账号</p>
      </div>
      
      <!-- 注册表单 -->
      <el-form
        ref="registerFormRef"
        :model="registerForm"
        :rules="registerRules"
        class="login-form"
        size="large"
      >
        <el-form-item prop="username">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            clearable
            class="custom-input"
          />
        </el-form-item>
        <el-form-item prop="email">
          <el-input
            v-model="registerForm.email"
            placeholder="请输入邮箱"
            :prefix-icon="Message"
            clearable
            class="custom-input"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            clearable
            show-password
            class="custom-input"
          />
        </el-form-item>
        <el-form-item prop="confirmPassword">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请确认密码"
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
            @click="handleRegister"
            :loading="loading"
          >
            <el-icon class="btn-icon" v-if="!loading"><Check /></el-icon>
            <span>注 册</span>
          </el-button>
        </el-form-item>
      </el-form>
      
      <!-- 底部信息 -->
      <div class="login-footer">
        <p class="footer-text">已有账号？<a href="/login" class="register-link">去登录</a></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { User, Lock, Setting, Check, Message } from '@element-plus/icons-vue'
import { addUser } from '@/api/user'

// 路由
const router = useRouter()

// 加载状态
const loading = ref(false)
// 表单引用
const registerFormRef = ref(null)

// 注册表单
const registerForm = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

// 表单校验规则
const registerRules = reactive({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在3-20之间', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        const hasLetter = /[a-zA-Z]/.test(value)
        const hasNumber = /[0-9]/.test(value)
        if (!hasLetter || !hasNumber) {
          callback(new Error('密码必须同时包含字母和数字'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
})

/**
 * 处理注册
 */
const handleRegister = async () => {
  try {
    // 表单校验
    const valid = await registerFormRef.value.validate()
    if (!valid) return

    loading.value = true
    
    // 调用注册接口
    await addUser({
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password
    })

    ElMessage.success('注册成功，请登录')
    
    // 跳转到登录页面
    router.push('/login')
  } catch (error) {
    console.error('注册失败：', error)
    ElMessage.error('注册失败，请稍后重试')
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