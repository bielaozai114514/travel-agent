<template>
  <div class="trip-result-container">
    <div class="page-header">
      <el-button class="back-button" size="large" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回规划
      </el-button>
      <el-space size="middle">
        <el-button type="success" v-if="!editMode" @click="openConversation">
          <el-icon><ChatDotRound /></el-icon>
          打开对话
        </el-button>
        <!-- <el-button v-if="!editMode" @click="toggleEditMode">
          <el-icon><Edit /></el-icon>
          编辑行程
        </el-button> -->
        <el-button v-else type="primary" @click="saveChanges">
          <el-icon><Check /></el-icon>
          保存修改
        </el-button>
        <el-button v-if="editMode" @click="cancelEdit">
          <el-icon><Close /></el-icon>
          取消编辑
        </el-button>
        <el-button type="danger" v-if="tripPlanId && !editMode" @click="handleDelete">
          <el-icon><Delete /></el-icon>
          删除
        </el-button>

        <el-dropdown v-if="!editMode">
          <template #dropdown>
            <el-menu>
              <el-menu-item @click="exportAsImage">
                <el-icon><Picture /></el-icon>
                导出为图片
              </el-menu-item>
              <el-menu-item @click="exportAsPDF">
                <el-icon><Document /></el-icon>
                导出为PDF
              </el-menu-item>
            </el-menu>
          </template>
          <el-button>
            <el-icon><Download /></el-icon>
            导出行程
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
        </el-dropdown>
      </el-space>
    </div>

    <div v-if="tripPlan" class="content-scroll-area" ref="contentScrollAreaRef">
      <div class="content-wrapper">
        <div class="side-nav">
          <el-menu :default-active="activeSection" @select="scrollToSection">
            <el-menu-item index="overview">
              <el-icon><Document /></el-icon>
              <span>行程概览</span>
            </el-menu-item>
            <el-menu-item index="budget" v-if="tripPlan.budget">
              <el-icon><Wallet /></el-icon>
              <span>预算明细</span>
            </el-menu-item>
            <el-menu-item index="map">
              <el-icon><Location /></el-icon>
              <span>景点地图</span>
            </el-menu-item>
            <el-sub-menu index="days">
              <template #title>
                <el-icon><Calendar /></el-icon>
                <span>每日行程</span>
              </template>
              <el-menu-item
                v-for="(day, index) in tripPlan.days"
                :key="`day-${index}`"
                :index="`day-${index}`"
              >
                第{{ day.day_index + 1}}天
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item index="weather" v-if="tripPlan.weather_info && tripPlan.weather_info.length > 0">
              <el-icon><Cloudy /></el-icon>
              <span>天气信息</span>
            </el-menu-item>
          </el-menu>
        </div>

        <div class="main-content" ref="mainContentRef">
          <div class="top-info-section">
            <div class="left-info">
              <el-card id="overview" class="overview-card">
                <template #header>
                  <div class="card-header">
                    <el-icon><Location /></el-icon>
                    <span>{{ tripPlan.city }}旅游计划</span>
                  </div>
                </template>
                <div class="overview-content">
                  <div class="info-item">
                    <span class="info-label">日期:</span>
                    <span class="info-value">{{ tripPlan.start_date }} 至 {{ tripPlan.end_date }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">建议:</span>
                    <span class="info-value">{{ tripPlan.overall_suggestions }}</span>
                  </div>
                </div>
              </el-card>

              <el-card id="budget" v-if="tripPlan.budget" class="budget-card">
                <template #header>
                  <div class="card-header">
                    <el-icon><Wallet /></el-icon>
                    <span>预算明细</span>
                  </div>
                </template>
                <div class="budget-grid">
                  <div class="budget-item">
                    <div class="budget-label">景点门票</div>
                    <div class="budget-value">¥{{ tripPlan.budget.total_attractions }}</div>
                  </div>
                  <div class="budget-item">
                    <div class="budget-label">酒店住宿</div>
                    <div class="budget-value">¥{{ tripPlan.budget.total_hotels }}</div>
                  </div>
                  <div class="budget-item">
                    <div class="budget-label">餐饮费用</div>
                    <div class="budget-value">¥{{ tripPlan.budget.total_meals }}</div>
                  </div>
                  <div class="budget-item">
                    <div class="budget-label">交通费用</div>
                    <div class="budget-value">¥{{ tripPlan.budget.total_transportation }}</div>
                  </div>
                </div>
                <div class="budget-total">
                  <span class="total-label">预估总费用</span>
                  <span class="total-value">¥{{ tripPlan.budget.total }}</span>
                </div>
              </el-card>
            </div>

            <div class="right-map">
              <el-card id="map" class="map-card">
                <template #header>
                  <div class="card-header">
                    <el-icon><Location /></el-icon>
                    <span>景点地图</span>
                  </div>
                </template>
                <div id="amap-container" class="map-container"></div>
              </el-card>
            </div>
          </div>

          <el-card class="days-card">
            <template #header>
              <div class="card-header">
                <el-icon><Calendar /></el-icon>
                <span>每日行程</span>
              </div>
            </template>
            <el-collapse v-model="activeDays">
              <el-collapse-item
                v-for="(day, index) in tripPlan.days"
                :key="index"
                :name="index"
                :id="`day-${index}`"
              >
                <template #title>
                  <div class="day-header">
                    <span class="day-title">第{{ day.day_index + 1}}天</span>
                    <span class="day-date">{{ day.date }}</span>
                  </div>
                </template>

                <div class="day-info">
                  <div class="info-row">
                    <span class="label">行程描述:</span>
                    <span class="value">{{ day.description }}</span>
                  </div>
                  <div class="info-row">
                    <span class="label">交通方式:</span>
                    <span class="value">{{ day.transportation }}</span>
                  </div>
                  <div class="info-row">
                    <span class="label">住宿:</span>
                    <span class="value">{{ day.accommodation }}</span>
                  </div>
                </div>

                <el-divider content-position="left">🎯 景点安排</el-divider>
                <el-row :gutter="16">
                  <el-col
                    :span="12"
                    v-for="(attraction, attrIndex) in day.attractions"
                    :key="attrIndex"
                  >
                    <el-card class="attraction-card" :body-style="{ padding: '16px' }">
                      <template #header>
                        <div class="attraction-header">
                          <span class="attraction-badge-small">{{ attrIndex + 1 }}</span>
                          <span class="attraction-name">{{ attraction.name }}</span>
                          <span class="price-tag" v-if="attraction.ticket_price">
                            ¥{{ attraction.ticket_price }}
                          </span>
                        </div>
                      </template>

                      <div v-if="editMode">
                        <el-form-item label="地址">
                          <el-input v-model="attraction.address" size="small" />
                        </el-form-item>
                        <el-form-item label="游览时长(分钟)">
                          <el-input-number v-model="attraction.visit_duration" :min="10" :max="480" size="small" style="width: 100%" />
                        </el-form-item>
                        <el-form-item label="描述">
                          <el-input v-model="attraction.description" type="textarea" :rows="2" size="small" />
                        </el-form-item>
                      </div>

                      <div v-else class="attraction-info">
                        <p><strong>地址:</strong> {{ attraction.address }}</p>
                        <p><strong>游览时长:</strong> {{ attraction.visit_duration }}分钟</p>
                        <p><strong>描述:</strong> {{ attraction.description }}</p>
                        <p v-if="attraction.rating"><strong>评分:</strong> {{ attraction.rating }}⭐</p>
                      </div>
                    </el-card>
                  </el-col>
                </el-row>

                  <el-divider v-if="day.hotel" content-position="left">🏨 住宿推荐</el-divider>
                  <el-card v-if="day.hotel" class="hotel-card">
                    <template #header>
                      <div class="hotel-header">
                        <span class="hotel-title">{{ day.hotel.name }}</span>
                        <span class="hotel-rating" v-if="day.hotel.rating">{{ day.hotel.rating }}⭐</span>
                      </div>
                    </template>
                    <div class="hotel-info-grid">
                      <div class="hotel-info-item">
                        <div class="hotel-info-content">
                          <span class="hotel-info-label">地址</span>
                          <span class="hotel-info-value">{{ day.hotel.address }}</span>
                        </div>
                      </div>
                      <div class="hotel-info-item">
                        <div class="hotel-info-content">
                          <span class="hotel-info-label">类型</span>
                          <span class="hotel-info-value">{{ day.hotel.type }}</span>
                        </div>
                      </div>
                      <div class="hotel-info-item">
                        <div class="hotel-info-content">
                          <span class="hotel-info-label">价格范围</span>
                          <span class="hotel-info-value price-highlight">{{ day.hotel.price_range }}</span>
                        </div>
                      </div>
                      <div class="hotel-info-item">
                        <div class="hotel-info-content">
                          <span class="hotel-info-label">距离</span>
                          <span class="hotel-info-value">{{ day.hotel.distance }}</span>
                        </div>
                      </div>
                    </div>
                  </el-card>

                <el-divider content-position="left">🍽️ 餐饮安排</el-divider>
                <el-descriptions :column="1" border size="small">
                  <el-descriptions-item
                    v-for="meal in day.meals"
                    :key="meal.type"
                    :label="getMealLabel(meal.type)"
                  >
                    {{ meal.name }}
                    <span v-if="meal.description"> - {{ meal.description }}</span>
                    <span v-if="meal.estimated_cost" class="meal-cost"> (约¥{{ meal.estimated_cost }})</span>
                  </el-descriptions-item>
                </el-descriptions>
              </el-collapse-item>
            </el-collapse>
          </el-card>

          <el-card id="weather" v-if="tripPlan.weather_info && tripPlan.weather_info.length > 0" class="weather-card">
            <template #header>
              <div class="card-header">
                <el-icon><Cloudy /></el-icon>
                <span>天气信息</span>
              </div>
            </template>
            <el-row :gutter="16">
              <el-col
                :span="8"
                v-for="(weather, index) in tripPlan.weather_info"
                :key="index"
              >
                <el-card class="weather-item" :body-style="{ padding: '16px' }">
                  <div class="weather-date">{{ weather.date }}</div>
                  <div class="weather-info-row">
                    <el-icon size="24"><Sunny /></el-icon>
                    <div>
                      <div class="weather-label">白天</div>
                      <div class="weather-value">{{ weather.day_weather }} {{ weather.day_temp }}°C</div>
                    </div>
                  </div>
                  <div class="weather-info-row">
                    <el-icon size="24"><Moon /></el-icon>
                    <div>
                      <div class="weather-label">夜间</div>
                      <div class="weather-value">{{ weather.night_weather }} {{ weather.night_temp }}°C</div>
                    </div>
                  </div>
                  <div class="weather-wind">
                    💨 {{ weather.wind_direction }} {{ weather.wind_power }}
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </el-card>
        </div>
      </div>
    </div>

    <el-empty v-else description="没有找到旅游计划数据">
      <template #image>
        <el-icon size="80"><MapLocation /></el-icon>
      </template>
      <el-button type="primary" @click="goBack">返回规划页面</el-button>
    </el-empty>

    <el-backtop :visibility-height="300">
      <div class="back-top-button">↑</div>
    </el-backtop>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Edit,
  Check,
  Close,
  Delete,
  Location,
  Wallet,
  Calendar,
  Cloudy,
  Sunny,
  Moon,
  MapLocation,
  Document,
  Download,
  ArrowDown,
  Picture,
  ChatDotRound
} from '@element-plus/icons-vue'
import { getTripPlanById, updateTripPlan, deleteTripPlan, createConversationFromTrip } from '@/api/trip'
import AMapLoader from '@amap/amap-jsapi-loader'
import html2canvas from 'html2canvas'
import jsPDF from 'jspdf'

