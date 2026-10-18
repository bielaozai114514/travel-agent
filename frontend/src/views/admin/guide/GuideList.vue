<template>
  <div class="guide-list-container">
    <!-- 操作按钮栏 -->
    <div class="guide-list-header">
      <span class="header-title">攻略管理</span>
    </div>

    <!-- 搜索和筛选栏 -->
    <div class="guide-filter-bar">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键词">
          <el-input
            v-model="searchForm.keyword"
            placeholder="搜索标题/摘要"
            clearable
            @clear="getGuideList"
          />
        </el-form-item>
        <el-form-item label="城市">
          <el-input
            v-model="searchForm.city"
            placeholder="城市名称"
            clearable
            @clear="getGuideList"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部状态" clearable @clear="getGuideList" style="min-width: 100px">
            <el-option label="草稿" value="draft" />
            <el-option label="待审核" value="pending" />
            <el-option label="已发布" value="published" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="getGuideList">查询</el-button>
          <el-button @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 攻略列表 -->
    <el-table
      :data="guideList"
      border
      stripe
      v-loading="loading"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="city" label="城市" width="120" />
      <el-table-column label="作者" width="120">
        <template v-slot="scope">
          {{ scope.row.author?.username || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template v-slot="scope">
          <el-tag :type="getStatusType(scope.row.status)">
            {{ getStatusText(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="view_count" label="浏览" width="80" />
      <el-table-column prop="like_count" label="点赞" width="80" />
      <el-table-column prop="comment_count" label="评论" width="80" />
      <el-table-column prop="create_time" label="创建时间" width="170" />
      <el-table-column label="操作" min-width="280" fixed="right">
        <template v-slot="scope">
          <el-button
            type="primary"
            size="small"
            icon="View"
            @click="handleView(scope.row)"
          >
            查看
          </el-button>
          <el-button
            type="warning"
            size="small"
            icon="Edit"
            @click="handleEdit(scope.row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="scope.row.status === 'pending'"
            type="success"
            size="small"
            icon="Check"
            @click="handleReview(scope.row)"
          >
            审核
          </el-button>
          <el-button
            type="danger"
            size="small"
            icon="Delete"
            @click="handleDelete(scope.row)"
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
      class="guide-pagination"
    >
    </el-pagination>

    <!-- 查看详情弹窗 -->
    <el-dialog
      v-model="viewDialogVisible"
      title="攻略详情"
      width="800px"
      class="view-dialog"
    >
      <div class="guide-detail-content" v-if="currentGuide">
        <h2>{{ currentGuide.title }}</h2>
        <div class="guide-meta">
          <span>城市: {{ currentGuide.city }}</span>
          <span>标签: {{ (currentGuide.tags || []).join(', ') || '无' }}</span>
          <span>作者: {{ currentGuide.author?.username || '-' }}</span>
        </div>
        <div class="guide-summary" v-if="currentGuide.summary">
          <h4>摘要</h4>
          <p>{{ currentGuide.summary }}</p>
        </div>
        <div class="guide-body">
          <h4>内容</h4>
          <div class="markdown-content" v-html="renderedContent"></div>
        </div>
      </div>
    </el-dialog>

    <!-- 审核弹窗 -->
    <el-dialog
      v-model="reviewDialogVisible"
      title="审核攻略"
      width="700px"
      class="review-dialog"
    >
      <div class="review-content" v-if="currentGuide">
        <div class="review-guide-info">
          <h3>{{ currentGuide.title }}</h3>
          <p class="guide-city">城市: {{ currentGuide.city }}</p>
          <div class="markdown-preview">
            <div class="markdown-content" v-html="renderedPreviewContent"></div>
          </div>
        </div>
        <el-form :model="reviewForm" label-width="80px" class="review-form">
          <el-form-item label="审核结果">
            <el-radio-group v-model="reviewForm.status">
              <el-radio label="published">通过</el-radio>
              <el-radio label="rejected">拒绝</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="审核意见">
            <el-input
              v-model="reviewForm.review_comment"
              type="textarea"
              :rows="4"
              placeholder="请输入审核意见（拒绝时必填）"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReview" :loading="submitting">
          提交审核
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { marked } from "marked";
import {
  getGuideList as fetchGuideList,
  deleteGuide,
  reviewGuide,
} from "@/api/guide";

// 导入权限相关
import { permissionDirective } from "@/utils/permission";
import { useUserStore } from "@/pinia/userStore";
const userStore = useUserStore();
const vPermission = permissionDirective(userStore);

// 响应式变量
const loading = ref(false);
const guideList = ref([]);
const total = ref(0);
const selectedIds = ref([]);

// 分页参数
const pageParams = reactive({
  page: 1,
  page_size: 10,
});

// 搜索表单
const searchForm = reactive({
  keyword: "",
  city: "",
  status: "",
});

// 弹窗相关
const viewDialogVisible = ref(false);
const reviewDialogVisible = ref(false);
const currentGuide = ref(null);
const submitting = ref(false);

// 审核表单
const reviewForm = reactive({
  status: "published",
  review_comment: "",
});

// 渲染 Markdown 内容
const renderedContent = computed(() => {
  if (!currentGuide.value) return "";
  return marked.parse(currentGuide.value.content || "");
});

const renderedPreviewContent = computed(() => {
  if (!currentGuide.value) return "";
  const content = currentGuide.value.content || "";
  // 只预览前2000字符
  const preview = content.length > 2000 ? content.substring(0, 2000) + "..." : content;
  return marked.parse(preview);
});

// 状态相关
const getStatusType = (status) => {
  const typeMap = {
    draft: "info",
    pending: "warning",
    published: "success",
    rejected: "danger",
  };
  return typeMap[status] || "info";
};

const getStatusText = (status) => {
  const textMap = {
    draft: "草稿",
    pending: "待审核",
    published: "已发布",
    rejected: "已拒绝",
  };
  return textMap[status] || status;
};

// 获取攻略列表
const getGuideList = async () => {
  try {
    loading.value = true;
    const params = {
      ...pageParams,
      ...searchForm,
    };
    const res = await fetchGuideList(params);
    guideList.value = res.items || [];
    total.value = res.total || 0;
  } catch (error) {
    console.error("获取攻略列表失败：", error);
    ElMessage.error("获取攻略列表失败");
  } finally {
    loading.value = false;
  }
};

// 分页处理
const handleSizeChange = (val) => {
  pageParams.page_size = val;
  getGuideList();
};

const handleCurrentChange = (val) => {
  pageParams.page = val;
  getGuideList();
};

// 重置搜索
const resetSearch = () => {
  searchForm.keyword = "";
  searchForm.city = "";
  searchForm.status = "";
  pageParams.page = 1;
  getGuideList();
};

// 选择变化
const handleSelectionChange = (val) => {
  selectedIds.value = val.map((item) => item.id);
};

// 查看详情
const handleView = (row) => {
  currentGuide.value = { ...row };
  viewDialogVisible.value = true;
};

// 编辑 - 跳转到前端编辑页面
const handleEdit = (row) => {
  window.open(`/guide/edit/${row.id}`, "_blank");
};

// 审核
const handleReview = (row) => {
  currentGuide.value = { ...row };
  reviewForm.status = "published";
  reviewForm.review_comment = "";
  reviewDialogVisible.value = true;
};

// 提交审核
const submitReview = async () => {
  if (reviewForm.status === "rejected" && !reviewForm.review_comment.trim()) {
    ElMessage.warning("拒绝时请填写审核意见");
    return;
  }

  try {
    submitting.value = true;
    await reviewGuide(currentGuide.value.id, {
      status: reviewForm.status,
      review_comment: reviewForm.review_comment,
    });
    ElMessage.success("审核成功");
    reviewDialogVisible.value = false;
    getGuideList();
  } catch (error) {
    console.error("审核失败：", error);
    ElMessage.error("审核失败");
  } finally {
    submitting.value = false;
  }
};

// 删除
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm("此操作将永久删除该攻略, 是否继续?", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deleteGuide(row.id);
    ElMessage.success("删除成功");
    getGuideList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除失败：", error);
      ElMessage.error("删除失败");
    }
  }
};

// 初始化
onMounted(() => {
  getGuideList();
});
</script>

<style scoped>
.guide-list-container {
  padding: 24px;
}

.guide-list-header {
  margin-bottom: 20px;
}

.header-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.guide-filter-bar {
  margin-bottom: 20px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 1px solid #e9ecef;
}

.search-form {
  margin: 0;
}

.guide-pagination {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e9ecef;
}

/* 弹窗样式 */
.view-dialog,
.review-dialog {
  :deep(.el-dialog__body) {
    max-height: 70vh;
    overflow-y: auto;
  }
}

.guide-detail-content h2 {
  margin: 0 0 16px 0;
  color: #303133;
}

.guide-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  color: #606266;
  font-size: 14px;
}

.guide-summary,
.guide-body {
  margin-bottom: 20px;
}

.guide-summary h4,
.guide-body h4 {
  margin: 0 0 12px 0;
  color: #303133;
  font-size: 15px;
}

.markdown-content {
  padding: 16px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  line-height: 1.6;

  :deep(h1),
  :deep(h2),
  :deep(h3),
  :deep(h4) {
    margin-top: 16px;
    margin-bottom: 8px;
  }

  :deep(p) {
    margin-bottom: 12px;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 24px;
    margin-bottom: 12px;
  }

  :deep(code) {
    background: #f5f7fa;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
  }

  :deep(pre) {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    margin-bottom: 12px;
  }

  :deep(blockquote) {
    border-left: 4px solid #409eff;
    padding-left: 16px;
    margin: 12px 0;
    color: #606266;
  }
}

.review-guide-info {
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.review-guide-info h3 {
  margin: 0 0 8px 0;
  color: #303133;
}

.guide-city {
  margin: 0 0 16px 0;
  color: #909399;
}

.markdown-preview {
  max-height: 300px;
  overflow-y: auto;
}

.review-form {
  margin-top: 20px;
}
</style>
