<template>
  <el-form
    ref="formRef"
    :model="form"
    :rules="rules"
    label-width="100px"
    size="default"
  >
    <el-form-item label="角色名称" prop="name">
      <el-input v-model="form.name" placeholder="请输入角色名称" />
    </el-form-item>
    <el-form-item label="角色描述" prop="description">
      <el-input
        v-model="form.description"
        type="textarea"
        :rows="3"
        placeholder="请输入角色描述"
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
const props = defineProps({
  roleInfo: {
    type: Object,
    default: () => ({})
  }
})

// 暴露方法给父组件
const emit = defineEmits(['submit'])

// 表单引用
const formRef = ref(null)

// 判断是否为编辑模式
const isEdit = ref(false)

// 表单数据
const form = reactive({
  name: '',
  description: '',
})

// 表单校验规则
const rules = reactive({
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' }
  ],
  description: [
    { required: true, message: '请输入角色描述', trigger: 'blur' }
  ]
})

// 重置表单
const handleReset = () => {
  if (formRef.value) {
    formRef.value.resetFields()
  }
  Object.assign(form, {
    name: '',
    description: ''
  })
}

// 提交表单
const handleSubmit = () => {
  formRef.value.validate((valid) => {
    if (valid) {
      emit('submit', { ...form })
    } else {
      ElMessage.error('表单校验失败，请检查输入')
      return false
    }
  })
}

// 监听父组件传值变化
watch(() => props.roleInfo, (newVal) => {
  if (newVal && newVal.id) {
    isEdit.value = true
    Object.assign(form, {
      name: newVal.name || '',
      description: newVal.description || ''
    })
  } else {
    isEdit.value = false
    handleReset()
  }
}, { immediate: true })

// 暴露方法给父组件
defineExpose({
  handleReset
})
</script>
