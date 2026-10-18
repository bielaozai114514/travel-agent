<template>
  <div class="guide-editor-container">
    <div class="editor-header">
      <div class="header-left">
        <el-button text @click="goBack">
          <el-icon><ArrowLeft /></el-icon>
          取消
        </el-button>
        <h1 class="page-title">{{ isEdit ? '编辑攻略' : '发布新攻略' }}</h1>
      </div>
      <div class="header-right">
        <el-button @click="handleSaveDraft" :loading="saving">
          保存草稿
        </el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          <el-icon><Check /></el-icon>
          {{ isEdit ? '提交审核' : '发布攻略' }}
        </el-button>
      </div>
    </div>

    <div class="editor-content">
      <!-- 左侧表单区 -->
      <div class="form-section">
        <el-card class="form-card">
          <el-form
            ref="formRef"
            :model="formData"
            :rules="formRules"
            label-width="100px"
          >
            <el-form-item label="攻略标题" prop="title">
              <el-input
                v-model="formData.title"
                placeholder="请输入攻略标题"
                maxlength="100"
                show-word-limit
              />
            </el-form-item>

            <el-form-item label="目的地城市" prop="city">
              <el-input
                v-model="formData.city"
                placeholder="例如：杭州"
                maxlength="50"
              />
            </el-form-item>

            <el-form-item label="攻略标签">
              <el-select
                v-model="formData.tags"
                multiple
                placeholder="选择标签（可多选）"
                style="width: 100%"
                allow-create
              >
                <el-option label="亲子游" value="亲子游" />
                <el-option label="情侣游" value="情侣游" />
                <el-option label="自驾游" value="自驾游" />
                <el-option label="背包客" value="背包客" />
                <el-option label="摄影" value="摄影" />
                <el-option label="美食" value="美食" />
                <el-option label="历史文化" value="历史文化" />
                <el-option label="自然风光" value="自然风光" />
                <el-option label="休闲度假" value="休闲度假" />
                <el-option label="探险" value="探险" />
              </el-select>
            </el-form-item>

            <el-form-item label="攻略简介">
              <el-input
                v-model="formData.summary"
                type="textarea"
                :rows="3"
                placeholder="简要介绍这篇攻略的内容"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>

            <el-form-item label="内容格式">
              <el-radio-group v-model="formData.content_format">
                <el-radio label="plain">纯文本</el-radio>
                <el-radio label="markdown">Markdown</el-radio>
              </el-radio-group>
            </el-form-item>
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #f0f0f0;">
              <el-button type="primary" @click="openAIGenerator" style="width: 100%;">
                <el-icon><MagicStick /></el-icon>
                AI生成攻略
              </el-button>
            </div>
          </el-form>
        </el-card>
      </div>

      <!-- 右侧编辑区 -->
      <div class="edit-section">
        <el-card class="edit-card">
          <template #header>
            <div class="card-header">
              <el-radio-group v-model="editMode" size="small">
                <el-radio-button value="edit">编辑</el-radio-button>
                <el-radio-button value="preview">预览</el-radio-button>
                <el-radio-button value="split">分屏</el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <div class="editor-wrapper">
            <!-- 编辑模式 -->
            <div
              v-if="editMode !== 'preview'"
              class="editor-pane"
              :class="{ 'half-width': editMode === 'split' }"
            >
              <el-input
                v-model="formData.content"
                type="textarea"
                placeholder="在这里写下你的攻略内容..."
                :rows="20"
                resize="none"
                class="content-editor"
              />
              <div class="editor-toolbar" v-if="formData.content_format === 'markdown'">
                <span class="toolbar-hint">
                  <el-icon><InfoFilled /></el-icon>
                  支持 Markdown 格式
                </span>
              </div>
            </div>

            <!-- 预览模式 -->
            <div
              v-if="editMode !== 'edit'"
              class="preview-pane"
              :class="{ 'half-width': editMode === 'split' }"
            >
              <div class="preview-content" v-html="renderedContent"></div>
              <el-empty v-if="!formData.content" description="暂无内容，快去编辑吧~" />
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 草稿选择对话框 -->
    <el-dialog
      v-model="draftDialogVisible"
      title="发现未完成的攻略"
      width="600px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <p>你有以下未完成的攻略，是否继续编辑？</p>
      <div class="draft-list">
        <div
          v-for="guide in unpublishedGuides"
          :key="guide.id"
          class="draft-item"
          @click="selectDraft(guide)"
        >
          <div class="draft-info">
            <div class="draft-title">{{ guide.title }}</div>
            <div class="draft-meta">
              <el-tag size="small" :type="getStatusType(guide.status)">
                {{ getStatusText(guide.status) }}
              </el-tag>
              <span class="draft-city">{{ guide.city }}</span>
              <span class="draft-time">{{ formatTime(guide.update_time) }}</span>
            </div>
          </div>
          <el-icon class="draft-arrow"><ArrowRight /></el-icon>
        </div>
      </div>
      <template #footer>
        <el-button @click="continueNew">创建新攻略</el-button>
      </template>
    </el-dialog>

    <!-- AI生成攻略对话框 -->
    <el-dialog
      v-model="aiDialogVisible"
      title="AI生成攻略"
      width="500px"
    >
      <el-form :model="aiForm" label-width="100px">
        <el-form-item label="目的地城市">
          <el-input v-model="aiForm.city" placeholder="请输入城市" />
        </el-form-item>
        <el-form-item label="游玩天数">
          <el-select v-model="aiForm.days" placeholder="请选择天数">
            <el-option v-for="n in 7" :key="n" :label="`${n}天`" :value="n" />
          </el-select>
        </el-form-item>
        <el-form-item label="游玩风格">
          <el-select v-model="aiForm.tags" multiple placeholder="选择标签（可多选）" style="width: 100%;">
            <el-option label="亲子游" value="亲子游" />
            <el-option label="情侣游" value="情侣游" />
            <el-option label="自驾游" value="自驾游" />
            <el-option label="背包客" value="背包客" />
            <el-option label="摄影" value="摄影" />
            <el-option label="美食" value="美食" />
            <el-option label="历史文化" value="历史文化" />
            <el-option label="自然风光" value="自然风光" />
            <el-option label="休闲度假" value="休闲度假" />
            <el-option label="探险" value="探险" />
          </el-select>
        </el-form-item>
        <el-form-item label="预算范围">
          <el-select v-model="aiForm.budget" placeholder="请选择预算">
            <el-option label="经济" value="经济" />
            <el-option label="中等" value="中等" />
            <el-option label="高端" value="高端" />
          </el-select>
        </el-form-item>
        <el-form-item label="额外要求">
          <el-input
            v-model="aiForm.extra_requirements"
            type="textarea"
            :rows="3"
            placeholder="有什么额外的要求..."
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleGenerateGuide" :loading="generating">
          生成攻略
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Check, InfoFilled, ArrowRight, MagicStick } from '@element-plus/icons-vue'
import { getGuideDetail, createGuide, updateGuide, getMyUnpublishedGuides, generateGuide } from '@/api/guide'
import { marked } from 'marked'

