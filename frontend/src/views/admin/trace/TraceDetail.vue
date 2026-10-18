<template>
  <div class="trace-detail-container">
    <!-- 头部信息栏 -->
    <div class="detail-header">
      <div class="header-left">
        <span class="trace-id">Trace ID: {{ traceId }}</span>
        <el-tag v-if="traceData" :type="getOverviewStatusType()" size="small" class="status-tag">
          {{ getOverviewStatusText() }}
        </el-tag>
      </div>
      <div class="header-right">
        <el-button size="small" @click="copyTraceId">
          <el-icon><DocumentCopy /></el-icon>
          复制 Trace ID
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <!-- 主体内容 -->
    <div v-else-if="traceData" class="detail-body">
      <el-row :gutter="20">
        <!-- 左侧：瀑布图/时间线 -->
        <el-col :span="16">
          <el-card class="timeline-card" shadow="never">
            <template #header>
              <div class="card-header">
                <div class="header-title-section">
                  <span class="card-icon">🌊</span>
                  <span class="card-title">执行流程</span>
                </div>
                <div class="view-toggle">
                  <el-radio-group v-model="viewMode" size="small">
                    <el-radio-button value="tree">树状</el-radio-button>
                    <el-radio-button value="flat">扁平</el-radio-button>
                  </el-radio-group>
                </div>
              </div>
            </template>

            <!-- 树状视图 -->
            <div v-if="viewMode === 'tree'" class="tree-view">
              <div v-for="node in traceData.tree" :key="node.span_id" class="tree-node-wrapper" :style="{ marginLeft: '0px' }">
                <div
                  class="tree-node-card"
                  :class="{ 'is-selected': selectedSpanId === node.span_id }"
                  @click="selectSpan(node)"
                >
                  <span
                    v-if="node.children && node.children.length"
                    class="tree-expand-btn"
                    @click.stop="toggleNodeExpand(node)"
                  >
                    {{ node._expanded ? '−' : '+' }}
                  </span>
                  <span v-else class="tree-node-spacer"></span>
                  <span class="tree-level-badge" :class="'tree-level-' + node.level.toLowerCase()">
                    {{ node.level }}
                  </span>
                  <span class="tree-node-name">{{ node.name }}</span>
                  <span class="tree-status-badge" :class="'tree-status-' + node.status.toLowerCase()">
                    {{ getStatusText(node.status) }}
                  </span>
                  <span v-if="node.duration_ms" class="tree-node-duration">
                    <span class="tree-duration-num">{{ formatDuration(node.duration_ms).value }}</span>
                    <span class="tree-duration-unit">{{ formatDuration(node.duration_ms).unit }}</span>
                  </span>
                </div>

                <!-- 递归子节点 -->
                <div v-if="node.children && node.children.length && node._expanded">
                  <div v-for="child in node.children" :key="child.span_id" class="tree-node-wrapper" :style="{ marginLeft: '36px' }">
                    <div
                      class="tree-node-card"
                      :class="{ 'is-selected': selectedSpanId === child.span_id }"
                      @click="selectSpan(child)"
                    >
                      <span
                        v-if="child.children && child.children.length"
                        class="tree-expand-btn"
                        @click.stop="toggleNodeExpand(child)"
                      >
                        {{ child._expanded ? '−' : '+' }}
                      </span>
                      <span v-else class="tree-node-spacer"></span>
                      <span class="tree-level-badge" :class="'tree-level-' + child.level.toLowerCase()">
                        {{ child.level }}
                      </span>
                      <span class="tree-node-name">{{ child.name }}</span>
                      <span class="tree-status-badge" :class="'tree-status-' + child.status.toLowerCase()">
                        {{ getStatusText(child.status) }}
                      </span>
                      <span v-if="child.duration_ms" class="tree-node-duration">
                        <span class="tree-duration-num">{{ formatDuration(child.duration_ms).value }}</span>
                        <span class="tree-duration-unit">{{ formatDuration(child.duration_ms).unit }}</span>
                      </span>
                    </div>

                    <!-- 第三层 -->
                    <div v-if="child.children && child.children.length && child._expanded">
                      <div v-for="grandchild in child.children" :key="grandchild.span_id" class="tree-node-wrapper" :style="{ marginLeft: '72px' }">
                        <div
                          class="tree-node-card"
                          :class="{ 'is-selected': selectedSpanId === grandchild.span_id }"
                          @click="selectSpan(grandchild)"
                        >
                          <span
                            v-if="grandchild.children && grandchild.children.length"
                            class="tree-expand-btn"
                            @click.stop="toggleNodeExpand(grandchild)"
                          >
                            {{ grandchild._expanded ? '−' : '+' }}
                          </span>
                          <span v-else class="tree-node-spacer"></span>
                          <span class="tree-level-badge" :class="'tree-level-' + grandchild.level.toLowerCase()">
                            {{ grandchild.level }}
                          </span>
                          <span class="tree-node-name">{{ grandchild.name }}</span>
                          <span class="tree-status-badge" :class="'tree-status-' + grandchild.status.toLowerCase()">
                            {{ getStatusText(grandchild.status) }}
                          </span>
                          <span v-if="grandchild.duration_ms" class="tree-node-duration">
                            <span class="tree-duration-num">{{ formatDuration(grandchild.duration_ms).value }}</span>
                            <span class="tree-duration-unit">{{ formatDuration(grandchild.duration_ms).unit }}</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div v-if="!traceData.tree || traceData.tree.length === 0" class="empty-tree">
                <el-empty description="暂无数据" :image-size="80" />
              </div>
            </div>

            <!-- 扁平视图 -->
            <div v-else class="flat-view">
              <el-table :data="traceData.spans" stripe @row-click="selectSpan" :row-class-name="getTableRowClassName">
                <el-table-column prop="level" label="层级" width="120">
                  <template #default="{ row }">
                    <span class="level-badge" :class="'level-' + row.level.toLowerCase()">
                      {{ row.level }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.status)" size="small" effect="light">
                      {{ getStatusText(row.status) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="duration_ms" label="耗时" width="110">
                  <template #default="{ row }">
                    <span v-if="row.duration_ms" class="duration-text">
                      <span class="duration-value">{{ formatDuration(row.duration_ms).value }}</span>
                      <span class="duration-unit">{{ formatDuration(row.duration_ms).unit }}</span>
                    </span>
                    <span v-else class="duration-empty">-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="timestamp" label="时间" width="170" />
              </el-table>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：详情面板 -->
        <el-col :span="8">
          <el-card class="detail-panel" shadow="never">
            <template #header>
              <div class="detail-header-inner">
                <span class="detail-icon">📋</span>
                <span class="card-title">
                  {{ selectedSpan ? selectedSpan.name : '节点详情' }}
                </span>
              </div>
            </template>

            <div v-if="selectedSpan" class="span-detail">
              <!-- 基本信息 -->
              <div class="detail-section">
                <div class="section-title">
                  <span class="section-icon">ℹ️</span>
                  <span>基本信息</span>
                </div>
                <el-descriptions :column="1" border size="small" class="info-desc">
                  <el-descriptions-item label="层级">
                    <span class="level-badge" :class="'level-' + selectedSpan.level.toLowerCase()">
                      {{ selectedSpan.level }}
                    </span>
                  </el-descriptions-item>
                  <el-descriptions-item label="状态">
                    <el-tag :type="getStatusType(selectedSpan.status)" size="small" effect="light">
                      {{ getStatusText(selectedSpan.status) }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="耗时">
                    <span class="duration-text">
                      <span class="duration-value">{{ formatDuration(selectedSpan.duration_ms).value }}</span>
                      <span class="duration-unit">{{ formatDuration(selectedSpan.duration_ms).unit }}</span>
                    </span>
                  </el-descriptions-item>
                  <el-descriptions-item label="Span ID">
                    <span class="mono">{{ selectedSpan.span_id }}</span>
                  </el-descriptions-item>
                  <el-descriptions-item v-if="selectedSpan.parent_span_id" label="Parent ID">
                    <span class="mono">{{ selectedSpan.parent_span_id }}</span>
                  </el-descriptions-item>
                </el-descriptions>
              </div>

              <!-- 错误信息 -->
              <div v-if="selectedSpan.error_message" class="detail-section error-section">
                <div class="section-title">
                  <span class="section-icon">❌</span>
                  <span>错误信息</span>
                </div>
                <el-alert
                  :title="selectedSpan.error_type || 'Error'"
                  :description="selectedSpan.error_message"
                  type="error"
                  :closable="false"
                  show-icon
                  class="error-alert"
                />
                <div v-if="selectedSpan.full_data?.error_stack" class="error-stack">
                  <pre>{{ selectedSpan.full_data.error_stack }}</pre>
                </div>
              </div>

              <!-- 层级专属数据 -->
              <div class="detail-section" v-if="selectedSpan.full_data">
                <div class="section-title">
                  <span class="section-icon">📊</span>
                  <span>详细数据</span>
                </div>
                <el-tabs v-model="detailTab" type="border-card" class="detail-tabs">
                  <!-- Input/Output -->
                  <el-tab-pane label="输入/输出" name="io">
                    <div v-if="selectedSpan.full_data.input" class="data-block">
                      <h5>Input</h5>
                      <div class="json-viewer">
                        <pre>{{ formatJson(selectedSpan.full_data.input) }}</pre>
                      </div>
                    </div>
                    <div v-if="selectedSpan.full_data.output" class="data-block">
                      <h5>Output</h5>
                      <div class="json-viewer">
                        <pre>{{ formatJson(selectedSpan.full_data.output) }}</pre>
                      </div>
                    </div>
                    <div v-if="!selectedSpan.full_data.input && !selectedSpan.full_data.output" class="data-empty">
                      <el-empty description="暂无输入输出数据" :image-size="60" />
                    </div>
                  </el-tab-pane>

                  <!-- Metadata -->
                  <el-tab-pane label="Metadata" name="metadata">
                    <div v-if="selectedSpan.full_data.metadata">
                      <div class="json-viewer">
                        <pre>{{ formatJson(selectedSpan.full_data.metadata) }}</pre>
                      </div>
                    </div>
                    <div v-else class="data-empty">
                      <el-empty description="暂无 Metadata 数据" :image-size="60" />
                    </div>
                  </el-tab-pane>

                  <!-- 完整 JSON -->
                  <el-tab-pane label="完整 JSON" name="full">
                    <div class="json-viewer">
                      <pre>{{ formatJson(selectedSpan.full_data) }}</pre>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </div>
              <div v-else class="detail-section">
                <el-alert
                  title="没有 full_data"
                  type="warning"
                  :closable="false"
                  description="该节点没有详细数据"
                />
              </div>
            </div>

            <div v-else class="no-selection">
              <el-empty description="请从左侧选择一个节点" :image-size="100">
                <template #image>
                  <div class="empty-icon">👆</div>
                </template>
              </el-empty>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { ElMessage } from "element-plus";
import { DocumentCopy } from "@element-plus/icons-vue";

import { getTraceDetail } from "@/api/trace";

// 辅助函数：格式化 JSON
const formatJson = (data) => {
  try {
    if (typeof data === "string") {
      return data;
    }
    return JSON.stringify(data, null, 2);
  } catch (e) {
    return String(data);
  }
};

// 辅助函数：智能格式化耗时
const formatDuration = (ms) => {
  if (!ms && ms !== 0) return { value: '-', unit: '' };

  const numMs = Number(ms);

  if (numMs < 1000) {
    // 小于1秒，显示毫秒
    return { value: Math.round(numMs), unit: 'ms' };
  } else if (numMs < 60000) {
    // 小于1分钟，显示秒
    return { value: (numMs / 1000).toFixed(1), unit: 's' };
  } else {
    // 大于等于1分钟，显示分:秒
    const minutes = Math.floor(numMs / 60000);
    const seconds = Math.round((numMs % 60000) / 1000);
    return { value: `${minutes}:${seconds.toString().padStart(2, '0')}`, unit: 'min' };
  }
};

// Props
const props = defineProps({
  traceId: { type: String, required: true },
});

const emit = defineEmits(["close"]);

// 响应式变量
const loading = ref(true);
const traceData = ref(null);
const selectedSpan = ref(null);
const selectedSpanId = ref(null);
const viewMode = ref("tree");
const detailTab = ref("io");

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true;
    const res = await getTraceDetail(props.traceId);
    traceData.value = res;

    // 初始化节点展开状态
    if (res.tree) {
      initTreeNodes(res.tree);
    }

    // 默认选中第一个节点
    if (res.spans && res.spans.length > 0) {
      selectSpan(res.spans[0]);
    }
  } catch (error) {
    console.error("获取 Trace 详情失败：", error);
    ElMessage.error("获取 Trace 详情失败");
  } finally {
    loading.value = false;
  }
};

const initTreeNodes = (nodes) => {
  nodes.forEach((node) => {
    node._expanded = true;
    if (node.children && node.children.length) {
      initTreeNodes(node.children);
    }
  });
};

const toggleNodeExpand = (node) => {
  node._expanded = !node._expanded;
};

// 选择 Span
const selectSpan = (span) => {
  // 从 spans 数组里找带 full_data 的完整对象
  const fullSpan = traceData.value?.spans?.find((s) => s.span_id === span.span_id);

  selectedSpan.value = fullSpan || span;
  selectedSpanId.value = span.span_id;
  detailTab.value = "io";
};

// 辅助函数
const getStatusType = (status) => {
  const types = { STARTED: "info", COMPLETED: "success", FAILED: "danger" };
  return types[status] || "info";
};

const getStatusText = (status) => {
  const texts = { STARTED: "进行中", COMPLETED: "成功", FAILED: "失败" };
  return texts[status] || status;
};

// 概览状态
const getOverviewStatusType = () => {
  if (!traceData.value || !traceData.value.spans) return "info";
  const hasFailed = traceData.value.spans.some((s) => s.status === "FAILED");
  return hasFailed ? "danger" : "success";
};

const getOverviewStatusText = () => {
  if (!traceData.value || !traceData.value.spans) return "未知";
  const hasFailed = traceData.value.spans.some((s) => s.status === "FAILED");
  return hasFailed ? "包含失败" : "全部成功";
};

// 表格行类名
const getTableRowClassName = ({ row }) => {
  return selectedSpanId.value === row.span_id ? "table-row-selected" : "";
};

// 复制 Trace ID
const copyTraceId = async () => {
  try {
    await navigator.clipboard.writeText(props.traceId);
    ElMessage.success("已复制 Trace ID");
  } catch {
    ElMessage.warning("复制失败，请手动复制");
  }
};

// 监听 traceId 变化
watch(
  () => props.traceId,
  () => {
    if (props.traceId) {
      fetchData();
    }
  },
  { immediate: true }
);

onMounted(() => {
  if (props.traceId) {
    fetchData();
  }
});
</script>

<style scoped>
.trace-detail-container {
  display: flex;
  flex-direction: column;
  height: 80vh;
  background: #f5f7fa;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.trace-id {
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  letter-spacing: 0.5px;
}

.status-tag {
  margin-left: 8px;
}

.loading-container {
  padding: 32px;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.timeline-card,
.detail-panel {
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
}

.timeline-card :deep(.el-card__header),
.detail-panel :deep(.el-card__header) {
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 16px 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title-section,
.detail-header-inner {
  display: flex;
  align-items: center;
  gap: 10px;
}

.card-icon,
.detail-icon {
  font-size: 18px;
}

.card-title {
  font-weight: 600;
  color: #303133;
  font-size: 15px;
}

/* ============ 树状图样式 - 直接在模板中 ============ */
.tree-view {
  max-height: 65vh;
  overflow-y: auto;
  padding: 16px;
}

.tree-view::-webkit-scrollbar {
  width: 8px;
}

.tree-view::-webkit-scrollbar-track {
  background: #f5f7fa;
  border-radius: 4px;
}

.tree-view::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 4px;
}

.tree-view::-webkit-scrollbar-thumb:hover {
  background: #c0c4cc;
}

.empty-tree {
  padding: 40px 0;
}

.tree-node-wrapper {
  margin-bottom: 12px;
}

.tree-node-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  background: #ffffff;
  border-radius: 14px;
  border: 2px solid #ebeef5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  position: relative;
  overflow: hidden;
}

.tree-node-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: transparent;
  transition: background 0.25s;
}

