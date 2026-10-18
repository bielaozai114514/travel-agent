import axios from 'axios' // axios 发送 HTTP 请求的库
import { ElMessage } from 'element-plus' // 弹窗提示
import { getToken } from '@/utils/auth' // 导入令牌工具（获取/设置令牌）

// 创建 axios 实例
const service = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json;charset=utf-8'
  }
})

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 添加 Token
    if (getToken()) {
      config.headers.Authorization = `Bearer ${getToken()}`
    }
    return config
  },
  (error) => {
    console.error('请求错误：', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response) => { // 成功响应：直接返回数据
    const res = response.data
    // 统一处理返回结果
    if (res.success === false) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(res)
    }
    return res
  },
  (error) => { // 失败响应
    console.error('响应错误：', error)
    const status = error.response?.status
    const data = error.response?.data

    // 处理422参数验证错误
    if (status === 422 && data?.errors && Array.isArray(data.errors)) {
      // 构建详细的错误信息
      const errorMessages = data.errors.map(err => {
        const fieldName = getFieldDisplayName(err.field)
        return `${fieldName}: ${err.message}`
      })
      const errorMsg = errorMessages.join('\n')
      
      // 使用Element Plus的消息框显示详细错误
      ElMessage.error({
        message: errorMsg,
        dangerouslyUseHTMLString: false,
        duration: 5000,
        showClose: true
      })
    } else {
      // 其他错误使用原有的错误提示
      const errMsg = data?.detail || data?.message || error.message || '服务器错误'
      ElMessage.error(errMsg)
    }

    // 401 未授权，跳转到登录页
    if (status === 401) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 字段名称映射表（将英文字段名转换为中文显示）
const fieldNameMap = {
  'username': '用户名',
  'password': '密码',
  'email': '邮箱',
  'name': '名称',
  'description': '描述',
  'scope': '权限标识',
  'title': '标题',
  'content': '内容',
  'role': '角色',
  'user_id': '用户ID',
  'role_id': '角色ID',
  'permission_id': '权限ID'
}

// 获取字段的显示名称
function getFieldDisplayName(field) {
  // 移除body.前缀（如果有）
  const cleanField = field.replace(/^body\./, '')
  return fieldNameMap[cleanField] || cleanField
}

export default service