const router = useRouter()
const route = useRoute()
const tripPlan = ref(null)
const tripPlanId = ref(null)
const editMode = ref(false)
const originalPlan = ref(null)
const activeSection = ref('overview')
const activeDays = ref([0])
const exportActiveDays = ref([])
const mainContentRef = ref(null)
const contentScrollAreaRef = ref(null)
let map = null
let scrollHandler = null

const loadTripPlan = async (id) => {
  try {
    const response = await getTripPlanById(id)
    if (response.success && response.data) {
      // 确保 days 数组按 day_index 排序
      if (response.data.days && Array.isArray(response.data.days)) {
        response.data.days.sort((a, b) => a.day_index - b.day_index)
      }
      tripPlan.value = response.data
      originalPlan.value = JSON.parse(JSON.stringify(response.data))
    }
  } catch (error) {
    ElMessage.error('加载旅游计划失败')
    console.error(error)
  }
}

const getSectionIds = () => {
  const ids = ['overview']
  if (tripPlan.value?.budget) {
    ids.push('budget')
  }
  ids.push('map')
  if (tripPlan.value?.days) {
    tripPlan.value.days.forEach((_, index) => {
      ids.push(`day-${index}`)
    })
  }
  if (tripPlan.value?.weather_info && tripPlan.value.weather_info.length > 0) {
    ids.push('weather')
  }
  return ids
}