.tree-node-card:hover {
  border-color: #dcdfe6;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.tree-node-card:hover::before {
  background: #409eff;
}

.tree-node-card.is-selected {
  background: #ecf5ff;
  border-color: #b3d1ff !important;
  box-shadow: 0 6px 24px rgba(64, 158, 255, 0.18) !important;
}

.tree-node-card.is-selected::before {
  background: #409eff !important;
}

.tree-expand-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 10px;
  background: #f5f7fa;
  border: 2px solid #dcdfe6;
  transition: all 0.2s ease;
  flex-shrink: 0;
  font-size: 18px;
  font-weight: 800;
  color: #606266;
  line-height: 1;
  user-select: none;
}

.tree-expand-btn:hover {
  background: #ecf5ff;
  border-color: #90cfff;
  color: #409eff;
  transform: scale(1.1);
}

.tree-node-spacer {
  width: 32px;
  flex-shrink: 0;
}

.tree-level-badge {
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.tree-level-agent {
  background: #409eff;
  color: #fff;
}

.tree-level-step {
  background: #f5576c;
  color: #fff;
}

.tree-level-tool {
  background: #4facfe;
  color: #fff;
}

.tree-level-llm {
  background: #43e97b;
  color: #fff;
}

.tree-node-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  color: #303133;
  font-weight: 600;
}

