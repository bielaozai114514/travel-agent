<template>
  <div class="user-role">
    <el-form label-width="100px">
      <el-form-item label="当前用户">
        <el-tag type="primary">{{ userName }}</el-tag>
      </el-form-item>
      <el-form-item label="角色列表">
        <el-tree
          ref="treeRef"
          :data="roleList"
          :props="treeProps"
          show-checkbox
          node-key="id"
          :default-checked-keys="checkedRoles"
          @check-change="handleCheckChange"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSave">保存角色</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getUserRoles, bindUserRoles, unbindUserRoles } from '@/api/user'
import { getRoleList } from '@/api/role'

// 接收父组件传值
const props = defineProps({
  userId: {
    type: Number,
    required: true
  }
})

// 暴露方法给父组件
const emit = defineEmits(['success'])

// 响应式变量：补充角色名称/完整角色列表
const treeRef = ref(null) // treeRef 响应式变量（绑定 el-tree 的 ref）
const roleList = ref([]) // 角色列表
const originCheckedRoles = ref([]) // 原始已选角色 ID
const checkedRoles = ref([]) // 已选角色 ID
const userName = ref('') // 用户名
const saveLoading = ref(false) // 保存按钮加载状态
const treeProps = reactive({ // 树配置
  label: 'name',
  children: 'children'
})

// 获取所有角色列表
const fetchRoleList = async () => {
  try {
    const res = await getRoleList({ page_num: 1, page_size: 100 })
    roleList.value = res.data.list
    console.log("获取角色列表成功")
  } catch (error) {
    ElMessage.error('获取角色列表失败')
  }
}

// 获取用户已绑定的角色
const fetchUserRoles = async () => {
  try {
    const res = await getUserRoles(props.userId)
    const responseData = res.data || {}
    const roleList = responseData.roles || []

    checkedRoles.value = roleList.map(item => item.id)
    // 关键：保存初始勾选状态（深拷贝，避免引用类型同步变化）
    originCheckedRoles.value = [...checkedRoles.value]
    userName.value = responseData.user?.username || ''
  } catch (error) {
    checkedRoles.value = []
    originCheckedRoles.value = [] // 异常时重置初始状态
    userName.value = ''
    ElMessage.error('获取用户角色失败')
    console.error('获取用户角色失败详情：', error)
  }
}

// 角色选择变化
const handleCheckChange = () => {
  checkedRoles.value = treeRef.value.getCheckedKeys()
}

// 保存角色
const handleSave = async () => {
  // 获取当前勾选的角色ID
  const currentCheckedKeys = treeRef.value?.getCheckedKeys() || []
  if (currentCheckedKeys.length === 0 && originCheckedRoles.value.length === 0) {
    ElMessage.warning('请选择至少一个角色')
    return
  }

  saveLoading.value = true
  try {
    // 对比初始状态和当前状态，拆分新增/删除的角色ID
    // 当前有但初始没有的ID（需要绑定）
    const addRoleIds = currentCheckedKeys.filter(id => !originCheckedRoles.value.includes(id))
    // 初始有但当前没有的ID（需要解绑）
    const deleteRoleIds = originCheckedRoles.value.filter(id => !currentCheckedKeys.includes(id))

    // 分别调用接口（有数据才调用，避免空请求）
    const requestList = []
    if (addRoleIds.length > 0) {
      requestList.push(bindUserRoles(props.userId, addRoleIds))
    }
    if (deleteRoleIds.length > 0) {
      requestList.push(unbindUserRoles(props.userId, deleteRoleIds))
    }

    // 等待所有接口调用完成
    if (requestList.length > 0) {
      await Promise.all(requestList)
    }

    // 成功提示 + 更新初始状态（避免重复保存时对比错误）
    ElMessage.success('角色更新成功')
    originCheckedRoles.value = [...currentCheckedKeys] // 更新初始状态为当前状态
    emit('success') // 通知父组件刷新数据
  } catch (error) {
    ElMessage.error('角色更新失败')
    console.error('角色更新失败详情：', error)
  } finally {
    saveLoading.value = false
  }
}

// 初始化
const init = async () => {
  // 先清空所有
  originCheckedRoles.value = []
  checkedRoles.value = []
  userName.value = ''
  roleList.value = []
  treeRef.value = null
  await fetchRoleList()
  await fetchUserRoles()
}

// 监听用户 ID 变化
watch(
  () => props.userId,
  () => {
    init()
  },
  { immediate: true }
)
</script>