const handleScroll = () => {
  const container = contentScrollAreaRef.value
  if (!container) return

  const scrollTop = container.scrollTop
  const containerTop = container.offsetTop
  const sectionIds = getSectionIds()

  let currentSection = sectionIds[0]

  for (const id of sectionIds) {
    const element = document.getElementById(id)
    if (element) {
      const elementTop = element.offsetTop - containerTop - 100
      if (scrollTop >= elementTop) {
        currentSection = id
      }
    }
  }

  if (activeSection.value !== currentSection) {
    activeSection.value = currentSection
    // 如果是 day-xx 格式，展开对应的天数
    if (currentSection.startsWith('day-')) {
      const dayIndex = parseInt(currentSection.split('-')[1])
      if (!activeDays.value.includes(dayIndex)) {
        activeDays.value.push(dayIndex)
      }
    }
  }
}

watch(() => route.params.id, async (newId) => {
  // 先移除旧的滚动监听
  if (contentScrollAreaRef.value && scrollHandler) {
    contentScrollAreaRef.value.removeEventListener('scroll', scrollHandler)
  }

  if (newId) {
    tripPlanId.value = newId
    await loadTripPlan(newId)
  } else {
    tripPlan.value = null
    tripPlanId.value = null
    const data = sessionStorage.getItem('tripPlan')
    if (data) {
      const parsedData = JSON.parse(data)
      // 确保 days 数组按 day_index 排序
      if (parsedData.days && Array.isArray(parsedData.days)) {
        parsedData.days.sort((a, b) => a.day_index - b.day_index)
      }
      tripPlan.value = parsedData
    }
  }
  // 切换规划后重新初始化地图
  if (map) {
    map.destroy()
    map = null
  }
  await nextTick()
  if (tripPlan.value) {
    initMap()
  }
  // 重新添加滚动监听
  await nextTick()
  if (contentScrollAreaRef.value && tripPlan.value) {
    activeSection.value = 'overview'
    scrollHandler = handleScroll
    contentScrollAreaRef.value.addEventListener('scroll', scrollHandler, { passive: true })
  }
})

