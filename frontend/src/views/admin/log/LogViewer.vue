<template>
  <div class="log-viewer-container">
    <!-- 头部 -->
    <div class="log-viewer-header">
      <span class="header-title">日志查看器</span>
      <div class="header-actions">
        <el-button type="primary" @click="refreshLogFiles">
          <el-icon><Refresh /></el-icon>
          刷新列表
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="log-viewer-body">
      <!-- 左侧：文件列表 -->
      <el-col :span="6">
        <el-card class="file-list-card">
          <template #header>
            <span class="card-title">日志文件</span>
          </template>
          <el-menu
            :default-active="currentFile"
            @select="selectFile"
            class="file-menu"
          >
            <el-menu-item
              v-for="file in logFiles"
              :key="file.filename"
              :index="file.filename"
            >
              <div class="file-item">
                <span class="file-name">{{ file.filename }}</span>
                <span class="file-size">{{ file.size_mb }}MB</span>
              </div>
            </el-menu-item>
          </el-menu>
        </el-card>
      </el-col>

      <!-- 右侧：日志内容 -->
      <el-col :span="18">
        <el-card class="log-content-card">
          <template #header>
            <div class="content-header">
              <span class="card-title">{{ currentFile || '请选择日志文件' }}</span>
              <div class="content-actions">
                <el-select
                  v-model="logLevelFilter"
                  placeholder="日志级别"
                  clearable
                  size="small"
                  style="width: 120px; margin-right: 12px"
                >
                  <el-option label="DEBUG" value="DEBUG" />
                  <el-option label="INFO" value="INFO" />
                  <el-option label="WARNING" value="WARNING" />
                  <el-option label="ERROR" value="ERROR" />
                  <el-option label="CRITICAL" value="CRITICAL" />
                </el-select>
                <el-input
                  v-model="keywordFilter"
                  placeholder="搜索关键词"
                  clearable
                  size="small"
                  style="width: 200px; margin-right: 12px"
                  @clear="applyFilters"
                  @keyup.enter="applyFilters"
                />
                <el-button size="small" @click="applyFilters">搜索</el-button>
                <el-button size="small" @click="jumpToTop">顶部</el-button>
                <el-button size="small" @click="jumpToBottom" :loading="autoRefresh">底部</el-button>
                <el-switch
                  v-model="autoRefresh"
                  size="small"
                  active-text="自动刷新"
                  style="margin-left: 12px"
                />
              </div>
            </div>
          </template>

          <!-- 加载状态 -->
          <div v-if="loading" class="loading-container">
            <el-skeleton :rows="20" animated />
          </div>

          <!-- 日志内容 -->
          <div v-else-if="currentFile" class="log-content" ref="logContentRef">
            <div
              v-for="(line, index) in filteredLines"
              :key="index"
              class="log-line"
              :class="getLineClass(line)"
            >
              <span class="line-number">{{ originalLineNumbers[index] }}</span>
              <span class="line-text">{{ line }}</span>
            </div>

            <!-- 加载更多 -->
            <div v-if="hasMore" class="load-more">
              <el-button link @click="loadMore" :loading="loadingMore">
                加载更多...
              </el-button>
            </div>
          </div>

          <!-- 未选择文件 -->
          <div v-else class="no-file">
            <el-empty description="请从左侧选择日志文件" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from "vue";
import { ElMessage } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import { getLogFiles, readLogFile } from "@/api/trace";

// 响应式变量
const loading = ref(false);
const loadingMore = ref(false);
const logFiles = ref([]);
const currentFile = ref(null);
const logContentRef = ref(null);

