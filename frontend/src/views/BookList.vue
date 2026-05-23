<template>
  <div class="book-list-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <h2>图书列表</h2>
          <div class="search-row">
            <el-input
              v-model="searchKeyword"
              placeholder="搜索书名、作者、ISBN"
              style="width: 200px"
              @keyup.enter="loadBooks"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select v-model="selectedCategory" placeholder="分类筛选" style="width: 140px" clearable>
              <el-option
                v-for="cat in categories"
                :key="cat"
                :label="cat"
                :value="cat"
              />
            </el-select>
            <el-button type="primary" @click="goToAddPage">
              <el-icon><Plus /></el-icon>
              添加图书
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="books" v-loading="loading" stripe>
        <el-table-column prop="cover_url" label="封面" width="100">
          <template #default="{ row }">
            <el-image
              v-if="row.cover_url && row.id"
              :src="`/api/books/${row.id}/cover`"
              style="width: 60px; height: 80px"
              fit="cover"
              referrerpolicy="no-referrer"
            >
              <template #error>
                <span class="cover-fallback">加载失败</span>
              </template>
            </el-image>
            <span v-else>无封面</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="书名" min-width="200" />
        <el-table-column prop="author" label="作者" width="150" />
        <el-table-column prop="publisher" label="出版社" width="150" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="isbn" label="ISBN" width="150" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="viewDetail(row.id)">详情</el-button>
              <el-button type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 移动端卡片视图（480px以下显示） -->
      <div class="mobile-card-list" v-if="isMobileView">
        <div class="mobile-card" v-for="book in books" :key="book.id">
          <div class="mobile-card-cover">
            <el-image
              v-if="book.cover_url && book.id"
              :src="`/api/books/${book.id}/cover`"
              fit="cover"
              style="width: 100%; height: 100%;"
              referrerpolicy="no-referrer"
            >
              <template #error>
                <span>封面</span>
              </template>
            </el-image>
            <span v-else>无封面</span>
          </div>
          <div class="mobile-card-info">
            <div class="mobile-card-title">{{ book.title }}</div>
            <div class="mobile-card-meta">作者：{{ book.author || '未知' }}</div>
            <div class="mobile-card-meta">ISBN：{{ book.isbn }}</div>
            <div class="mobile-card-actions">
              <el-button type="primary" size="small" @click="viewDetail(book.id)">详情</el-button>
              <el-button type="danger" size="small" @click="handleDelete(book.id)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadBooks"
        @current-change="loadBooks"
        style="margin-top: 20px; justify-content: center"
      />
    </el-card>

    <!-- 添加图书对话框：ISBN 扫码 / 手动输入 -->
    <el-dialog v-model="showAddDialog" title="添加图书" width="520px" @closed="onAddDialogClosed">
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="ISBN">
          <div class="isbn-input-row">
            <el-input
              v-model="addForm.isbn"
              placeholder="请输入 ISBN 或点击扫码"
              clearable
              @blur="onIsbnBlur"
            >
              <template #append>
                <el-button type="primary" @click="showScan = true">
                  <el-icon><Camera /></el-icon>
                  扫码
                </el-button>
              </template>
            </el-input>
          </div>
          <div v-if="isbnValidation.valid === true" class="isbn-hint success">格式正确</div>
          <div v-else-if="isbnValidation.valid === false" class="isbn-hint error">ISBN 格式不正确（支持 ISBN-10 / ISBN-13）</div>
          <div v-else class="isbn-hint muted">支持 ISBN-10、ISBN-13；可手动输入或摄像头扫描条码</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddBook" :loading="adding">确定添加</el-button>
      </template>
    </el-dialog>

    <IsbnBarcodeScanner v-model="showScan" @scan="onScan" />
  </div>
</template>

<script>
import { ref, reactive, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Camera } from '@element-plus/icons-vue'
import { getBooks, addBook, deleteBook, getCategories } from '../api/books'
import { validateIsbn } from '../api/isbn'
import IsbnBarcodeScanner from '../components/IsbnBarcodeScanner.vue'

