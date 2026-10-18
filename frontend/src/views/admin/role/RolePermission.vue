<template>
  <div class="role-permission-container">
    <el-transfer
      v-model="selectedPermissions"
      :data="permissionList"
      :titles="['未分配权限', '已分配权限']"
      :props="{
        key: 'id',
        label: 'description'
      }"
      filterable
      :filter-method="filterPermission"
      filter-placeholder="请输入权限名称搜索"
    />
    <div class="permission-actions">
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleSave" :loading="loading">保存</el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getPermissionList } from '@/api/permission'
import { getRolePermissions, bindRolePermissions, unbindRolePermissions } from '@/api/role'

const props = defineProps({
  roleId: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['success', 'cancel'])

// 响应式变量
const loading = ref(false)
const permissionList = ref([])
const selectedPermissions = ref([])
const originalPermissions = ref([])

// 权限筛选方法
const filterPermission = (query, item) => {
  return item.description.toLowerCase().includes(query.toLowerCase()) ||
         item.scope.toLowerCase().includes(query.toLowerCase())
}

// 获取所有权限列表
const fetchPermissionList = async () => {
  try {
    const res = await getPermissionList({ page_num: 1, page_size: 1000 })
    permissionList.value = res.data.list || []
  } catch (error) {
    console.error('获取权限列表失败：', error)
    ElMessage.error('获取权限列表失败')
  }
}

// 获取角色当前权限
const fetchRolePermissions = async () => {
  try {
    const res = await getRolePermissions(props.roleId)
    const permissions = Array.isArray(res.data?.permissions) ? res.data.permissions : []
    selectedPermissions.value = permissions.map(p => p.id)
    originalPermissions.value = [...selectedPermissions.value]
  } catch (error) {
    console.error('获取角色权限失败：', error)
    ElMessage.error('获取角色权限失败')
  }
}

// 保存权限配置
const handleSave = async () => {
  loading.value = true
  try {
    const currentPerms = selectedPermissions.value
    const originalPerms = originalPermissions.value

    // 计算新增的权限
    const toAdd = currentPerms.filter(id => !originalPerms.includes(id))
    // 计算移除的权限
    const toRemove = originalPerms.filter(id => !currentPerms.includes(id))

    // 执行绑定操作
    if (toAdd.length > 0) {
      await bindRolePermissions(props.roleId, toAdd)
    }

    // 执行解绑操作
    if (toRemove.length > 0) {
      await unbindRolePermissions(props.roleId, toRemove)
    }

    ElMessage.success('权限配置保存成功')
    emit('success')
  } catch (error) {
    console.error('保存权限配置失败：', error)
    ElMessage.error('保存权限配置失败')
  } finally {
    loading.value = false
  }
}

// 取消操作
const handleCancel = () => {
  emit('cancel')
}

// 监听roleId变化
watch(() => props.roleId, (newVal) => {
  if (newVal) {
    fetchRolePermissions()
  }
}, { immediate: true })

// 初始化
onMounted(() => {
  fetchPermissionList()
})
</script>

<style scoped>
.role-permission-container {
  padding: 20px;
}

.permission-actions {
  margin-top: 20px;
  text-align: right;
}
</style>