// 去除 ANSI 颜色转义码
const stripAnsiCodes = (str) => {
  // eslint-disable-next-line no-control-regex
  return str.replace(/\x1b\[[0-9;]*m/g, '');
};

// 日志数据
const allLines = ref([]);
const currentOffset = ref(0);
const hasMore = ref(true);
const originalLineNumbers = ref([]);

// 过滤器
const logLevelFilter = ref("");
const keywordFilter = ref("");
const autoRefresh = ref(false);

let autoRefreshInterval = null;

const filteredLines = computed(() => {
  let lines = allLines.value;

  // 按日志级别过滤
  if (logLevelFilter.value) {
    const level = logLevelFilter.value.toUpperCase();
    lines = lines.filter((line) => line.includes(`- ${level} -`));
  }

  // 按关键词过滤
  if (keywordFilter.value) {
    lines = lines.filter((line) =>
      line.toLowerCase().includes(keywordFilter.value.toLowerCase())
    );
  }

  return lines;
});

// 获取日志文件列表
const refreshLogFiles = async () => {
  try {
    const res = await getLogFiles();
    logFiles.value = res || [];
  } catch (error) {
    console.error("获取日志文件列表失败：", error);
    ElMessage.error("获取日志文件列表失败");
  }
};

// 选择文件
const selectFile = async (filename) => {
  currentFile.value = filename;
  currentOffset.value = 0;
  allLines.value = [];
  originalLineNumbers.value = [];
  hasMore.value = true;
  await loadLogContent();
};

// 加载日志内容
const loadLogContent = async () => {
  if (!currentFile.value) return;

  try {
    loading.value = true;
    const limit = 1000;
    const res = await readLogFile(currentFile.value, currentOffset.value, limit);

    if (res) {
      // 记录原始行号，并去除 ANSI 转义码
      const newLineNumbers = [];
      const cleanedLines = res.lines.map(line => stripAnsiCodes(line));
      for (let i = 0; i < cleanedLines.length; i++) {
        newLineNumbers.push(currentOffset.value + i + 1);
      }
      originalLineNumbers.value = [...newLineNumbers, ...originalLineNumbers.value];

      // 新内容添加到前面（因为日志是倒序读取的）
      allLines.value = [...cleanedLines, ...allLines.value];

      currentOffset.value += limit;
      hasMore.value = currentOffset.value < res.total_lines;

      // 如果是第一次加载，自动滚动到底部
      if (currentOffset.value <= limit) {
        await nextTick();
        jumpToBottom();
      }
    }
  } catch (error) {
    console.error("加载日志内容失败：", error);
    ElMessage.error("加载日志内容失败");
  } finally {
    loading.value = false;
  }
};

// 加载更多
const loadMore = async () => {
  if (!hasMore.value || loadingMore.value) return;

  try {
    loadingMore.value = true;
    await loadLogContent();
  } finally {
    loadingMore.value = false;
  }
};

// 应用过滤器
const applyFilters = () => {
  // 过滤逻辑已经在 computed 中处理
};

// 滚动到顶部
const jumpToTop = () => {
  if (logContentRef.value) {
    logContentRef.value.scrollTop = 0;
  }
};

// 滚动到底部
const jumpToBottom = () => {
  if (logContentRef.value) {
    nextTick(() => {
      logContentRef.value.scrollTop = logContentRef.value.scrollHeight;
    });
  }
};

// 获取行样式类
const getLineClass = (line) => {
  // 更宽松的匹配方式，不依赖固定格式
  const upperLine = line.toUpperCase();
  if (upperLine.includes("ERROR") || upperLine.includes("CRITICAL")) {
    return "error";
  }
  if (upperLine.includes("WARNING") || upperLine.includes("WARN")) {
    return "warning";
  }
  if (upperLine.includes("DEBUG")) {
    return "debug";
  }
  if (upperLine.includes("INFO")) {
    return "info";
  }
  return "";
};

// 监听自动刷新
watch(autoRefresh, (val) => {
  if (val) {
    autoRefreshInterval = setInterval(() => {
      if (currentFile.value) {
        // 重新加载最新内容
        currentOffset.value = 0;
        allLines.value = [];
        originalLineNumbers.value = [];
        hasMore.value = true;
        loadLogContent();
      }
    }, 3000);
  } else {
    if (autoRefreshInterval) {
      clearInterval(autoRefreshInterval);
      autoRefreshInterval = null;
    }
  }
});

// 清理
onUnmounted(() => {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
  }
});

// 初始化
onMounted(() => {
  refreshLogFiles();
});
</script>

<style scoped>
.log-viewer-container {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.log-viewer-body {
  flex: 1;
  overflow: hidden;
}

.file-list-card,
.log-content-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.file-list-card :deep(.el-card__body),
.log-content-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.file-menu {
  height: 100%;
  max-height: 70vh;
  overflow-y: auto;
  overflow-x: hidden;
  border: none;
}

.file-menu :deep(.el-menu-item) {
  padding-right: 8px;
  height: auto;
  line-height: 1.4;
  padding-top: 8px;
  padding-bottom: 8px;
}

.file-menu :deep(.el-menu-item__content) {
  width: 100%;
  overflow: hidden;
}

.file-item {
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 8px;
}

.file-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.file-size {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
  white-space: nowrap;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.content-actions {
  display: flex;
  align-items: center;
}

.loading-container {
  padding: 20px;
}

.log-content {
  height: 70vh;
  overflow-y: auto;
  background: #1e1e1e;
  padding: 12px;
  font-family: "Consolas", "Monaco", monospace;
  font-size: 13px;
  line-height: 1.6;
}

.log-line {
  display: flex;
  gap: 12px;
  padding: 2px 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.line-number {
  color: #858585;
  user-select: none;
  text-align: right;
  min-width: 50px;
  flex-shrink: 0;
}

.line-text {
  flex: 1;
  color: #d4d4d4;
}

.log-line.debug .line-text {
  color: #9cdcfe;
}

.log-line.info .line-text {
  color: #6a9955;
}

.log-line.warning .line-text {
  color: #dcdcaa;
}

.log-line.error .line-text {
  color: #f14c4c;
}

.load-more {
  text-align: center;
  padding: 12px 0;
}

.no-file {
  padding: 60px 0;
}
</style>
