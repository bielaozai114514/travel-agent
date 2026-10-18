<template>
  <div class="guide-detail-container" v-loading="loading">
    <div class="header-nav">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回攻略列表
      </el-button>
    </div>

    <div v-if="guide" class="detail-content">
      <!-- 攻略头部 -->
      <el-card class="header-card">
        <div class="guide-header">
          <div class="header-top">
            <div class="title-section">
              <div class="guide-tags">
                <el-tag v-if="guide.is_official" type="warning" size="large" effect="dark">官方攻略</el-tag>
                <el-tag v-else type="success" size="large">用户攻略</el-tag>
                <el-tag v-if="guide.is_ai_generated" type="info" size="large">AI生成</el-tag>
                <el-tag v-for="tag in guide.tags" :key="tag" size="large" class="tag-item">
                  {{ tag }}
                </el-tag>
              </div>
              <h1 class="guide-title">{{ guide.title }}</h1>
              <div class="guide-meta">
                <div class="city-info">
                  <el-icon><Location /></el-icon>
                  <span>{{ guide.city }}</span>
                </div>
                <div class="author-info">
                  <el-avatar :size="28">
                    {{ guide.author?.username?.charAt(0).toUpperCase() || 'U' }}
                  </el-avatar>
                  <span class="author-name">{{ guide.author?.username || '匿名' }}</span>
                </div>
                <div class="time-info">
                  <el-icon><Clock /></el-icon>
                  <span>{{ formatTime(guide.create_time) }}</span>
                </div>
              </div>
            </div>
            <div class="action-section">
              <div class="stats-card">
                <div class="stat-item">
                  <span class="stat-value">{{ guide.view_count }}</span>
                  <span class="stat-label">浏览</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ guide.like_count }}</span>
                  <span class="stat-label">点赞</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ guide.comment_count }}</span>
                  <span class="stat-label">评论</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ guide.share_count }}</span>
                  <span class="stat-label">分享</span>
                </div>
              </div>
              <div class="action-buttons">
                <el-button
                  :type="isLiked ? 'danger' : 'default'"
                  @click="handleToggleLike"
                >
                  <el-icon><component :is="isLiked ? 'StarFilled' : 'Star'" /></el-icon>
                  {{ isLiked ? '已点赞' : '点赞' }}
                </el-button>
                <el-button @click="handleShare" style="margin-left: 0">
                  <el-icon><Share /></el-icon>
                  分享
                </el-button>
                <!-- <el-button
                  type="primary"
                  @click="handleToTrip"
                  v-if="userStore.hasPermission('guides:write')"
                  style="margin-left: 0"
                >
                  <el-icon><Promotion /></el-icon>
                  生成行程
                </el-button> -->
                <el-button
                  v-if="canEdit"
                  @click="goToEdit"
                  style="margin-left: 0"
                >
                  <el-icon><Edit /></el-icon>
                  编辑
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <!-- 攻略内容 -->
      <el-card class="content-card">
        <template #header>
          <div class="card-header">
            <span>攻略详情</span>
          </div>
        </template>
        <div class="guide-summary" v-if="guide.summary">
          <h4>攻略简介</h4>
          <p>{{ guide.summary }}</p>
        </div>
        <div class="guide-body" v-html="renderContent"></div>
      </el-card>

      <!-- 评论区 -->
      <el-card class="comments-card">
        <template #header>
          <div class="card-header">
            <span>评论 ({{ totalComments }})</span>
          </div>
        </template>

        <!-- 发表评论 -->
        <div class="comment-form" v-if="userStore.userInfo.id">
          <el-input
            v-model="newComment"
            type="textarea"
            :rows="3"
            placeholder="写下你的评论..."
          />
          <div class="form-actions">
            <el-button type="primary" @click="handleSubmitComment" :loading="submittingComment">
              发表评论
            </el-button>
          </div>
        </div>

        <!-- 评论列表 -->
        <div class="comments-list">
          <el-empty v-if="comments.length === 0 && !commentsLoading" description="暂无评论" />
          <div v-else class="comment-item" v-for="comment in comments" :key="comment.id">
            <el-avatar :size="40" class="comment-avatar">
              {{ comment.user?.username?.charAt(0).toUpperCase() || 'U' }}
            </el-avatar>
            <div class="comment-content">
              <div class="comment-header">
                <span class="comment-author">{{ comment.user?.username || '匿名' }}</span>
                <span class="comment-time">{{ formatTime(comment.create_time) }}</span>
              </div>
              <p class="comment-text">{{ comment.content }}</p>
              <div class="comment-actions">
                <el-button text size="small" @click="handleReply(comment)">回复</el-button>
                <el-button
                  v-if="canDeleteComment(comment)"
                  text
                  size="small"
                  type="danger"
                  @click="handleDeleteComment(comment)"
                >
                  删除
                </el-button>
              </div>

              <!-- 子评论 -->
              <div class="replies" v-if="comment.replies && comment.replies.length > 0">
                <div class="reply-item" v-for="reply in comment.replies" :key="reply.id">
                  <el-avatar :size="28" class="reply-avatar">
                    {{ reply.user?.username?.charAt(0).toUpperCase() || 'U' }}
                  </el-avatar>
                  <div class="reply-content">
                    <div class="reply-header">
                      <span class="reply-author">{{ reply.user?.username || '匿名' }}</span>
                      <span class="reply-time">{{ formatTime(reply.create_time) }}</span>
                    </div>
                    <p class="reply-text">{{ reply.content }}</p>
                  </div>
                </div>
              </div>

              <!-- 回复输入框 -->
              <div class="reply-form" v-if="replyingTo === comment.id">
                <el-input
                  v-model="replyContent"
                  type="textarea"
                  :rows="2"
                  placeholder="回复评论..."
                />
                <div class="reply-actions">
                  <el-button size="small" @click="replyingTo = null">取消</el-button>
                  <el-button size="small" type="primary" @click="handleSubmitReply(comment.id)">
                    回复
                  </el-button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 评论分页 -->
        <div class="comments-pagination" v-if="totalComments > pageSize">
          <el-pagination
            v-model:current-page="commentPage"
            :page-size="pageSize"
            :total="totalComments"
            layout="prev, pager, next"
            @current-change="fetchComments"
          />
        </div>
      </el-card>
    </div>

    <!-- 生成行程对话框 -->
    <el-dialog
      v-model="toTripDialogVisible"
      title="生成行程规划"
      width="500px"
    >
      <el-form :model="tripForm" label-width="100px">
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="tripForm.start_date"
            type="date"
            placeholder="选择开始日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="tripForm.end_date"
            type="date"
            placeholder="选择结束日期"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="toTripDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmToTrip" :loading="generatingTrip">
          生成行程
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Location, Clock, Star, StarFilled, Share,
  Promotion, Edit
} from '@element-plus/icons-vue'
import { useUserStore } from '@/pinia/userStore'
import {
  getGuideDetail,
  checkLikeStatus,
  toggleLike,
  shareGuide,
  getGuideComments,
  createComment,
  deleteComment,
  guideToTrip
} from '@/api/guide'
import { marked } from 'marked'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loading = ref(false)
const guide = ref(null)
const isLiked = ref(false)
const comments = ref([])
const commentsLoading = ref(false)
const submittingComment = ref(false)
const newComment = ref('')
const replyingTo = ref(null)
const replyContent = ref('')
const commentPage = ref(1)
const pageSize = ref(20)
const totalComments = ref(0)
const toTripDialogVisible = ref(false)
const generatingTrip = ref(false)