export default {
  name: 'BookList',
  components: {
    Search,
    Plus,
    Camera,
    IsbnBarcodeScanner
  },
  setup() {
    const router = useRouter()
    const books = ref([])
    const loading = ref(false)
    const adding = ref(false)
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(0)
    const searchKeyword = ref('')
    const selectedCategory = ref('')
    const categories = ref([])
    const showAddDialog = ref(false)
    const showScan = ref(false)
    const isbnValidation = reactive({ valid: null })
    const isMobileView = ref(false)

    // 检测移动端视图
    const checkMobileView = () => {
      isMobileView.value = window.innerWidth <= 480
    }

    const addForm = reactive({
      isbn: ''
    })

    const onAddDialogClosed = () => {
      addForm.isbn = ''
      isbnValidation.valid = null
    }

    // 跳转到添加页面
    const goToAddPage = () => {
      router.push('/books/add')
    }

    const onIsbnBlur = async () => {
      const s = (addForm.isbn || '').trim()
      if (!s) {
        isbnValidation.valid = null
        return
      }
      try {
        const res = await validateIsbn(s)
        isbnValidation.valid = !!res.valid
      } catch {
        isbnValidation.valid = false
      }
    }

    const onScan = async (isbn) => {
      addForm.isbn = isbn
      try {
        const res = await validateIsbn(isbn)
        isbnValidation.valid = !!res.valid
      } catch {
        isbnValidation.valid = false
      }
    }

    const loadBooks = async () => {
      loading.value = true
      try {
        const params = {
          page: currentPage.value,
          per_page: pageSize.value
        }
        if (searchKeyword.value) {
          params.search = searchKeyword.value
        }
        if (selectedCategory.value) {
          params.category = selectedCategory.value
        }
        
        const res = await getBooks(params)
        books.value = res.books
        total.value = res.total
      } catch (error) {
        console.error(error)
      } finally {
        loading.value = false
      }
    }
    
    const loadCategories = async () => {
      try {
        const res = await getCategories()
        categories.value = res.categories
      } catch (error) {
        console.error(error)
      }
    }
    
    const handleAddBook = async () => {
      const isbn = addForm.isbn.trim()
      if (!isbn) {
        ElMessage.warning('请输入或扫描 ISBN')
        return
      }
      if (isbnValidation.valid === false) {
        ElMessage.warning('请修正 ISBN 格式后再添加')
        return
      }
      if (isbnValidation.valid === null) {
        try {
          const res = await validateIsbn(isbn)
          isbnValidation.valid = !!res.valid
          if (!res.valid) {
            ElMessage.warning('ISBN 格式不正确，请使用 ISBN-10 或 ISBN-13')
            return
          }
        } catch {
          isbnValidation.valid = false
          ElMessage.warning('ISBN 校验失败，请检查格式')
          return
        }
      }

      adding.value = true
      try {
        const res = await addBook(isbn)
        // 根据返回消息显示不同的提示
        if (res.message === '图书已存在') {
          ElMessage.warning(res.message)
        } else {
          ElMessage.success(res.message || '添加成功')
        }
        showAddDialog.value = false
        addForm.isbn = ''
        isbnValidation.valid = null
        loadBooks()
      } catch (err) {
        // 错误消息已在响应拦截器中显示，这里只记录日志
        console.error('添加图书失败:', err)
        // 如果响应拦截器没有处理（如网络错误），这里补充提示
        if (!err.response && !err.request) {
          ElMessage.error('添加失败，请检查网络连接')
        }
      } finally {
        adding.value = false
      }
    }
    
    const handleDelete = async (id) => {
      try {
        await ElMessageBox.confirm('确定要删除这本图书吗？', '提示', {
          type: 'warning'
        })
        
        await deleteBook(id)
        ElMessage.success('删除成功')
        loadBooks()
      } catch (error) {
        if (error !== 'cancel') {
          console.error(error)
        }
      }
    }
    
    const viewDetail = (id) => {
      router.push(`/books/${id}`)
    }
    
    watch([searchKeyword, selectedCategory], () => {
      currentPage.value = 1
      loadBooks()
    })
    
    onMounted(() => {
      loadBooks()
      loadCategories()
      checkMobileView()
      window.addEventListener('resize', checkMobileView)
    })

    onBeforeUnmount(() => {
      window.removeEventListener('resize', checkMobileView)
    })
    
    return {
      books,
      loading,
      adding,
      currentPage,
      pageSize,
      total,
      searchKeyword,
      selectedCategory,
      categories,
      showAddDialog,
      showScan,
      addForm,
      isbnValidation,
      isMobileView,
      Camera,
      onAddDialogClosed,
      goToAddPage,
      onIsbnBlur,
      onScan,
      loadBooks,
      handleAddBook,
      handleDelete,
      viewDetail
    }
  }
}
</script>