.tree-status-badge {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.tree-status-completed {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}

.tree-status-failed {
  background: #fef0f0;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}

.tree-status-started {
  background: #f4f4f5;
  color: #909399;
  border: 1px solid #e9e9eb;
}

.tree-node-duration {
  display: flex;
  align-items: baseline;
  gap: 3px;
  flex-shrink: 0;
  padding: 5px 12px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.tree-duration-num {
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  font-size: 15px;
  font-weight: 700;
  color: #409eff;
}

.tree-duration-unit {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

/* ============ 扁平视图样式 ============ */
.flat-view {
  max-height: 65vh;
  overflow-y: auto;
}

.flat-view::-webkit-scrollbar {
  width: 6px;
}

.flat-view::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.table-row-selected {
  background: #ecf5ff !important;
}

.duration-text {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.duration-value {
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  font-size: 14px;
  font-weight: 600;
  color: #409eff;
}

.duration-unit {
  font-size: 12px;
  color: #909399;
}

.duration-empty {
  color: #c0c4cc;
}

.level-badge {
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.level-agent {
  background: #409eff;
  color: #fff;
}

.level-step {
  background: #f5576c;
  color: #fff;
}

.level-tool {
  background: #4facfe;
  color: #fff;
}

.level-llm {
  background: #43e97b;
  color: #fff;
}

/* ============ 详情面板样式 ============ */
.span-detail {
  max-height: 65vh;
  overflow-y: auto;
}

.span-detail::-webkit-scrollbar {
  width: 6px;
}

.span-detail::-webkit-scrollbar-thumb {
  background: #dcdfe6;
  border-radius: 3px;
}

.detail-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.section-icon {
  font-size: 16px;
}

.info-desc :deep(.el-descriptions__label) {
  width: 90px;
  background: #fafafa;
}

.mono {
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  font-size: 12px;
  color: #606266;
}

.error-section .section-title {
  color: #f56c6c;
}

.error-alert {
  margin-bottom: 12px;
}

.error-stack {
  margin-top: 12px;
  background: #fef0f0;
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
  border: 1px solid #fde2e2;
}

.error-stack pre {
  margin: 0;
  font-size: 12px;
  color: #f56c6c;
  line-height: 1.6;
}

.data-block {
  margin-bottom: 18px;
}

.data-block h5 {
  margin: 0 0 10px 0;
  font-size: 13px;
  font-weight: 600;
  color: #606266;
}

.data-empty {
  padding: 20px 0;
}

.text-content {
  background: #f5f7fa;
  padding: 14px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
  border: 1px solid #ebeef5;
}

.llm-info {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.token-stats {
  display: flex;
  gap: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.token-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
  flex: 1;
}

.token-item.total {
  border-left: 2px solid #dcdfe6;
  padding-left: 16px;
}

.token-label {
  font-size: 12px;
  color: #909399;
}

.token-value {
  font-family: "SF Mono", "Monaco", "Inconsolata", "Roboto Mono", monospace;
  font-size: 18px;
  font-weight: 700;
  color: #409eff;
}

.token-item.total .token-value {
  color: #303133;
}

.detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.detail-tabs :deep(.el-tabs__content) {
  padding-top: 8px;
}

.json-viewer pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
  border: 1px solid #3d3d3d;
}

.json-viewer :deep(.el-collapse-item__header) {
  background: #f5f7fa;
  border-radius: 6px;
  padding-left: 12px;
  font-size: 13px;
  color: #606266;
}

.json-viewer :deep(.el-collapse-item__content) {
  padding-top: 12px;
}

.no-selection {
  padding: 60px 0;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
</style>