const tripForm = reactive({
  start_date: '',
  end_date: ''
})

const canEdit = computed(() => {
  if (!guide.value) return false
  const isAdmin = userStore.userInfo.roles?.some(r => ['admin', 'guide_admin'].includes(r.name))
  const isAuthor = guide.value.author_id === userStore.userInfo.id
  return isAdmin || isAuthor
})

const renderContent = computed(() => {
  if (!guide.value) return ''
  if (guide.value.content_format === 'markdown') {
    return marked(guide.value.content)
  }
  return guide.value.content.replace(/\n/g, '<br>')
})

const fetchGuide = async () => {
  loading.value = true
  try {
    guide.value = await getGuideDetail(route.params.id, true)
    if (userStore.userInfo.id) {
      try {
        const likeRes = await checkLikeStatus(route.params.id)
        isLiked.value = likeRes.data?.is_liked || false
      } catch (e) {
        // 忽略点赞状态检查失败
      }
    }
    fetchComments()
  } catch (error) {
    ElMessage.error('获取攻略详情失败')
  } finally {
    loading.value = false
  }
}

const fetchComments = async () => {
  commentsLoading.value = true
  try {
    const res = await getGuideComments(route.params.id, {
      page_num: commentPage.value,
      page_size: pageSize.value
    })
    comments.value = res.data?.list || []
    totalComments.value = res.data?.total || 0
  } catch (error) {
    ElMessage.error('获取评论失败')
  } finally {
    commentsLoading.value = false
  }
}

