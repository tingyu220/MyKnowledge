<template>
  <div class="ebook-manage-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>电子书管理</h2>
          <el-upload
            :http-request="handleUpload"
            :before-upload="beforeUpload"
            :show-file-list="false"
          >
            <el-button type="primary" :loading="uploading">
              <el-icon><Upload /></el-icon>
              上传电子书
            </el-button>
          </el-upload>
        </div>
      </template>
      
      <el-table :data="ebooks" v-loading="loading" stripe>
        <el-table-column prop="file_name" label="文件名" min-width="200" />
        <el-table-column prop="file_size" label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_type" label="类型" width="100" />
        <el-table-column prop="uploaded_at" label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.uploaded_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button type="success" size="small" @click="handleView(row)">查看</el-button>
            <el-button type="primary" size="small" @click="handleDownload(row.id)">下载</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { getEbooks, uploadEbook, deleteEbook, downloadEbook } from '../api/ebooks'

export default {
  name: 'EbookManage',
  components: {
    Upload
  },
  setup() {
    const router = useRouter()
    const ebooks = ref([])
    const loading = ref(false)
    const uploading = ref(false)
    
    const loadEbooks = async () => {
      loading.value = true
      try {
        const res = await getEbooks()
        ebooks.value = res.ebooks
      } catch (error) {
        console.error(error)
      } finally {
        loading.value = false
      }
    }
    
    const beforeUpload = (file) => {
      const allowedTypes = [
        'application/pdf',
        'application/epub+zip',
        'application/x-mobipocket-ebook',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      ]
      const name = (file.name || '').toLowerCase()
      const isAllowed =
        allowedTypes.includes(file.type) ||
        name.endsWith('.pdf') ||
        name.endsWith('.epub') ||
        name.endsWith('.mobi') ||
        name.endsWith('.txt') ||
        name.endsWith('.doc') ||
        name.endsWith('.docx')
      
      if (!isAllowed) {
        ElMessage.error('只支持 PDF、EPUB、MOBI、TXT、DOC、DOCX 格式的文件')
        return false
      }
      
      const isLt100M = file.size / 1024 / 1024 < 100
      if (!isLt100M) {
        ElMessage.error('文件大小不能超过 100MB')
        return false
      }
      
      return true
    }
    
    const handleUpload = async (options) => {
      const formData = new FormData()
      formData.append('file', options.file)
      
      uploading.value = true
      try {
        const res = await uploadEbook(formData)
        ElMessage.success('上传成功')
        loadEbooks()
        if (typeof options.onSuccess === 'function') options.onSuccess(res)
      } catch (error) {
        console.error(error)
        const msg = error?.response?.data?.error || error?.message || '上传失败'
        ElMessage.error(msg)
        if (typeof options.onError === 'function') options.onError(error)
      } finally {
        uploading.value = false
      }
    }
    
    const handleDownload = async (id) => {
      try {
        const res = await downloadEbook(id)
        // 处理文件下载
        const blob = new Blob([res])
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        const ebook = ebooks.value.find(e => e.id === id)
        link.download = ebook?.file_name || 'download'
        link.click()
        window.URL.revokeObjectURL(url)
      } catch (error) {
        console.error(error)
      }
    }

    const handleView = (row) => {
      router.push({
        path: `/ebooks/${row.id}/view`,
        query: row.book_id ? { book_id: String(row.book_id) } : {}
      })
    }
    
    const handleDelete = async (id) => {
      try {
        await ElMessageBox.confirm('确定要删除这个电子书吗？', '提示', {
          type: 'warning'
        })
        
        await deleteEbook(id)
        ElMessage.success('删除成功')
        loadEbooks()
      } catch (error) {
        if (error !== 'cancel') {
          console.error(error)
        }
      }
    }
    
    const formatFileSize = (bytes) => {
      if (!bytes) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
    }
    
    const formatDate = (dateStr) => {
      if (!dateStr) return ''
      const date = new Date(dateStr)
      return date.toLocaleString('zh-CN')
    }
    
    onMounted(() => {
      loadEbooks()
    })
    
    return {
      ebooks,
      loading,
      uploading,
      loadEbooks,
      beforeUpload,
      handleUpload,
      handleView,
      handleDownload,
      handleDelete,
      formatFileSize,
      formatDate
    }
  }
}
</script>

<style scoped>
.ebook-manage-container {
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .ebook-manage-container {
    padding: 8px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .card-header h2 {
    font-size: 16px;
    width: 100%;
  }

  .card-header :deep(.el-button) {
    width: 100%;
  }

  .ebook-manage-container :deep(.el-table) {
    font-size: 12px;
  }

  .ebook-manage-container :deep(.el-button--small) {
    padding: 5px 8px;
    font-size: 11px;
  }

  .ebook-manage-container :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: center;
  }
}
</style>

