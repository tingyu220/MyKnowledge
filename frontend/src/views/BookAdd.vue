<template>
  <div class="book-add-container">
    <el-card class="add-card">
      <template #header>
        <div class="card-header">
          <h2>添加图书</h2>
          <el-button @click="goBack" plain size="small">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
        </div>
      </template>

      <el-form :model="addForm" label-width="80px">
        <!-- ISBN 输入 -->
        <el-form-item label="ISBN" class="isbn-item">
          <el-input
            v-model="addForm.isbn"
            placeholder="请输入 ISBN"
            clearable
            @blur="onIsbnBlur"
            @keyup.enter="handleAddBook"
            :disabled="adding"
            size="large"
          >
            <template #prefix>
              <el-icon><Postcard /></el-icon>
            </template>
          </el-input>

          <!-- 验证状态提示 -->
          <div v-if="isbnValidation.valid === true" class="isbn-hint success">
            <el-icon><CircleCheck /></el-icon> ISBN 格式正确
          </div>
          <div v-else-if="isbnValidation.valid === false" class="isbn-hint error">
            <el-icon><CircleClose /></el-icon> ISBN 格式不正确
          </div>
        </el-form-item>

        <!-- 手机端扫码按钮 -->
        <el-form-item label="" v-if="isMobile">
          <el-button type="primary" plain class="scan-btn" @click="handleScanClick">
            <el-icon><Monitor /></el-icon>
            扫描 ISBN 条码
          </el-button>
        </el-form-item>

        <!-- PC端扫码按钮 -->
        <el-form-item label="" v-else>
          <el-button type="primary" @click="handleScanClick" :disabled="adding">
            <el-icon><Camera /></el-icon>
            摄像头扫码
          </el-button>
        </el-form-item>

        <!-- 提示信息 -->
        <el-form-item>
          <el-alert
            type="info"
            :closable="false"
            show-icon
          >
            <template #title>操作说明</template>
            <div class="tips-content">
              输入 ISBN 后点击"添加图书"，系统将自动获取图书信息
            </div>
          </el-alert>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="footer-actions">
          <el-button @click="goBack" :disabled="adding" size="large">取消</el-button>
          <el-button
            type="primary"
            @click="handleAddBook"
            :loading="adding"
            :disabled="!canSubmit"
            size="large"
            class="add-btn"
          >
            添加图书
          </el-button>
        </div>
      </template>
    </el-card>

    <!-- 添加结果对话框 -->
    <el-dialog
      v-model="showResultDialog"
      :title="resultDialog.title"
      width="90%"
      :close-on-click-modal="false"
    >
      <div class="result-content" v-if="resultDialog.book">
        <div class="result-book">
          <el-image
            v-if="resultDialog.book.cover_url"
            :src="resultDialog.book.cover_url"
            class="result-cover"
            fit="cover"
          >
            <template #error>
              <div class="cover-placeholder">无封面</div>
            </template>
          </el-image>
          <div v-else class="cover-placeholder">无封面</div>

          <div class="result-info">
            <h3>{{ resultDialog.book.title }}</h3>
            <p v-if="resultDialog.book.author">
              <span class="label">作者：</span>{{ resultDialog.book.author }}
            </p>
            <p v-if="resultDialog.book.publisher">
              <span class="label">出版社：</span>{{ resultDialog.book.publisher }}
            </p>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="handleResultOk" size="small">查看图书</el-button>
        <el-button type="primary" @click="handleResultContinue" size="small">继续添加</el-button>
      </template>
    </el-dialog>

    <!-- PC 端扫码弹窗 -->
    <IsbnBarcodeScanner v-model="showScanner" @scan="onScanResult" />

    <!-- 手动输入对话框 -->
    <el-dialog
      v-model="showManualDialog"
      title="手动输入图书信息"
      width="90%"
      :close-on-click-modal="false"
    >
      <el-form :model="manualForm" label-width="80px">
        <el-form-item label="ISBN">
          <el-input v-model="manualForm.isbn" placeholder="ISBN" />
        </el-form-item>
        <el-form-item label="书名" required>
          <el-input v-model="manualForm.title" placeholder="图书名称" />
        </el-form-item>
        <el-form-item label="作者">
          <el-input v-model="manualForm.author" placeholder="作者" />
        </el-form-item>
        <el-form-item label="出版社">
          <el-input v-model="manualForm.publisher" placeholder="出版社" />
        </el-form-item>
        <el-form-item label="出版日期">
          <el-input v-model="manualForm.publish_date" placeholder="如：2020-01" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input
            v-model="manualForm.description"
            type="textarea"
            :rows="3"
            placeholder="图书简介"
          />
        </el-form-item>
        <el-form-item label="封面URL">
          <el-input v-model="manualForm.cover_url" placeholder="封面图片链接" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showManualDialog = false">取消</el-button>
        <el-button type="primary" @click="handleManualSubmit" :loading="adding">
          确认添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Camera,
  ArrowLeft,
  CircleCheck,
  CircleClose,
  Postcard,
  Monitor
} from '@element-plus/icons-vue'
import { addBook } from '../api/books'
import { validateIsbn } from '../api/isbn'
import IsbnBarcodeScanner from '../components/IsbnBarcodeScanner.vue'