onMounted(async () => {
  if (route.params.id) {
    tripPlanId.value = route.params.id
    await loadTripPlan(route.params.id)
  } else {
    const data = sessionStorage.getItem('tripPlan')
    if (data) {
      const parsedData = JSON.parse(data)
      // 确保 days 数组按 day_index 排序
      if (parsedData.days && Array.isArray(parsedData.days)) {
        parsedData.days.sort((a, b) => a.day_index - b.day_index)
      }
      tripPlan.value = parsedData
    }
  }
  await nextTick()
  if (tripPlan.value) {
    initMap()
  }
  // 添加滚动监听
  await nextTick()
  if (contentScrollAreaRef.value) {
    scrollHandler = handleScroll
    contentScrollAreaRef.value.addEventListener('scroll', scrollHandler, { passive: true })
  }
})

onUnmounted(() => {
  if (contentScrollAreaRef.value && scrollHandler) {
    contentScrollAreaRef.value.removeEventListener('scroll', scrollHandler)
  }
})

const goBack = () => {
  router.push('/trip')
}

const openConversation = async () => {
  if (!tripPlanId.value) {
    ElMessage.warning('请先保存行程后再打开对话')
    return
  }

  try {
    const response = await createConversationFromTrip(tripPlanId.value)
    if (response.success && response.data) {
      const conversationId = response.data.conversation_id
      router.push(`/chat/${conversationId}`)
    }
  } catch (error) {
    console.error('打开对话失败:', error)
    ElMessage.error('打开对话失败')
  }
}