const handleToggleLike = async () => {
  if (!userStore.userInfo.id) {
    ElMessage.warning('请先登录')
    return
  }
  try {
    const res = await toggleLike(route.params.id)
    isLiked.value = res.data?.is_liked || false
    guide.value.like_count = res.data?.like_count || guide.value.like_count
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const handleShare = async () => {
  try {
    // 复制当前页面链接
    const url = window.location.href

    // 先尝试使用现代 clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(url)
    } else {
      // 降级方案：使用传统的 document.execCommand
      const textarea = document.createElement('textarea')
      textarea.value = url
      textarea.style.position = 'fixed'
      textarea.style.left = '-9999px'
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }

    // 调用分享统计 API
    await shareGuide(route.params.id)
    guide.value.share_count++

    ElMessage.success('链接已复制到剪贴板')
  } catch (error) {
    console.error('分享失败:', error)
    ElMessage.error('分享失败，请重试')
  }
}

const handleToTrip = () => {
  toTripDialogVisible.value = true
}

const confirmToTrip = async () => {
  if (!tripForm.start_date || !tripForm.end_date) {
    ElMessage.warning('请选择日期')
    return
  }
  generatingTrip.value = true
  try {
    const res = await guideToTrip(route.params.id, tripForm)
    sessionStorage.setItem('tripPlan', JSON.stringify(res.data))
    ElMessage.success('行程生成成功')
    toTripDialogVisible.value = false
    router.push('/trip/result')
  } catch (error) {
    ElMessage.error('行程生成失败')
  } finally {
    generatingTrip.value = false
  }
}

const handleSubmitComment = async () => {
  if (!newComment.value.trim()) {
    ElMessage.warning('请输入评论内容')
    return
  }
  submittingComment.value = true
  try {
    await createComment(route.params.id, { content: newComment.value })
    ElMessage.success('评论成功')
    newComment.value = ''
    fetchComments()
  } catch (error) {
    ElMessage.error('评论失败')
  } finally {
    submittingComment.value = false
  }
}

const handleReply = (comment) => {
  replyingTo.value = comment.id
  replyContent.value = ''
}

const handleSubmitReply = async (parentId) => {
  if (!replyContent.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  try {
    await createComment(route.params.id, {
      content: replyContent.value,
      parent_id: parentId
    })
    ElMessage.success('回复成功')
    replyingTo.value = null
    replyContent.value = ''
    fetchComments()
  } catch (error) {
    ElMessage.error('回复失败')
  }
}

const canDeleteComment = (comment) => {
  const isAdmin = userStore.userInfo.roles?.some(r => ['admin', 'guide_admin'].includes(r.name))
  const isAuthor = comment.user_id === userStore.userInfo.id
  return isAdmin || isAuthor
}

const handleDeleteComment = async (comment) => {
  try {
    await ElMessageBox.confirm('确定要删除这条评论吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteComment(comment.id)
    ElMessage.success('删除成功')
    fetchComments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const goBack = () => {
  router.push('/guides')
}

const goToEdit = () => {
  router.push(`/guide/edit/${guide.value.id}`)
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleDateString('zh-CN')
}

onMounted(() => {
  fetchGuide()
})
</script>

<style scoped>
.guide-detail-container {
  padding: 24px;
  background: #f5f7fa;
  max-width: 1000px;
  margin: 0 auto;
  overflow-y: auto;
  height: 100vh;
  box-sizing: border-box;
}

.header-nav {
  margin-bottom: 16px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.header-card,
.content-card,
.comments-card {
  border-radius: 12px;
}

.card-header {
  font-size: 16px;
  font-weight: 600;
}

.guide-header {
  padding: 8px 0;
}

.header-top {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}

.title-section {
  flex: 1;
  min-width: 300px;
}

.guide-tags {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.tag-item {
  margin: 0;
}

.guide-title {
  margin: 0 0 16px 0;
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  line-height: 1.4;
}

.guide-meta {
  display: flex;
  gap: 20px;
  align-items: center;
}

.city-info,
.time-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #606266;
  font-size: 14px;
}

.author-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.author-name {
  font-size: 14px;
  color: #606266;
}

.action-section {
  width: 280px;
  flex-shrink: 0;
}

.stats-card {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px;
  background: #409eff;
  border-radius: 12px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  color: #fff;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  opacity: 0.9;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-buttons .el-button {
  width: 100%;
}

.guide-summary {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 24px;
}

.guide-summary h4 {
  margin: 0 0 8px 0;
  color: #606266;
}

.guide-summary p {
  margin: 0;
  color: #606266;
  line-height: 1.8;
}

.guide-body {
  font-size: 16px;
  line-height: 1.8;
  color: #303133;
}

.guide-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

.comment-form {
  margin-bottom: 24px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.comments-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.comment-item {
  display: flex;
  gap: 12px;
}

.comment-avatar {
  flex-shrink: 0;
}

.comment-content {
  flex: 1;
}

.comment-header {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.comment-author {
  font-weight: 600;
  color: #303133;
}

.comment-time {
  font-size: 12px;
  color: #909399;
}

.comment-text {
  margin: 0 0 8px 0;
  color: #606266;
  line-height: 1.6;
}

.comment-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.replies {
  padding-left: 12px;
  border-left: 2px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reply-item {
  display: flex;
  gap: 8px;
}

.reply-avatar {
  flex-shrink: 0;
}

.reply-content {
  flex: 1;
}

.reply-header {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
}

.reply-author {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.reply-time {
  font-size: 12px;
  color: #909399;
}

.reply-text {
  margin: 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.reply-form {
  margin-top: 12px;
}

.reply-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.comments-pagination {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
