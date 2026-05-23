<template>
  <div class="dashboard-container">
    <el-row :gutter="16" class="top-row">
      <el-col :xs="24" :sm="24" :md="12" :lg="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <div class="title">我的藏书</div>
              <el-button text @click="refresh" :loading="loading">刷新</el-button>
            </div>
          </template>

          <div class="stat-main">
            <div class="big">{{ summary.total_books || 0 }}</div>
            <div class="sub">本图书</div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="24" :md="12" :lg="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <div class="title">书籍分类占比</div>
            </div>
          </template>
          <div ref="chartEl" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="bottom-row">
      <el-col :xs="24" :sm="24" :md="24" :lg="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <div class="title">经典书单推荐</div>
            </div>
          </template>
          <el-scrollbar height="360px">
            <div class="famous-list">
              <div v-for="b in famousBooks" :key="b.title" class="famous-item">
                <div class="famous-title">{{ b.title }}</div>
                <div class="famous-sub">{{ b.note }}</div>
              </div>
            </div>
          </el-scrollbar>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { getDashboardSummary, getRecommendations } from '../api/dashboard'

export default {
  name: 'Dashboard',
  setup() {
    const router = useRouter()
    const loading = ref(false)
    const summary = reactive({
      categories: [],
      total_books: 0
    })

    const famousBooks = ref([])
    const loadingBooks = ref(false)

    const chartEl = ref(null)
    let chart = null

    const renderChart = () => {
      if (!chartEl.value) return
      if (!chart) chart = echarts.init(chartEl.value)
      const data = (summary.categories || []).map(c => ({ name: c.category, value: c.count }))
      chart.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
        legend: { top: 'bottom' },
        series: [
          {
            type: 'pie',
            radius: ['45%', '70%'],
            avoidLabelOverlap: true,
            label: { show: true, formatter: '{b} {d}%' },
            data
          }
        ]
      })
    }

    const refresh = async () => {
      loading.value = true
      try {
        const res = await getDashboardSummary(10)
        Object.assign(summary, {
          categories: res.categories || [],
          total_books: res.total_books || 0
        })
      } finally {
        loading.value = false
        renderChart()
      }
    }

    const loadRecommendations = async () => {
      loadingBooks.value = true
      try {
        const res = await getRecommendations()
        famousBooks.value = res.recommendations || []
      } catch (error) {
        console.error('Failed to load recommendations:', error)
        famousBooks.value = []
      } finally {
        loadingBooks.value = false
      }
    }

    const goBook = (id) => router.push(`/books/${id}`)

    const onResize = () => chart?.resize()

    onMounted(async () => {
      await Promise.all([refresh(), loadRecommendations()])
      window.addEventListener('resize', onResize)
    })

    onBeforeUnmount(() => {
      window.removeEventListener('resize', onResize)
      chart?.dispose()
      chart = null
    })

    watch(() => summary.categories, () => renderChart(), { deep: true })

    return {
      loading,
      summary,
      chartEl,
      famousBooks,
      loadingBooks,
      refresh,
      goBook
    }
  }
}
</script>

<style scoped>
/* 移动端适配 */
@media (max-width: 768px) {
  .dashboard-container {
    padding: 8px;
  }

  .top-row {
    margin-bottom: 16px;
  }

  .top-row > div,
  .top-row > aside {
    margin-bottom: 16px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .stat-main {
    text-align: center;
    padding: 8px 0 4px 0;
  }

  .big {
    font-size: 28px;
  }

  .sub {
    font-size: 13px;
  }

  .chart {
    height: 220px;
  }

  .bottom-row {
    margin-bottom: 16px;
  }

  .bottom-row > div,
  .bottom-row > aside {
    margin-bottom: 16px;
  }
}

@media (max-width: 480px) {
  .dashboard-container {
    padding: 4px;
  }

  .big {
    font-size: 24px;
  }

  .title {
    font-size: 14px;
  }

  .chart {
    height: 180px;
  }
}

.dashboard-container {
  padding: 16px;
}
.top-row {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.stat-main {
  text-align: center;
  padding: 8px 0 4px 0;
}
.big {
  font-size: 36px;
  font-weight: 700;
  color: #409eff;
}
.sub {
  color: #666;
  margin-top: 4px;
}
.chart {
  height: 260px;
}
.famous-item {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.famous-title {
  font-weight: 600;
  color: #333;
}
.famous-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #777;
}
</style>