export default {
  name: 'BookAdd',
  components: {
    Camera,
    ArrowLeft,
    CircleCheck,
    CircleClose,
    Postcard,
    Monitor,
    IsbnBarcodeScanner
  },
  setup() {
    const router = useRouter()
    const route = useRoute()

    // 表单数据
    const addForm = reactive({
      isbn: ''
    })

    // 状态
    const showScanner = ref(false)
    const adding = ref(false)
    const isMobile = ref(false)
    const isbnValidation = reactive({ valid: null })
    
    // 手动输入对话框
    const showManualDialog = ref(false)
    const manualForm = reactive({
      isbn: '',
      title: '',
      author: '',
      publisher: '',
      publish_date: '',
      description: '',
      cover_url: ''
    })

    // 结果对话框
    const showResultDialog = ref(false)
    const resultDialog = reactive({
      title: '',
      book: null
    })

    // 检测设备类型
    onMounted(() => {
      isMobile.value = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)

      // 从 URL 读取 ISBN 参数
      const isbnFromURL = route.query.isbn
      if (isbnFromURL) {
        addForm.isbn = isbnFromURL
        // 延迟校验，确保 DOM 已渲染
        setTimeout(() => {
          onIsbnBlur()
        }, 100)
      }
    })

    // 监听 ISBN 变化，实时校验
    let validateTimer = null
    watch(() => addForm.isbn, (newVal) => {
      isbnValidation.valid = null
      if (validateTimer) clearTimeout(validateTimer)
      if (newVal) {
        validateTimer = setTimeout(onIsbnBlur, 500)
      }
    })

    // 返回列表
    const goBack = () => {
      router.push('/books')
    }

    // 打开扫码弹窗
    const openScanner = () => {
      console.log('打开扫码弹窗', showScanner.value)
      showScanner.value = true
    }

    // 手机端打开扫码（使用摄像头扫描ISBN条码）
    const openMobileScanner = () => {
      console.log('手机端打开扫码')
      showScanner.value = true
    }

    // 处理扫码按钮点击
    const handleScanClick = () => {
      console.log('点击了扫码按钮, isMobile:', isMobile.value)
      if (isMobile.value) {
        openMobileScanner()
      } else {
        openScanner()
      }
    }

    // 扫码结果
    const onScanResult = (isbn) => {
      console.log('[BookAdd] 扫码回调触发, ISBN:', isbn)
      addForm.isbn = isbn
      console.log('[BookAdd] addForm.isbn 当前值:', addForm.isbn)
      onIsbnBlur()
    }

    // ISBN 校验
    const onIsbnBlur = async () => {
      const s = (addForm.isbn || '').trim()
      if (!s) {
        isbnValidation.valid = null
        return
      }
      try {
        const res = await validateIsbn(s)
        isbnValidation.valid = !!res.valid
      } catch (error) {
        isbnValidation.valid = false
      }
    }

    // 计算：是否可以提交
    const canSubmit = computed(() => {
      return isbnValidation.valid === true && !adding.value
    })

    // 提交添加图书
    const handleAddBook = async () => {
      const isbn = addForm.isbn.trim()
      if (!isbn) {
        ElMessage.warning('请输入或扫描 ISBN')
        return
      }
      if (isbnValidation.valid !== true) {
        // 再次校验
        await onIsbnBlur()
        if (isbnValidation.valid !== true) {
          ElMessage.warning('请修正 ISBN 格式后再添加')
          return
        }
      }

      adding.value = true
      try {
        const res = await addBook(isbn)

        // 成功，显示结果
        if (res.message === '图书已存在') {
          resultDialog.title = '图书已存在'
          resultDialog.book = res.book
          showResultDialog.value = true
        } else {
          resultDialog.title = '添加成功'
          resultDialog.book = res.book
          showResultDialog.value = true
        }
      } catch (error) {
        console.error('添加图书失败:', error)
        const status = error.response?.status
        const errData = error.response?.data
        
        // 如果后端要求手动输入
        if (status === 200 && errData?.requires_manual) {
          // 显示手动输入对话框
          manualForm.isbn = isbn
          manualForm.title = ''
          manualForm.author = ''
          manualForm.publisher = ''
          manualForm.publish_date = ''
          manualForm.description = ''
          manualForm.cover_url = ''
          showManualDialog.value = true
          ElMessage.info('未能找到图书信息，请手动输入')
        } else {
          ElMessage.error(errData?.error || error.response?.data?.error || '添加失败，请稍后重试')
        }
      } finally {
        adding.value = false
      }
    }

    // 提交手动输入
    const handleManualSubmit = async () => {
      if (!manualForm.title || !manualForm.title.trim()) {
        ElMessage.warning('请输入书名')
        return
      }

      adding.value = true
      try {
        const payload = {
          isbn: manualForm.isbn,
          title: manualForm.title,
          author: manualForm.author,
          publisher: manualForm.publisher,
          publish_date: manualForm.publish_date,
          description: manualForm.description,
          cover_url: manualForm.cover_url,
          manual: true
        }
        const res = await addBook(payload)
        
        showManualDialog.value = false
        if (res.message === '图书已存在') {
          resultDialog.title = '图书已存在'
          resultDialog.book = res.book
        } else {
          resultDialog.title = '添��成功'
          resultDialog.book = res.book
        }
        showResultDialog.value = true
      } catch (error) {
        console.error('手动添加失败:', error)
        ElMessage.error(error.response?.data?.error || '添加失败')
      } finally {
        adding.value = false
      }
    }

    // 结果对话框 - 查看图书
    const handleResultOk = () => {
      showResultDialog.value = false
      if (resultDialog.book?.id) {
        router.push(`/books/${resultDialog.book.id}`)
      } else {
        router.push('/books')
      }
    }

    // 结果对话框 - 继续添加
    const handleResultContinue = () => {
      showResultDialog.value = false
      addForm.isbn = ''
      isbnValidation.valid = null
    }

    return {
      addForm,
      showScanner,
      adding,
      isMobile,
      isbnValidation,
      showManualDialog,
      manualForm,
      showResultDialog,
      resultDialog,
      goBack,
      openScanner,
      openMobileScanner,
      handleScanClick,
      onScanResult,
      onIsbnBlur,
      canSubmit,
      handleAddBook,
      handleManualSubmit,
      handleResultOk,
      handleResultContinue
    }
  }
}
</script>