const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const saving = ref(false)
const submitting = ref(false)
const editMode = ref('split')
const isEdit = computed(() => !!route.params.id)
const unpublishedGuides = ref([])
const draftDialogVisible = ref(false)

const formData = reactive({
  title: '',
  city: '',
  tags: [],
  summary: '',
  content: '',
  content_format: 'markdown',
  status: 'draft',
  is_ai_generated: false
})

// AI生成对话框
const aiDialogVisible = ref(false)
const generating = ref(false)
const aiForm = reactive({
  city: '',
  days: 2,
  tags: [],
  budget: '中等',
  extra_requirements: ''
})

// 打开AI生成对话框
const openAIGenerator = () => {
  aiForm.city = formData.city || ''
  aiForm.tags = [...(formData.tags || [])]
  aiDialogVisible.value = true
}

// 执行AI生成
const handleGenerateGuide = async () => {
  if (!aiForm.city) {
    ElMessage.warning('请输入目的地城市')
    return
  }

  generating.value = true
  try {
    const res = await generateGuide(aiForm)
    // 填充到表单
    const data = res.data
    formData.title = data.title
    formData.city = data.city  // 填充城市
    formData.summary = data.summary
    formData.content = data.content
    formData.tags = data.tags
    // 标记为AI生成
    formData.is_ai_generated = true

    ElMessage.success('AI生成攻略成功')
    aiDialogVisible.value = false
  } catch (error) {
    ElMessage.error('AI生成失败，请重试')
  } finally {
    generating.value = false
  }
}

const formRules = {
  title: [
    { required: true, message: '请输入攻略标题', trigger: 'blur' },
    { min: 5, max: 100, message: '标题长度在 5 到 100 个字符', trigger: 'blur' }
  ],
  city: [
    { required: true, message: '请输入目的地城市', trigger: 'blur' }
  ]
}

const renderedContent = computed(() => {
  if (!formData.content) return ''
  if (formData.content_format === 'markdown') {
    return marked(formData.content)
  }
  return formData.content.replace(/\n/g, '<br>')
})

const fetchGuide = async () => {
  try {
    const guide = await getGuideDetail(route.params.id, false)
    formData.title = guide.title || ''
    formData.city = guide.city || ''
    formData.tags = guide.tags || []
    formData.summary = guide.summary || ''
    formData.content = guide.content || ''
    formData.content_format = guide.content_format || 'markdown'
  } catch (error) {
    ElMessage.error('获取攻略详情失败')
    router.push('/guides')
  }
}

const fetchUnpublishedGuides = async () => {
  try {
    const res = await getMyUnpublishedGuides()
    unpublishedGuides.value = res.data?.items || []
  } catch (error) {
    console.error('获取未发布攻略失败', error)
  }
}

