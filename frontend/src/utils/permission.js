/**
 * 权限指令封装
 * @param {object} userStore Pinia 用户状态
 * @returns {object} 自定义指令
 */
export function permissionDirective(userStore) {
  return {
    mounted(el, binding) {
      const requiredPermission = binding.value
      if (!requiredPermission) return
      
      // 检查是否有权限
      const hasPermission = userStore.hasPermission(requiredPermission)
      if (!hasPermission) {
        // 无权限则隐藏元素
        el.style.display = 'none'
        // 或者移除元素
        // el.parentNode?.removeChild(el)
      }
    }
  }
}

/**
 * 权限检查函数（用于脚本中）
 * @param {object} userStore Pinia 用户状态
 * @param {string} permission 权限标识
 * @returns {boolean} 是否有权限
 */
export function checkPermission(userStore, permission) {
  return userStore.hasPermission(permission)
}