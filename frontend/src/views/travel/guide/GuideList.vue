<template>
  <div class="guide-list-container">
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">旅游攻略</h1>
        <p class="page-subtitle">探索精彩目的地，发现旅游灵感</p>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="goToCreate">
          <el-icon><Plus /></el-icon>
          <span>发布攻略</span>
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选区 -->
    <el-card class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="搜索攻略标题" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="城市" >
          <el-input v-model="searchForm.city" placeholder="目的地城市" clearable style="width: 100px" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="searchForm.tags" multiple placeholder="选择标签" clearable style="width: 180px">
            <el-option label="亲子游" value="亲子游" />
            <el-option label="情侣游" value="情侣游" />
            <el-option label="自驾游" value="自驾游" />
            <el-option label="背包客" value="背包客" />
            <el-option label="摄影" value="摄影" />
            <el-option label="美食" value="美食" />
            <el-option label="历史文化" value="历史文化" />
            <el-option label="自然风光" value="自然风光" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="searchForm.is_official" placeholder="全部" clearable style="width: 100px">
            <!-- <el-option :label="null" value="null">全部</el-option> -->
            <el-option label="官方攻略" :value="true" />
            <el-option label="用户攻略" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 100px">
            <el-option label="已发布" value="published" />
            <el-option label="待审核" value="pending" />
            <el-option label="草稿" value="draft" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="AI生成">
          <el-select v-model="searchForm.is_ai_generated" placeholder="全部" clearable style="width: 100px">
            <!-- <el-option :label="null" value="null">全部</el-option> -->
            <el-option label="AI生成" :value="true" />
            <el-option label="用户创作" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 攻略列表 -->
    <div class="guide-grid" v-loading="loading">
      <el-empty v-if="!loading && guides.length === 0" description="暂无攻略" />

      <el-card
        v-for="guide in guides"
        :key="guide.id"
        class="guide-card"
        shadow="hover"
        @click="goToDetail(guide.id)"
      >
        <div class="card-header">
          <div class="card-tags">
            <el-tag v-if="guide.is_official" type="warning" size="small" effect="dark">官方</el-tag>
            <el-tag v-else type="success" size="small">用户</el-tag>
            <el-tag v-if="guide.is_ai_generated" type="info" size="small">AI生成</el-tag>
            <el-tag v-if="guide.status === 'pending'" type="warning" size="small">待审核</el-tag>
            <el-tag v-else-if="guide.status === 'draft'" type="info" size="small">草稿</el-tag>
            <el-tag v-else-if="guide.status === 'rejected'" type="danger" size="small">已拒绝</el-tag>
          </div>
          <el-dropdown trigger="click" @command="(cmd) => handleCardCommand(cmd, guide)">
            <el-button text @click.stop><el-icon><MoreFilled /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit" v-if="canEdit(guide)">
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-dropdown-item>
                <el-dropdown-item command="delete" v-if="canEdit(guide)" divided>
                  <el-icon><Delete /></el-icon>
                  删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <div class="card-content">
          <h3 class="card-title">{{ guide.title }}</h3>
          <div class="card-city">
            <el-icon><Location /></el-icon>
            <span>{{ guide.city }}</span>
          </div>
          <p class="card-summary">{{ guide.summary || '暂无简介' }}</p>
          <div class="card-tags-list">
            <el-tag v-for="tag in guide.tags" :key="tag" size="small" class="tag-item">
              {{ tag }}
            </el-tag>
          </div>
        </div>

        <div class="card-footer">
          <div class="author-info">
            <el-avatar :size="24">
              {{ guide.author?.username?.charAt(0).toUpperCase() || 'U' }}
            </el-avatar>
            <span class="author-name">{{ guide.author?.username || '匿名' }}</span>
          </div>
          <div class="stats">
            <span class="stat-item">
              <el-icon><View /></el-icon>
              {{ guide.view_count }}
            </span>
            <span class="stat-item">
              <el-icon><Star /></el-icon>
              {{ guide.like_count }}
            </span>
            <span class="stat-item">
              <el-icon><ChatDotRound /></el-icon>
              {{ guide.comment_count }}
            </span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 分页 -->
    <div class="pagination-container" v-if="total > 0">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="fetchGuides"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Search, Refresh, MoreFilled, Edit, Delete,
  Location, View, Star, ChatDotRound
} from '@element-plus/icons-vue'
import { useUserStore } from '@/pinia/userStore'
import { getGuideList, deleteGuide } from '@/api/guide'

const router = useRouter()
const userStore = useUserStore()

const loading = ref(false)
const guides = ref([])
const total = ref(0)

const searchForm = reactive({
  keyword: '',
  city: '',
  tags: [],
  is_official: null,
  status: '',
  is_ai_generated: null
})

const pagination = reactive({
  page: 1,
  page_size: 10
})

const fetchGuides = async () => {
  loading.value = true
  try {
    const params = {
      ...searchForm,
      is_official: searchForm.is_official === 'null' ? null : searchForm.is_official,
      is_ai_generated: searchForm.is_ai_generated === 'null' ? null : searchForm.is_ai_generated,
      page: pagination.page,
      page_size: pagination.page_size
    }
    const res = await getGuideList(params)
    guides.value = res.items || []
    total.value = res.total || 0
  } catch (error) {
    ElMessage.error('获取攻略列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchGuides()
}

const handleSizeChange = () => {
  pagination.page = 1
  fetchGuides()
}

const handleReset = () => {
  searchForm.keyword = ''
  searchForm.city = ''
  searchForm.tags = []
  searchForm.is_official = null
  searchForm.status = ''
  searchForm.is_ai_generated = null
  handleSearch()
}

const goToCreate = () => {
  router.push('/guide/create')
}

const goToDetail = (id) => {
  router.push(`/guide/${id}`)
}

const canEdit = (guide) => {
  const isAdmin = userStore.userInfo.roles?.some(r => ['admin', 'guide_admin'].includes(r.name))
  const isAuthor = String(guide.author_id) === String(userStore.userInfo.id)
  return isAdmin || isAuthor
}

const handleCardCommand = async (command, guide) => {
  if (command === 'edit') {
    router.push(`/guide/edit/${guide.id}`)
  } else if (command === 'delete') {
    try {
      await ElMessageBox.confirm('确定要删除这篇攻略吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })
      await deleteGuide(guide.id)
      ElMessage.success('删除成功')
      fetchGuides()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('删除失败')
      }
    }
  }
}

onMounted(() => {
  fetchGuides()
})
</script>

<style scoped>
.guide-list-container {
  padding: 24px;
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  flex: 1;
}

.page-title {
  margin: 0 0 8px 0;
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.page-subtitle {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.search-card {
  margin-bottom: 24px;
  border-radius: 12px;
}

.search-form {
  margin: 0;
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.guide-card {
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.guide-card:hover {
  transform: translateY(-4px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.card-tags {
  display: flex;
  gap: 8px;
}

.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-title {
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-city {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: #667eea;
  margin-bottom: 12px;
}

.card-summary {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}

.card-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.tag-item {
  margin: 0;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.author-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.author-name {
  font-size: 13px;
  color: #606266;
}

.stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #909399;
}

.pagination-container {
  display: flex;
  justify-content: center;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
}
</style>
