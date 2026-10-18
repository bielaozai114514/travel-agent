<template>
  <el-button
    v-if="hasPermission"
    :type="type"
    :icon="icon"
    :size="size"
    @click="handleClick"
    v-bind="$attrs"
  >
    <slot></slot>
  </el-button>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '@/pinia/userStore'
import { checkPermission } from '@/utils/permission'

const props = defineProps({
  // 权限标识
  permission: {
    type: String,
    required: true
  },
  // 按钮类型
  type: {
    type: String,
    default: 'default'
  },
  // 按钮图标
  icon: {
    type: String,
    default: ''
  },
  // 按钮大小
  size: {
    type: String,
    default: 'default'
  }
})

const emit = defineEmits(['click'])

const userStore = useUserStore()

// 判断是否有权限
const hasPermission = computed(() => {
  return checkPermission(userStore, props.permission)
})

// 按钮点击事件
const handleClick = () => {
  emit('click')
}
</script>