const selectDraft = (guide) => {
  draftDialogVisible.value = false
  router.push(`/guide/edit/${guide.id}`)
}

const continueNew = () => {
  draftDialogVisible.value = false
}

const getStatusType = (status) => {
  const typeMap = {
    draft: 'info',
    pending: 'warning',
    rejected: 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    draft: '草稿',
    pending: '待审核',
    rejected: '已拒绝'
  }
  return textMap[status] || status
}

const formatTime = (time) => {
  if (!time) return ''
  const date = new Date(time)
  return date.toLocaleString('zh-CN')
}

const handleSaveDraft = async () => {
  saving.value = true
  try {
    if (isEdit.value) {
      await updateGuide(route.params.id, {
        ...formData,
        status: 'draft'
      })
      ElMessage.success('草稿保存成功')
    } else {
      await createGuide({
        ...formData,
        status: 'draft'
      })
      ElMessage.success('草稿保存成功')
      router.push('/guides')
    }
  } catch (error) {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    if (!formData.content || formData.content.length < 50) {
      ElMessage.warning('攻略内容至少需要50个字符')
      return
    }

    submitting.value = true
    try {
      if (isEdit.value) {
        await updateGuide(route.params.id, {
          ...formData,
          status: 'pending'
        })
        ElMessage.success('攻略更新成功，已提交审核')
      } else {
        await createGuide({
          ...formData,
          status: 'pending'
        })
        ElMessage.success('攻略发布成功，已提交审核')
      }
      router.push('/guides')
    } catch (error) {
      ElMessage.error('发布失败')
    } finally {
      submitting.value = false
    }
  })
}

const goBack = () => {
  if (isEdit.value) {
    router.push(`/guide/${route.params.id}`)
  } else {
    router.push('/guides')
  }
}

onMounted(async () => {
  if (isEdit.value) {
    fetchGuide()
  } else {
    // 检查是否有未发布的攻略
    await fetchUnpublishedGuides()
    if (unpublishedGuides.value.length > 0) {
      draftDialogVisible.value = true
    }
  }
})
</script>

<style scoped>
.guide-editor-container {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
  flex-direction: column;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  gap: 12px;
}

.editor-content {
  flex: 1;
  padding: 24px;
  display: grid;
  grid-template-columns: 400px 1fr;
  gap: 20px;
  overflow-y: auto;
}

.form-section,
.edit-section {
  display: flex;
  flex-direction: column;
}

.form-card,
.edit-card {
  border-radius: 12px;
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: flex-end;
}

.editor-wrapper {
  display: flex;
  height: calc(100vh - 220px);
  min-height: 500px;
}

.editor-pane,
.preview-pane {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.half-width {
  flex: 1;
  border-right: 1px solid #e4e7ed;
}

.preview-pane.half-width {
  border-right: none;
}

.content-editor {
  flex: 1;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
}

.content-editor :deep(textarea) {
  height: 100% !important;
  resize: none;
}

.editor-toolbar {
  padding: 8px 12px;
  background: #f5f7fa;
  border-top: 1px solid #e4e7ed;
}

.toolbar-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;
}

.preview-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  line-height: 1.8;
  color: #303133;
}

.preview-content :deep(h1),
.preview-content :deep(h2),
.preview-content :deep(h3) {
  margin-top: 24px;
  margin-bottom: 12px;
  font-weight: 600;
}

.preview-content :deep(h1) {
  font-size: 24px;
}

.preview-content :deep(h2) {
  font-size: 20px;
}

.preview-content :deep(h3) {
  font-size: 18px;
}

.preview-content :deep(p) {
  margin-bottom: 16px;
}

.preview-content :deep(ul),
.preview-content :deep(ol) {
  margin-bottom: 16px;
  padding-left: 24px;
}

.preview-content :deep(li) {
  margin-bottom: 8px;
}

.preview-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 13px;
}

.preview-content :deep(pre) {
  background: #1a1f2e;
  color: #fff;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 16px;
}

.preview-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.preview-content :deep(blockquote) {
  border-left: 4px solid #667eea;
  padding-left: 16px;
  margin: 16px 0;
  color: #606266;
}

.preview-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

.preview-content :deep(a) {
  color: #667eea;
  text-decoration: none;
}

.preview-content :deep(a:hover) {
  text-decoration: underline;
}

/* 草稿列表样式 */
.draft-list {
  max-height: 400px;
  overflow-y: auto;
}

.draft-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  margin-bottom: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.draft-item:hover {
  background: #e6f7ff;
  transform: translateX(4px);
}

.draft-info {
  flex: 1;
}

.draft-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.draft-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.draft-city {
  font-size: 14px;
  color: #667eea;
}

.draft-time {
  font-size: 13px;
  color: #909399;
}

.draft-arrow {
  color: #c0c4cc;
  font-size: 18px;
}

@media (max-width: 1200px) {
  .editor-content {
    grid-template-columns: 1fr;
  }
}
</style>
