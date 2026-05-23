<template>
  <div class="book-detail-container">
    <el-card v-loading="loading">
      <el-button @click="$router.back()" style="margin-bottom: 20px">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
      
      <div v-if="book" class="book-detail">
        <div class="book-info">
          <div class="book-cover">
            <el-image
              v-if="book.cover_url"
              :src="coverProxyUrl"
              style="width: 200px; height: 280px"
              fit="cover"
              referrerpolicy="no-referrer"
            >
              <template #error>
                <div class="no-cover">加载失败</div>
              </template>
            </el-image>
            <div v-else class="no-cover">无封面</div>
          </div>
          
          <div class="book-content">
            <h1>{{ book.title }}</h1>
            <div class="book-meta">
              <p><strong>作者：</strong>{{ book.author || '未知' }}</p>
              <p><strong>出版社：</strong>{{ book.publisher || '未知' }}</p>
              <p><strong>出版日期：</strong>{{ book.publish_date || '未知' }}</p>
              <p><strong>ISBN：</strong>{{ book.isbn }}</p>
              <p><strong>分类：</strong>{{ book.category || '未分类' }}</p>
              <p v-if="book.tags && book.tags.length">
                <strong>标签：</strong>
                <el-tag v-for="tag in book.tags" :key="tag" style="margin-right: 5px">{{ tag }}</el-tag>
              </p>
            </div>
            
            <div class="book-actions">
              <el-button type="primary" @click="analyzeBook" :loading="analyzing">
                <el-icon><MagicStick /></el-icon>
                AI分析
              </el-button>
              <el-button type="success" @click="refreshBook" :loading="refreshing">
                <el-icon><Refresh /></el-icon>
                重新爬取
              </el-button>
              <el-button @click="showEditDialog = true">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
            </div>
          </div>
        </div>
        
        <div class="book-description">
          <h3>简介</h3>
          <p>{{ book.description || '暂无简介' }}</p>
        </div>
      </div>
    </el-card>
    
    <!-- 编辑对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑图书信息" width="600px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="书名">
          <el-input v-model="editForm.title"></el-input>
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="editForm.author"></el-input>
        </el-form-item>
        <el-form-item label="出版社">
          <el-input v-model="editForm.publisher"></el-input>
        </el-form-item>
        <el-form-item label="出版日期">
          <el-input v-model="editForm.publish_date"></el-input>
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="editForm.category"></el-input>
        </el-form-item>
        <el-form-item label="标签">
          <el-select
            v-model="editForm.tags"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入标签，可多选"
            style="width: 100%"
          >
            <el-option v-for="t in allTags" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="简介">
          <el-input 
            v-model="editForm.description" 
            type="textarea" 
            :rows="8"
            :maxlength="2000"
            show-word-limit
            placeholder="最多 2000 字"
          ></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleUpdate" :loading="updating">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, MagicStick, Edit, Refresh } from '@element-plus/icons-vue'
import { getBook, updateBook, refreshBook as refreshBookApi, getTags } from '../api/books'
import { analyzeBook } from '../api/ai'

export default {
  name: 'BookDetail',
  components: {
    ArrowLeft,
    MagicStick,
    Edit,
    Refresh
  },
  setup() {
    const route = useRoute()
    const book = ref(null)
    const loading = ref(false)
    const analyzing = ref(false)
    const refreshing = ref(false)
    const updating = ref(false)
    const showEditDialog = ref(false)

    const editForm = reactive({
      title: '',
      author: '',
      publisher: '',
      publish_date: '',
      category: '',
      description: '',
      tags: []
    })
    const allTags = ref([])

    const coverProxyUrl = computed(() => {
      const b = book.value
      if (!b?.cover_url || !b?.id) return ''
      return `/api/books/${b.id}/cover`
    })
    
    const loadBook = async () => {
      loading.value = true
      try {
        const res = await getBook(route.params.id)
        book.value = res.book
        
        // 填充编辑表单
        Object.assign(editForm, {
          title: book.value.title || '',
          author: book.value.author || '',
          publisher: book.value.publisher || '',
          publish_date: book.value.publish_date || '',
          category: book.value.category || '',
          description: book.value.description || '',
          tags: [...(book.value.tags || [])]
        })
      } catch (error) {
        console.error(error)
      } finally {
        loading.value = false
      }
    }

    const analyzeBookInfo = async () => {
      analyzing.value = true
      try {
        const res = await analyzeBook(route.params.id)
        ElMessage.success('分析完成')
        loadBook()
      } catch (error) {
        console.error(error)
      } finally {
        analyzing.value = false
      }
    }
    
    const refreshBookInfo = async () => {
      refreshing.value = true
      try {
        const res = await refreshBookApi(route.params.id)
        ElMessage.success(res.message || '重新爬取成功')
        loadBook()
      } catch (error) {
        console.error(error)
      } finally {
        refreshing.value = false
      }
    }
    
    const handleUpdate = async () => {
      updating.value = true
      try {
        const payload = {
          title: editForm.title,
          author: editForm.author,
          publisher: editForm.publisher,
          publish_date: editForm.publish_date,
          category: editForm.category,
          description: editForm.description,
          tags: editForm.tags
        }
        await updateBook(route.params.id, payload)
        ElMessage.success('更新成功')
        showEditDialog.value = false
        loadBook()
      } catch (error) {
        console.error(error)
      } finally {
        updating.value = false
      }
    }
    
    const loadAllTags = async () => {
      try {
        const res = await getTags()
        allTags.value = res.tags || []
      } catch {
        allTags.value = []
      }
    }

    onMounted(() => {
      loadBook()
      loadAllTags()
    })

    onBeforeUnmount(() => {
    })
    
    return {
      book,
      coverProxyUrl,
      allTags,
      loading,
      analyzing,
      refreshing,
      updating,
      showEditDialog,
      editForm,
      loadBook,
      analyzeBook: analyzeBookInfo,
      refreshBook: refreshBookInfo,
      handleUpdate
    }
  }
}
</script>

<style scoped>
.book-detail-container {
  padding: 16px;
}

.book-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.book-info {
  display: flex;
  gap: 24px;
}

.book-cover {
  flex-shrink: 0;
}

.no-cover {
  width: 160px;
  height: 220px;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.book-content {
  flex: 1;
  min-width: 0;
}

.book-content h1 {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 22px;
  word-break: break-word;
}

.book-meta p {
  margin: 8px 0;
  color: #666;
  font-size: 14px;
}

.book-actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.book-description {
  margin-top: 20px;
}

.book-description h3 {
  margin-bottom: 12px;
  color: #333;
}

.book-description p {
  line-height: 1.8;
  color: #666;
  white-space: pre-wrap;
  font-size: 14px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .book-detail-container {
    padding: 8px;
  }

  .book-info {
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 16px;
  }

  .book-cover .el-image,
  .no-cover {
    width: 140px !important;
    height: 190px !important;
  }

  .no-cover {
    width: 140px;
    height: 190px;
  }

  .book-content h1 {
    font-size: 18px;
  }

  .book-meta p {
    font-size: 13px;
  }

  .book-actions {
    justify-content: center;
  }

  .book-actions .el-button {
    flex: 1;
    min-width: 100px;
  }
}

@media (max-width: 480px) {
  .book-cover .el-image,
  .no-cover {
    width: 120px !important;
    height: 160px !important;
  }

  .no-cover {
    width: 120px;
    height: 160px;
  }

  .book-content h1 {
    font-size: 16px;
  }
}
</style>