<style scoped>
.book-add-container {
  padding: 16px;
  max-width: 600px;
  margin: 0 auto;
}

.add-card {
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
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
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.isbn-item {
  margin-bottom: 8px;
}

.isbn-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 13px;
}

.isbn-hint.success { color: #67c23a; }
.isbn-hint.error { color: #f56c6c; }

.scan-btn {
  width: 100%;
  margin-top: 8px;
  height: 44px;
  font-size: 16px;
}

.tips-content {
  font-size: 13px;
  color: #606266;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
}

.add-btn {
  min-width: 100px;
}

/* 结果对话框 */
.result-content {
  padding: 10px 0;
}

.result-book {
  display: flex;
  gap: 20px;
  padding: 16px;
  background: #f9f9f9;
  border-radius: 8px;
}

.result-cover {
  width: 100px;
  height: 140px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
}

.cover-placeholder {
  width: 100px;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
  color: #999;
  font-size: 12px;
  border-radius: 4px;
}

.result-info {
  flex: 1;
  overflow: hidden;
}

.result-info h3 {
  margin: 0 0 12px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.result-info p {
  margin: 6px 0;
  font-size: 14px;
  color: #606266;
}

.result-info .label {
  color: #909399;
  font-weight: 500;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .book-add-container {
    padding: 8px;
  }

  .add-card {
    border-radius: 8px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .card-header h2 {
    font-size: 18px;
    margin: 0;
  }

  .isbn-item {
    margin-bottom: 12px;
  }

  .isbn-hint {
    margin-top: 6px;
    font-size: 12px;
  }

  .scan-btn {
    width: 100%;
    margin-top: 12px;
    height: 44px;
    font-size: 15px;
  }

  .tips-content {
    font-size: 12px;
    line-height: 1.5;
  }

  .footer-actions {
    flex-direction: column;
    gap: 10px;
    padding-top: 12px;
  }

  .footer-actions .el-button {
    width: 100%;
    height: 44px;
    font-size: 16px;
  }

  .result-book {
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 16px;
  }

  .result-cover,
  .cover-placeholder {
    width: 120px;
    height: 160px;
    flex-shrink: 0;
  }

  .result-info {
    width: 100%;
  }

  .result-info h3 {
    font-size: 16px;
    margin: 0 0 12px 0;
    word-break: break-all;
  }

  .result-info p {
    margin: 8px 0;
    font-size: 14px;
    text-align: left;
    word-break: break-all;
  }
}
</style>
