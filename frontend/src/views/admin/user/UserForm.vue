<template>
  <el-form
    ref="formRef"
    :model="form"
    :rules="rules"
    label-width="100px"
    size="default"
  >
    <el-form-item label="用户名" prop="username">
      <el-input v-model="form.username" placeholder="请输入用户名" />
    </el-form-item>
    <el-form-item label="邮箱" prop="email">
      <el-input v-model="form.email" placeholder="请输入邮箱" />
    </el-form-item>
    <el-form-item label="密码" v-if="!isEdit">
      <el-input
        v-model="form.password"
        type="password"
        placeholder="请输入密码"
      />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="handleSubmit">提交</el-button>
      <el-button @click="handleReset">重置</el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

// 接收父组件传值
// 作用：父组件（UserList.vue）通过 :user-info="currentUser" 传值给子组件
// 比如编辑用户时，父组件把选中的用户数据传给子组件，子组件填充到表单里
const props = defineProps({
  userInfo: { // 定义接收的参数：userInfo（用户信息）
    type: Object,  // 参数类型：对象
    default: () => ({}) // 默认值：空对象（避免 undefined）
  }
})

// 暴露方法给父组件
// 作用：子组件通过 emit('submit', 数据) 把表单数据传给父组件
// 比如提交表单时，子组件把 form 数据传给父组件，父组件调用后端接口新增/编辑用户
const emit = defineEmits(['submit'])

// 表单引用
const formRef = ref(null)

// 判断是否为编辑模式
// - false：新增模式（默认）→ 显示密码框
// - true：编辑模式 → 隐藏密码框
// 响应式变量：值变 → 模板里的 v-if="!isEdit" 自动更新
const isEdit = ref(false)

// 表单数据
const form = reactive({
  username: '',
  email: '',
  password: '',
})

// 表单校验规则
const rules = reactive({
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
})

// 提交表单
const handleSubmit = () => {
  formRef.value.validate((valid) => { // 调用表单的 validate 方法：执行校验规则
    if (valid) {
      emit('submit', form) // 校验通过：把表单数据传给父组件; emit('submit', 数据) → 触发父组件的 @submit="handleFormSubmit"
    } else {
      ElMessage.error('表单校验失败，请检查输入')
      return false
    }
  })
}

// 重置表单
const handleReset = () => {
  if (formRef.value) { // 判断表单实例是否存在
    formRef.value.resetFields() // 重置表单字段
  }
  Object.assign(form, { // 手动重置 form 对象的所有属性（兜底：确保数据清空）
    username: '',
    email: '',
    password: ''
  })
}
// 为什么要双重重置？
// - resetFields()：重置表单输入框的显示值（基于初始值）
// - Object.assign：重置 form 对象的实际数据（避免数据残留）


// 监听用户信息变化，初始化表单
// 区分新增/编辑模式
watch(
  () => props.userInfo, // 监听的目标：父组件传过来的 userInfo
  (val) => { // val = 最新的 userInfo 值
    if (val.id) {
      // 有 id → 编辑模式（父组件传了已存在的用户数据）
      isEdit.value = true
      Object.assign(form, val) // 把用户数据填充到表单里（Object.assign 合并对象）
      delete form.password // 编辑模式下删除password字段，避免传给后端
    } else {
      // 无 id → 新增模式（父组件传的是空对象）
      isEdit.value = false
      handleReset()
    }
  },
  { immediate: true } // 立即执行：组件挂载时就触发一次监听（初始化表单）
)
</script>