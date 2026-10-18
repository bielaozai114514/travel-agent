<template>
  <div class="trace-list-container">
    <!-- 头部：统计卡片 -->
    <div class="trace-stats-bar" v-if="statistics">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-card class="stat-card">
            <div class="stat-value">{{ statistics.total_count }}</div>
            <div class="stat-label">总调用次数</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card success">
            <div class="stat-value">{{ statistics.success_count }}</div>
            <div class="stat-label">成功次数</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card danger">
            <div class="stat-value">{{ statistics.failed_count }}</div>
            <div class="stat-label">失败次数</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card class="stat-card info">
            <div class="stat-value">{{ statistics.success_rate }}%</div>
            <div class="stat-label">成功率</div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <!-- 操作按钮栏 -->
    <div class="trace-list-header">
      <span class="header-title">Agent Trace 追踪</span>
      <div class="header-actions">
        <el-button type="primary" @click="refreshStatistics">
          <el-icon><Refresh /></el-icon>
          刷新统计
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选栏 -->
    <div class="trace-filter-bar">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键词">
          <el-input
            v-model="searchForm.keyword"
            placeholder="搜索 Trace ID/名称/错误"
            clearable
            @clear="getTraceList"
          />
        </el-form-item>
        <el-form-item label="Agent 类型">
          <el-select v-model="searchForm.agent_type" placeholder="全部类型" clearable @clear="getTraceList" style="min-width: 175px">
            <el-option label="SimpleAgent" value="SimpleAgent" />
            <el-option label="ReActAgent" value="ReActAgent" />
            <el-option label="PlanSolveAgent" value="PlanSolveAgent" />
            <el-option label="ReflectionAgent" value="ReflectionAgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部状态" clearable @clear="getTraceList" style="min-width: 100px">
            <el-option label="成功" value="COMPLETED" />
            <el-option label="失败" value="FAILED" />
            <el-option label="进行中" value="STARTED" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DDTHH:mm:ss"
            @change="handleDateRangeChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="getTraceList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- Trace 列表 -->
    <el-table
      :data="traceList"
      border
      stripe
      v-loading="loading"
      row-key="id"
      :tree-props="{ children: 'children' }"
    >
      <el-table-column prop="trace_id" label="Trace ID" width="280">
        <template #default="{ row }">
          <el-tag type="info" size="small" class="trace-id-tag">
            {{ row.trace_id.substring(0, 16) }}...
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
      <el-table-column prop="agent_type" label="Agent 类型" width="140">
        <template #default="{ row }">
          <el-tag v-if="row.agent_type" size="small" :type="getAgentTypeColor(row.agent_type)">
            {{ row.agent_type }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="duration_ms" label="耗时" width="100">
        <template #default="{ row }">
          <span v-if="row.duration_ms">{{ formatDuration(row.duration_ms) }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column prop="timestamp" label="时间" width="170" />
      <el-table-column prop="error_message" label="错误" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
          <span v-else class="text-gray">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="250" fixed="right">
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            icon="View"
            @click="handleView(row)"
          >
            详情
          </el-button>
          <el-button
            type="danger"
            size="small"
            icon="Delete"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      :current-page="pageParams.page"
      :page-sizes="[10, 20, 50, 100]"
      :page-size="pageParams.page_size"
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      class="trace-pagination"
    >
    </el-pagination>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="Trace 详情"
      width="90%"
      class="detail-dialog"
      :close-on-click-modal="false"
    >
      <TraceDetail
        v-if="currentTraceId"
        :trace-id="currentTraceId"
        @close="detailDialogVisible = false"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Refresh } from "@element-plus/icons-vue";

import {
  getTraceList as fetchTraceList,
  deleteTrace,
  getTraceStatistics,
} from "@/api/trace";
import TraceDetail from "./TraceDetail.vue";

// 响应式变量
const loading = ref(false);
const traceList = ref([]);
const total = ref(0);
const statistics = ref(null);
const dateRange = ref([]);

// 分页参数
const pageParams = reactive({
  page: 1,
  page_size: 20,
});

// 搜索表单
const searchForm = reactive({
  keyword: "",
  agent_type: "",
  status: "",
  start_time: null,
  end_time: null,
});

// 弹窗相关
const detailDialogVisible = ref(false);
const currentTraceId = ref(null);

// 状态相关
const getStatusType = (status) => {
  const typeMap = {
    STARTED: "info",
    COMPLETED: "success",
    FAILED: "danger",
  };
  return typeMap[status] || "info";
};

const getStatusText = (status) => {
  const textMap = {
    STARTED: "进行中",
    COMPLETED: "成功",
    FAILED: "失败",
  };
  return textMap[status] || status;
};

const getAgentTypeColor = (type) => {
  const colorMap = {
    SimpleAgent: "",
    ReActAgent: "warning",
    PlanSolveAgent: "primary",
    ReflectionAgent: "success",
  };
  return colorMap[type] || "";
};

// 辅助函数：智能格式化耗时
const formatDuration = (ms) => {
  if (!ms && ms !== 0) return '-';

  const numMs = Number(ms);

  if (numMs < 1000) {
    // 小于1秒，显示毫秒
    return `${Math.round(numMs)}ms`;
  } else if (numMs < 60000) {
    // 小于1分钟，显示秒
    return `${(numMs / 1000).toFixed(1)}s`;
  } else {
    // 大于等于1分钟，显示分:秒
    const minutes = Math.floor(numMs / 60000);
    const seconds = Math.round((numMs % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}min`;
  }
};

// 获取 Trace 列表
const getTraceList = async () => {
  try {
    loading.value = true;
    const params = {
      ...pageParams,
      ...searchForm,
    };
    const res = await fetchTraceList(params);
    traceList.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error("获取 Trace 列表失败：", error);
    ElMessage.error("获取 Trace 列表失败");
  } finally {
    loading.value = false;
  }
};

// 获取统计数据
const refreshStatistics = async () => {
  try {
    const res = await getTraceStatistics(7);
    statistics.value = res;
  } catch (error) {
    console.error("获取统计数据失败：", error);
  }
};

// 时间范围变化
const handleDateRangeChange = (val) => {
  if (val && val.length === 2) {
    searchForm.start_time = val[0];
    searchForm.end_time = val[1];
  } else {
    searchForm.start_time = null;
    searchForm.end_time = null;
  }
};

// 分页处理
const handleSizeChange = (val) => {
  pageParams.page_size = val;
  getTraceList();
};

const handleCurrentChange = (val) => {
  pageParams.page = val;
  getTraceList();
};

// 重置搜索
const resetSearch = () => {
  searchForm.keyword = "";
  searchForm.agent_type = "";
  searchForm.status = "";
  searchForm.start_time = null;
  searchForm.end_time = null;
  dateRange.value = [];
  pageParams.page = 1;
  getTraceList();
};

// 查看详情
const handleView = (row) => {
  currentTraceId.value = row.trace_id;
  detailDialogVisible.value = true;
};

// 删除
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm("此操作将永久删除该 Trace, 是否继续?", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deleteTrace(row.trace_id);
    ElMessage.success("删除成功");
    getTraceList();
    refreshStatistics();
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除失败：", error);
      ElMessage.error("删除失败");
    }
  }
};

// 初始化
onMounted(() => {
  getTraceList();
  refreshStatistics();
});
</script>

<style scoped>
.trace-list-container {
  padding: 24px;
}

.trace-stats-bar {
  margin-bottom: 24px;
}

.stat-card {
  text-align: center;
  border: none;
}

.stat-card.success {
  border-left: 4px solid #67c23a;
}

.stat-card.danger {
  border-left: 4px solid #f56c6c;
}

.stat-card.info {
  border-left: 4px solid #409eff;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.trace-list-header {
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

.trace-filter-bar {
  margin-bottom: 20px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 1px solid #e9ecef;
}

.search-form {
  margin: 0;
}

.trace-id-tag {
  font-family: monospace;
}

.error-text {
  color: #f56c6c;
}

.text-gray {
  color: #909399;
}

.trace-pagination {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e9ecef;
}

.detail-dialog :deep(.el-dialog__body) {
  padding: 0;
  max-height: 80vh;
  overflow: hidden;
}
</style>

<style>
.detail-dialog .el-dialog__header{
  position: relative;
}

/* 全局样式 - 弹窗关闭按钮 */
.detail-dialog .el-dialog__headerbtn {
  top: 14px;
  right: 24px;
}

.detail-dialog .el-dialog__headerbtn  {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #909399;
  transition: all 0.2s ease;
  background: #f5f7fa;
}

.detail-dialog .el-dialog__headerbtn .el-dialog__close:hover {
  background: #e6e6e6;
  color: #606266;
}
</style>
