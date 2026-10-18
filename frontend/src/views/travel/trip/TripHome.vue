<template>
  <div class="trip-home-container">
    <div class="page-header">
      <div class="icon-wrapper">
        <el-icon size="64"><Compass /></el-icon>
      </div>
      <h1 class="page-title">智能旅游助手</h1>
      <p class="page-subtitle">基于AI的个性化旅游规划,让每一次出行都完美无忧</p>
    </div>

    <el-card class="form-card" :body-style="{ padding: '32px' }">
      <el-form :model="formData" label-position="top" @submit.prevent="handleSubmit">
        <div class="form-section">
          <div class="section-header">
            <el-icon size="24"><Location /></el-icon>
            <span class="section-title">目的地与日期</span>
          </div>

          <el-row :gutter="24">
            <el-col :span="8">
              <el-form-item label="目的地城市" required>
                <el-input
                  v-model="formData.city"
                  placeholder="例如: 北京"
                  size="large"
                  :prefix-icon="MapLocation"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="开始日期" required>
                <el-date-picker
                  v-model="formData.start_date"
                  type="date"
                  placeholder="选择日期"
                  size="large"
                  style="width: 100%"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="结束日期" required>
                <el-date-picker
                  v-model="formData.end_date"
                  type="date"
                  placeholder="选择日期"
                  size="large"
                  style="width: 100%"
                  format="YYYY-MM-DD"
                  value-format="YYYY-MM-DD"
                />
              </el-form-item>
            </el-col>
            <el-col :span="4">
              <el-form-item label="旅游天数">
                <div class="days-display">
                  <span class="days-value">{{ formData.travel_days }}</span>
                  <span class="days-unit">天</span>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-header">
            <el-icon size="24"><Setting /></el-icon>
            <span class="section-title">偏好设置</span>
          </div>

          <el-row :gutter="24">
            <el-col :span="8">
              <el-form-item label="交通方式">
                <el-select v-model="formData.transportation" size="large" style="width: 100%">
                  <el-option label="🚌 公共交通" value="公共交通" />
                  <el-option label="🚗 自驾" value="自驾" />
                  <el-option label="🚶 步行" value="步行" />
                  <el-option label="🔀 混合" value="混合" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="住宿偏好">
                <el-select v-model="formData.accommodation" size="large" style="width: 100%">
                  <el-option label="经济型酒店" value="经济型酒店" />
                  <el-option label="舒适型酒店" value="舒适型酒店" />
                  <el-option label="豪华酒店" value="豪华酒店" />
                  <el-option label="民宿" value="民宿" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="旅游偏好">
                <el-checkbox-group v-model="formData.preferences" class="preference-tags">
                  <el-checkbox-button value="历史文化">历史文化</el-checkbox-button>
                  <el-checkbox-button value="自然风光">自然风光</el-checkbox-button>
                  <el-checkbox-button value="美食">美食</el-checkbox-button>
                  <el-checkbox-button value="购物">购物</el-checkbox-button>
                  <el-checkbox-button value="艺术">艺术</el-checkbox-button>
                  <el-checkbox-button value="休闲">休闲</el-checkbox-button>
                </el-checkbox-group>
              </el-form-item>
            </el-col>
          </el-row>
        </div>

        <div class="form-section">
          <div class="section-header">
            <el-icon size="24"><ChatDotRound /></el-icon>
            <span class="section-title">额外要求</span>
          </div>

          <el-form-item>
            <el-input
              v-model="formData.free_text_input"
              type="textarea"
              :rows="3"
              placeholder="请输入您的额外要求,例如:想去看升旗、需要无障碍设施、对海鲜过敏等..."
              size="large"
            />
          </el-form-item>
        </div>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="submit-button"
            @click="handleSubmit"
          >
            <template v-if="!loading">
              <el-icon><Promotion /></el-icon>
              <span>开始规划我的旅游</span>
            </template>
            <template v-else>
              <span>正在生成中...</span>
            </template>
          </el-button>
        </el-form-item>

        <el-form-item v-if="loading">
          <div class="loading-container">
            <el-progress
              :percentage="loadingProgress"
              :stroke-width="10"
              :color="progressColors"
            />
            <p class="loading-status">{{ loadingStatus }}</p>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Compass,
  Location,
  MapLocation,
  Setting,
  ChatDotRound,
  Promotion
} from '@element-plus/icons-vue'
import { generateTripPlanBackground } from '@/api/trip'

const router = useRouter()
const loading = ref(false)
const loadingProgress = ref(0)
const loadingStatus = ref('')

const formData = reactive({
  city: '',
  start_date: '',
  end_date: '',
  travel_days: 1,
  transportation: '公共交通',
  accommodation: '经济型酒店',
  preferences: [],
  free_text_input: ''
})

const progressColors = [
  { color: '#409eff', percentage: 30 },
  { color: '#66b1ff', percentage: 70 },
  { color: '#f56c6c', percentage: 100 }
]

watch([() => formData.start_date, () => formData.end_date], ([start, end]) => {
  if (start && end) {
    const startDate = new Date(start)
    const endDate = new Date(end)
    const days = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1
    if (days > 0 && days <= 30) {
      formData.travel_days = days
    } else if (days > 30) {
      ElMessage.warning('旅游天数不能超过30天')
      formData.end_date = ''
    } else {
      ElMessage.warning('结束日期不能早于开始日期')
      formData.end_date = ''
    }
  }
})

const handleSubmit = async () => {
  if (!formData.city || !formData.start_date || !formData.end_date) {
    ElMessage.error('请填写完整的目的地和日期信息')
    return
  }

  loading.value = true
  loadingProgress.value = 0
  loadingStatus.value = '正在初始化...'

  try {
    const response = await generateTripPlanBackground(formData)

    if (response.success && response.data) {
      ElMessage.success('已开始后台规划行程，您可以在左侧列表查看进度！')

      // 清除进度条，恢复初始状态
      setTimeout(() => {
        loading.value = false
        loadingProgress.value = 0
        loadingStatus.value = ''
      }, 1000)
    } else {
      throw new Error(response.message || '创建任务失败')
    }

  } catch (error) {
    ElMessage.error(error.message || '生成旅游计划失败,请稍后重试')
    loading.value = false
    loadingProgress.value = 0
    loadingStatus.value = ''
  }
}
</script>

<style scoped>
.trip-home-container {
  height: 100%;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 40px 20px;
}

.page-header {
  text-align: center;
  margin-bottom: 40px;
}

.icon-wrapper {
  width: 80px;
  height: 80px;
  background: #409eff;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  color: #fff;
}

.page-title {
  font-size: 36px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 12px;
  letter-spacing: 1px;
}

.page-subtitle {
  font-size: 16px;
  color: #909399;
  margin: 0;
}

.form-card {
  max-width: 1000px;
  margin: 0 auto;
  border-radius: 12px;
}

.form-section {
  margin-bottom: 24px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.section-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 10px;
  border-bottom: 2px solid #409eff;
  color: #409eff;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-left: 10px;
}

.days-display {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 8px 16px;
  background: #409eff;
  border-radius: 8px;
  color: white;
}

.days-value {
  font-size: 20px;
  font-weight: 700;
  margin-right: 4px;
}

.days-unit {
  font-size: 14px;
}

.preference-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.submit-button {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  background: #409eff;
  border: none;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.submit-button:hover {
  background: #66b1ff;
}

.loading-container {
  text-align: center;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 2px dashed #409eff;
}

.loading-status {
  margin-top: 12px;
  color: #409eff;
  font-size: 16px;
  font-weight: 500;
}
</style>