const scrollToSection = (key) => {
  activeSection.value = key

  // 如果是 day-xx 格式，展开对应的天数
  if (key.startsWith('day-')) {
    const dayIndex = parseInt(key.split('-')[1])
    activeDays.value = [dayIndex]
  }

  nextTick(() => {
    const element = document.getElementById(key)
    if (element && contentScrollAreaRef.value) {
      const container = contentScrollAreaRef.value
      const elementTop = element.offsetTop - container.offsetTop - 20
      container.scrollTo({
        top: elementTop,
        behavior: 'smooth'
      })
    }
  })
}

const toggleEditMode = () => {
  editMode.value = true
  originalPlan.value = JSON.parse(JSON.stringify(tripPlan.value))
  ElMessage.info('进入编辑模式')
}

const saveChanges = async () => {
  editMode.value = false
  if (tripPlan.value) {
    if (tripPlanId.value) {
      try {
        await updateTripPlan(tripPlanId.value, tripPlan.value)
        ElMessage.success('修改已保存')
      } catch (error) {
        ElMessage.error('保存失败')
      }
    } else {
      sessionStorage.setItem('tripPlan', JSON.stringify(tripPlan.value))
      ElMessage.success('修改已保存到本地')
    }
  }

  if (map) {
    map.destroy()
    map = null
  }
  await nextTick()
  initMap()
}

