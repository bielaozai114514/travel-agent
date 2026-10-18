<template>
  <!-- 路由出口：所有页面都在这里渲染 -->
  <router-view />
</template>

<script setup>
// 无需添加代码，仅作为路由容器
</script>

<style scoped>
/* 全局样式重置：去除默认边距，让页面占满屏幕 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
}
</style>