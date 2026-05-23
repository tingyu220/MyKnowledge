<template>
  <div class="ebook-viewer-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <div class="title">电子书预览</div>
          <div class="actions">
            <el-button @click="$router.back()">返回</el-button>
            <el-button type="primary" @click="openInNewTab">新窗口打开</el-button>
          </div>
        </div>
      </template>

      <div class="viewer-wrap">
        <iframe class="viewer" :src="viewUrl" />
      </div>

      <el-alert
        style="margin-top: 12px"
        type="info"
        show-icon
        :closable="false"
        title="提示"
        description="若提示不支持预览（如 EPUB/MOBI），请使用下载功能在本地阅读；Word 预览需要服务器安装 LibreOffice。"
      />
    </el-card>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

export default {
  name: 'EbookViewer',
  setup() {
    const route = useRoute()
    const viewUrl = computed(() => `/api/ebooks/${route.params.id}/view`)
    const openInNewTab = () => window.open(viewUrl.value, '_blank')

    return { viewUrl, openInNewTab }
  }
}
</script>

<style scoped>
.ebook-viewer-container {
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.title {
  font-size: 18px;
  font-weight: 600;
}

.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.viewer-wrap {
  width: 100%;
  height: calc(100vh - 200px);
  min-height: 400px;
  background: #f5f5f5;
  border-radius: 6px;
  overflow: hidden;
}

.viewer {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .ebook-viewer-container {
    padding: 8px;
  }

  .title {
    font-size: 16px;
  }

  .viewer-wrap {
    height: calc(100vh - 180px);
    min-height: 300px;
  }

  .actions .el-button {
    flex: 1;
    min-width: 80px;
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .viewer-wrap {
    height: calc(100vh - 160px);
    min-height: 250px;
  }

  .actions {
    width: 100%;
  }

  .actions .el-button {
    flex: 1;
  }
}
</style>