const cancelEdit = () => {
  if (originalPlan.value) {
    tripPlan.value = JSON.parse(JSON.stringify(originalPlan.value))
  }
  editMode.value = false
  ElMessage.info('已取消编辑')
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除这个旅游计划吗？删除后无法恢复。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await deleteTripPlan(tripPlanId.value)
    ElMessage.success('删除成功')
    router.push('/trip')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const getMealLabel = (type) => {
  const labels = {
    breakfast: '早餐',
    lunch: '午餐',
    dinner: '晚餐',
    snack: '小吃'
  }
  return labels[type] || type
}

const initMap = async () => {
  if (!tripPlan.value) return

  if (map) {
    map.destroy()
  }

  try {
    const AMap = await AMapLoader.load({
      key: import.meta.env.VITE_AMAP_WEB_JS_KEY || 'demo',
      version: '2.0',
      plugins: ['AMap.Marker', 'AMap.Polyline', 'AMap.InfoWindow']
    })

    // 获取城市中心坐标作为初始中心点
    const cityCenter = getCityCenter(tripPlan.value.city)

    map = new AMap.Map('amap-container', {
      zoom: 12,
      center: cityCenter,
      viewMode: '3D'
    })

    addAttractionMarkers(AMap)

  } catch (error) {
    console.error('地图加载失败:', error)
  }
}

const getCityCenter = (city) => {
  // 主要城市中心坐标
  const cityCenters = {
    "北京": [116.397428, 39.90923],
    "上海": [121.4737, 31.2304],
    "广州": [113.2644, 23.1291],
    "深圳": [114.0579, 22.5431],
    "杭州": [120.1551, 30.2741],
    "成都": [104.0668, 30.5728],
    "重庆": [106.5516, 29.5630],
    "武汉": [114.3055, 30.5931],
    "西安": [108.9398, 34.3416],
    "南京": [118.7969, 32.0603],
    "苏州": [120.6196, 31.2990],
    "厦门": [118.0894, 24.4798],
    "青岛": [120.3827, 36.0671],
    "大连": [121.6147, 38.9140],
    "昆明": [102.7103, 25.0406],
    "长沙": [112.9388, 28.2282],
    "郑州": [113.6254, 34.7466],
    "济南": [117.1201, 36.6512],
    "沈阳": [123.4315, 41.8045],
    "哈尔滨": [126.5356, 45.8038],
    "长春": [125.3235, 43.8868],
    "石家庄": [114.5149, 38.0423],
    "太原": [112.5489, 37.8570],
    "合肥": [117.2830, 31.8612],
    "福州": [119.2965, 26.0998],
    "南昌": [115.8922, 28.6765],
    "南宁": [108.3200, 22.8240],
    "海口": [110.1999, 20.0442],
    "贵阳": [106.7135, 26.5783],
    "兰州": [103.8236, 36.0580],
    "银川": [106.2784, 38.4684],
    "西宁": [101.7802, 36.6171],
    "乌鲁木齐": [87.6177, 43.7928],
    "拉萨": [91.1375, 29.6525],
    "呼和浩特": [111.6708, 40.8414],
    "无锡": [120.3053, 31.5747],
    "常州": [119.9741, 31.8112],
    "宁波": [121.5494, 29.8683],
    "温州": [120.6994, 27.9942],
  }

  // 精确匹配
  if (city in cityCenters) {
    return cityCenters[city]
  }

  // 前缀匹配
  for (const [cityName, center] of Object.entries(cityCenters)) {
    if (city.startsWith(cityName) || cityName.startsWith(city)) {
      return center
    }
  }

  // 默认使用北京坐标
  console.warn(`未知城市: ${city}，使用默认坐标`)
  return [116.397428, 39.90923]
}

const addAttractionMarkers = (AMap) => {
  if (!tripPlan.value || !map) return

  const markers = []
  const allAttractions = []

  // 收集所有景点
  tripPlan.value.days.forEach((day, dayIndex) => {
    day.attractions.forEach((attraction, attrIndex) => {
      if (attraction.location && attraction.location.longitude && attraction.location.latitude) {
        allAttractions.push({
          ...attraction,
          dayIndex,
          attrIndex
        })
      }
    })
  })

  // 创建标记
  allAttractions.forEach((attraction, index) => {
    const marker = new AMap.Marker({
      position: [attraction.location.longitude, attraction.location.latitude],
      title: attraction.name,
      label: {
        content: `<div style="background: #4CAF50; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">${index + 1}</div>`,
        offset: new AMap.Pixel(0, -30)
      }
    })

    // 创建信息窗口
    const infoWindow = new AMap.InfoWindow({
      content: `
        <div style="padding: 10px;">
          <h4 style="margin: 0 0 8px 0;">${attraction.name}</h4>
          <p style="margin: 4px 0;"><strong>地址:</strong> ${attraction.address}</p>
          <p style="margin: 4px 0;"><strong>游览时长:</strong> ${attraction.visit_duration}分钟</p>
          <p style="margin: 4px 0;"><strong>描述:</strong> ${attraction.description}</p>
          <p style="margin: 4px 0; color: #1890ff;"><strong>第${attraction.dayIndex + 1}天 景点${attraction.attrIndex + 1}</strong></p>
        </div>
      `,
      offset: new AMap.Pixel(0, -30)
    })

    // 点击标记显示信息窗口
    marker.on('click', () => {
      infoWindow.open(map, marker.getPosition())
    })

    markers.push(marker)
  })

  // 添加标记到地图
  map.add(markers)

  // 自动调整视野以包含所有标记
  if (allAttractions.length > 0) {
    map.setFitView(markers)
  }

  // 绘制路线
  drawRoutes(AMap, allAttractions)
}

const drawRoutes = (AMap, attractions) => {
  if (attractions.length < 2 || !map) return

  const dayGroups = {}
  attractions.forEach(attr => {
    if (!dayGroups[attr.dayIndex]) {
      dayGroups[attr.dayIndex] = []
    }
    dayGroups[attr.dayIndex].push(attr)
  })

  Object.values(dayGroups).forEach((dayAttractions) => {
    if (dayAttractions.length < 2) return

    const path = dayAttractions.map((attr) => {
      const lon = attr.location.longitude
      const lat = attr.location.latitude
      return [lon, lat]
    })

    const polyline = new AMap.Polyline({
      path: path,
      strokeColor: '#1890ff',
      strokeWeight: 4,
      strokeOpacity: 0.8,
      strokeStyle: 'solid',
      showDir: true
    })

    map.add(polyline)
  })
}

const exportAsImage = async () => {
  let loadingMessage = null
  try {
    loadingMessage = ElMessage({ message: '正在生成图片...', type: 'info', duration: 0 })

    // 保存当前展开状态
    const savedActiveDays = [...activeDays.value]

    // 展开所有天数
    if (tripPlan.value && tripPlan.value.days) {
      exportActiveDays.value = tripPlan.value.days.map((_, index) => index)
      activeDays.value = exportActiveDays.value
    }

    // 等待DOM更新
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 300))

    const element = mainContentRef.value
    if (!element) {
      throw new Error('未找到内容元素')
    }

    const canvas = await html2canvas(element, {
      backgroundColor: '#f5f7fa',
      scale: 2,
      logging: false,
      useCORS: true,
      allowTaint: true
    })

    const link = document.createElement('a')
    link.download = `旅游计划_${tripPlan.value?.city}_${new Date().getTime()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()

    // 关闭加载提示
    if (loadingMessage && loadingMessage.close) {
      loadingMessage.close()
    }
    ElMessage.success('图片导出成功!')

    // 恢复原来的展开状态
    activeDays.value = savedActiveDays
  } catch (error) {
    console.error('导出图片失败:', error)
    if (loadingMessage && loadingMessage.close) {
      loadingMessage.close()
    }
    ElMessage.error(`导出图片失败: ${error.message}`)
  }
}

const exportAsPDF = async () => {
  let loadingMessage = null
  try {
    loadingMessage = ElMessage({ message: '正在生成PDF...', type: 'info', duration: 0 })

    // 保存当前展开状态
    const savedActiveDays = [...activeDays.value]

    // 展开所有天数
    if (tripPlan.value && tripPlan.value.days) {
      exportActiveDays.value = tripPlan.value.days.map((_, index) => index)
      activeDays.value = exportActiveDays.value
    }

    // 等待DOM更新
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 300))

    const element = mainContentRef.value
    if (!element) {
      throw new Error('未找到内容元素')
    }

    const canvas = await html2canvas(element, {
      backgroundColor: '#f5f7fa',
      scale: 2,
      logging: false,
      useCORS: true,
      allowTaint: true
    })

    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    })

    const imgWidth = 210
    const imgHeight = (canvas.height * imgWidth) / canvas.width

    let heightLeft = imgHeight
    let position = 0

    pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
    heightLeft -= 297

    while (heightLeft > 0) {
      position = heightLeft - imgHeight
      pdf.addPage()
      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight)
      heightLeft -= 297
    }

    pdf.save(`旅游计划_${tripPlan.value?.city}_${new Date().getTime()}.pdf`)

    // 关闭加载提示
    if (loadingMessage && loadingMessage.close) {
      loadingMessage.close()
    }
    ElMessage.success('PDF导出成功!')

    // 恢复原来的展开状态
    activeDays.value = savedActiveDays
  } catch (error) {
    console.error('导出PDF失败:', error)
    if (loadingMessage && loadingMessage.close) {
      loadingMessage.close()
    }
    ElMessage.error(`导出PDF失败: ${error.message}`)
  }
}
</script>

<style scoped>
.trip-result-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  overflow: hidden;
}

.page-header {
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  z-index: 10;
  flex-shrink: 0;
}

.back-button {
  border-radius: 8px;
  font-weight: 500;
}

.content-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-height: 0;
}

.content-wrapper {
  max-width: 1600px;
  margin: 0 auto;
  display: flex;
  gap: 24px;
}

.side-nav {
  width: 200px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: fit-content;
  max-height: calc(100vh - 180px);
  overflow-y: auto;
}

.side-nav :deep(.el-menu) {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  background: white;
  border: none;
}

.side-nav :deep(.el-menu-item) {
  margin: 4px 8px;
  border-radius: 8px;
  height: 44px;
  line-height: 44px;
}

.side-nav :deep(.el-menu-item.is-active) {
  background: #409eff;
  color: white;
}

.side-nav :deep(.el-sub-menu__title) {
  margin: 4px 8px;
  border-radius: 8px;
}

.main-content {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
}

.top-info-section {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.left-info {
  flex: 0 0 400px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.right-map {
  flex: 1;
  min-width: 0;
}

.map-card {
  height: 520px;
}

.map-card :deep(.el-card-body) {
  height: calc(100% - 57px);
  padding: 0;
}

.map-container {
  width: 100%;
  height: 100%;
}

.overview-card, .budget-card, .days-card, .weather-card, .map-card {
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 600;
}

.overview-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-label {
  font-size: 14px;
  font-weight: 600;
  color: #666;
}

.info-value {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
}

.budget-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.budget-item {
  text-align: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.budget-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}

.budget-value {
  font-size: 20px;
  font-weight: 700;
  color: #1890ff;
}

.budget-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: #409eff;
  border-radius: 8px;
  color: white;
}

.total-label {
  font-size: 16px;
  font-weight: 600;
}

.total-value {
  font-size: 28px;
  font-weight: 700;
}

.day-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.day-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.day-date {
  font-size: 14px;
  color: #999;
}

.day-info {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.info-row {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  font-weight: 600;
  color: #666;
  min-width: 80px;
}

.info-row .value {
  color: #333;
  flex: 1;
}

.attraction-card {
  margin-bottom: 16px;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.attraction-card:hover {
  transform: scale(1.02);
}

.attraction-header {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 12px;
}

.attraction-badge-small {
  background: #409eff;
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
}

.attraction-name {
  font-weight: 600;
  font-size: 16px;
  flex: 1;
}

.price-tag {
  background: rgba(255, 77, 79, 0.9);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: bold;
  font-size: 14px;
  flex-shrink: 0;
}

.attraction-info p {
  margin-bottom: 8px;
  font-size: 14px;
}

.hotel-card {
  border-radius: 12px;
  border: 1px solid #d4e8f5;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.hotel-card :deep(.el-card__header) {
  background: #409eff;
  padding: 16px 20px;
  border-bottom: none;
}

.hotel-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.hotel-title {
  font-weight: 600;
  font-size: 17px;
  color: white;
  flex: 1;
}

.hotel-rating {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 600;
  backdrop-filter: blur(4px);
}

.hotel-card :deep(.el-card__body) {
  padding: 20px;
  background: #e8f4fd;
}

.hotel-info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.hotel-info-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e1edf5;
  transition: background 0.2s;
}

.hotel-info-item:hover {
  background: #f5f9fc;
}

.hotel-info-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.hotel-info-label {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.hotel-info-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  word-break: break-all;
}

.hotel-info-value.price-highlight {
  color: #e6a23c;
  font-weight: 600;
}

.meal-cost {
  color: #67c23a;
  font-weight: 500;
}

.weather-item {
  background: #e0f7fa;
  border: none;
  margin-bottom: 16px;
  transition: all 0.3s ease;
}

.weather-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
}

.weather-date {
  font-size: 16px;
  font-weight: bold;
  color: #00796b;
  margin-bottom: 12px;
  text-align: center;
}

.weather-info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.weather-label {
  font-size: 12px;
  color: #666;
}

.weather-value {
  font-size: 16px;
  font-weight: 600;
  color: #00796b;
}

.weather-wind {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 121, 107, 0.2);
  text-align: center;
  color: #00796b;
  font-size: 14px;
}

.back-top-button {
  width: 50px;
  height: 50px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  cursor: pointer;
  transition: all 0.3s ease;
}

.back-top-button:hover {
  transform: scale(1.1);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
}

@media (max-width: 1200px) {
  .top-info-section {
    flex-direction: column;
  }

  .left-info {
    flex: none;
    width: 100%;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 16px;
    padding: 16px;
  }

  .content-scroll-area {
    padding: 16px;
  }

  .content-wrapper {
    flex-direction: column;
  }

  .side-nav {
    width: 100%;
    position: relative;
    max-height: none;
  }

  .budget-grid {
    grid-template-columns: 1fr;
  }
}
</style>