<style scoped>
.book-list-container {
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

.search-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.isbn-input-row {
  width: 100%;
}

.isbn-input-row :deep(.el-input-group__append) {
  padding: 0;
}

.isbn-input-row :deep(.el-input-group__append .el-button) {
  margin: 0;
  border-radius: 0 4px 4px 0;
}

.isbn-hint {
  margin-top: 6px;
  font-size: 12px;
}

.isbn-hint.muted { color: #999; }
.isbn-hint.success { color: #67c23a; }
.isbn-hint.error { color: #f56c6c; }

.cover-fallback {
  display: inline-block;
  width: 60px;
  height: 80px;
  line-height: 80px;
  text-align: center;
  font-size: 12px;
  color: #999;
  background: #f0f0f0;
}

/* 操作按钮横向排列 */
.action-buttons {
  display: flex;
  gap: 4px;
  justify-content: center;
  align-items: center;
  flex-wrap: nowrap;
}

.action-buttons .el-button {
  flex-shrink: 0;
  padding: 5px 10px;
  font-size: 12px;
  min-height: 24px;
  line-height: 1;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .book-list-container {
    padding: 8px;
  }

  .card-header h2 {
    font-size: 16px;
    width: 100%;
  }

  .search-row {
    width: 100%;
  }

  .search-row :deep(.el-input),
  .search-row :deep(.el-select) {
    width: 100% !important;
  }

  .card-header :deep(.el-button) {
    width: 100%;
  }
}

/* 表格移动端适配 */
@media (max-width: 768px) {
  .book-list-container :deep(.el-table) {
    font-size: 12px;
  }

  .book-list-container :deep(.el-table__header) {
    font-size: 12px;
  }

  .book-list-container :deep(.el-table__body) {
    font-size: 12px;
  }

  .book-list-container :deep(.el-button--small) {
    padding: 5px 8px;
    font-size: 11px;
  }

  .book-list-container :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: center;
  }
}

/* 超小屏幕 - 改为卡片式布局 */
@media (max-width: 480px) {
  .book-list-container :deep(.el-table__body-wrapper) {
    display: none;
  }

  /* 显示卡片列表 */
  .book-list-container .mobile-card-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .book-list-container .mobile-card {
    display: flex;
    padding: 12px;
    background: #f9f9f9;
    border-radius: 8px;
    border: 1px solid #ebeef5;
  }

  .book-list-container .mobile-card-cover {
    width: 60px;
    height: 80px;
    flex-shrink: 0;
    margin-right: 12px;
    border-radius: 4px;
    overflow: hidden;
    background: #f0f0f0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: #999;
  }

  .book-list-container .mobile-card-cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .book-list-container .mobile-card-info {
    flex: 1;
    min-width: 0;
  }

  .book-list-container .mobile-card-title {
    font-size: 14px;
    font-weight: 600;
    color: #303133;
    margin: 0 0 8px 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .book-list-container .mobile-card-meta {
    font-size: 12px;
    color: #909399;
    margin-bottom: 4px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .book-list-container .mobile-card-actions {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  .book-list-container .mobile-card-actions .el-button {
    flex: 1;
    font-size: 12px;
    padding: 4px 8px;
    min-height: 28px;
  }
}
</style>
