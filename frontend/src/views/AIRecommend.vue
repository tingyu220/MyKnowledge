<template>
  <div class="ai-assistant-page">
    <el-card class="assistant-shell">
      <template #header>
        <div class="assistant-header">
          <div>
            <h2>AI 图书助手</h2>
            <p>先帮您准确查书，再在需要时补充推荐</p>
          </div>
          <el-button text @click="handleClearHistory" v-if="messages.length > 0">清空对话</el-button>
        </div>
      </template>

      <div class="assistant-body">
        <div class="messages-panel" ref="messagesContainer">
          <div v-if="messages.length === 0" class="assistant-empty">
            <div class="welcome-block">
              <h3>可以这样问我</h3>
              <p>我会只根据您的书库、标签和书架位置来回答。</p>
            </div>

            <div class="example-list">
              <el-tag
                v-for="(query, idx) in exampleQueries"
                :key="idx"
                type="warning"
                effect="plain"
                class="example-tag"
                @click="useExample(query)"
              >
                {{ query }}
              </el-tag>
            </div>

            <div v-if="recentBooks.length > 0" class="recent-section">
              <div class="section-title">
                <h3>最近添加</h3>
                <span>这些书会优先作为默认推荐上下文</span>
              </div>
              <div class="recent-grid">
                <el-card
                  v-for="book in recentBooks"
                  :key="book.id"
                  class="recent-book"
                  shadow="hover"
                  @click="viewBookDetail(book.id)"
                >
                  <div class="recent-cover">
                    <el-image
                      v-if="book.cover_url && book.id"
                      :src="`/api/books/${book.id}/cover`"
                      fit="cover"
                      referrerpolicy="no-referrer"
                    >
                      <template #error>
                        <div class="cover-fallback">暂无封面</div>
                      </template>
                    </el-image>
                    <div v-else class="cover-fallback">暂无封面</div>
                  </div>
                  <div class="recent-meta">
                    <h4>{{ book.title }}</h4>
                    <p>{{ book.author || '未知作者' }}</p>
                  </div>
                </el-card>
              </div>
            </div>
          </div>

          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message-row', msg.type]"
          >
            <div class="message-card">
              <div class="message-role">{{ msg.type === 'user' ? '我' : 'AI 图书助手' }}</div>
              <div class="message-content">{{ msg.content }}</div>
              <div v-if="msg.recommendations && msg.recommendations.length" class="message-books">
                <el-tag
                  v-for="book in msg.recommendations"
                  :key="`${msg.created_at || index}-${book.id || book.title}`"
                  type="info"
                  effect="plain"
                  class="book-tag"
                  @click="book.id && viewBookDetail(book.id)"
                >
                  {{ book.title }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>

        <div class="input-panel">
          <div class="hint-row" v-if="awaitingMood">
            <span>助手正在等待您的阅读心境补充，您可以自由描述。</span>
          </div>
          <el-input
            v-model="question"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="例如：余华有什么书；我最近想看点轻松一点的；帮我找心理学入门书"
            @keyup.ctrl.enter="handleAsk"
            clearable
          />
          <div class="action-row">
            <span class="shortcut">按 Ctrl+Enter 发送</span>
            <el-button type="primary" @click="handleAsk" :loading="asking">
              <el-icon><ChatLineRound /></el-icon>
              发送
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineRound } from '@element-plus/icons-vue'
import { chatWithAssistant, getChatHistory, saveChatMessage, clearChatHistory } from '../api/ai'
import { getBooks } from '../api/books'

export default {
  name: 'AIRecommend',
  components: {
    ChatLineRound
  },
  setup() {
    const router = useRouter()
    const question = ref('')
    const messages = ref([])
    const asking = ref(false)
    const awaitingMood = ref(false)
    const recentBooks = ref([])
    const messagesContainer = ref(null)

    const exampleQueries = [
      '余华有什么书',
      '余华有什么书，顺便推荐一本到两本',
      '帮我找心理学入门书',
      '最近想看点轻松一点的书',
      '你帮我挑两本适合最近看的书'
    ]

    const normalizeBooks = (books = []) => {
      const seen = new Set()
      return books.filter(book => {
        const key = book.id || book.title
        if (!key || seen.has(key)) {
          return false
        }
        seen.add(key)
        return true
      })
    }

    const saveMessage = async (type, content, recommendations = []) => {
      try {
        await saveChatMessage(type, content, recommendations)
      } catch (error) {
        console.error('保存消息失败:', error)
      }
    }

    const scrollToBottom = () => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    }

    const loadHistory = async () => {
      try {
        const res = await getChatHistory(50)
        if (res && res.messages) {
          messages.value = res.messages.map(msg => ({
            ...msg,
            recommendations: normalizeBooks(msg.recommendations || [])
          }))
          await nextTick()
          scrollToBottom()
        }
      } catch (error) {
        console.error('加载历史失败:', error)
      }
    }

    const loadRecentBooks = async () => {
      try {
        const res = await getBooks({ page: 1, per_page: 8 })
        recentBooks.value = res?.books || []
      } catch (error) {
        console.error('加载最近图书失败:', error)
      }
    }

    onMounted(() => {
      loadHistory()
      loadRecentBooks()
    })

    const useExample = (query) => {
      question.value = query
    }

    const buildRecentMessages = () => {
      return messages.value.slice(-6).map(item => ({
        type: item.type,
        content: item.content
      }))
    }

    const handleAsk = async () => {
      if (!question.value.trim()) {
        ElMessage.warning('请输入内容')
        return
      }

      const userQuestion = question.value.trim()
      messages.value.push({
        type: 'user',
        content: userQuestion,
        recommendations: []
      })
      question.value = ''
      asking.value = true

      await nextTick()
      scrollToBottom()
      saveMessage('user', userQuestion).catch(err => console.error(err))

      try {
        const recentMessages = buildRecentMessages()
        const res = await chatWithAssistant(userQuestion, recentMessages, awaitingMood.value)
        const displayBooks = normalizeBooks(res.display_books || [])
        awaitingMood.value = !!res.needs_clarification

        messages.value.push({
          type: 'ai',
          content: res.answer || '我已经处理好了，但这次没有生成可展示的回复。',
          recommendations: displayBooks
        })
        saveMessage('ai', res.answer || '', displayBooks).catch(err => console.error(err))
      } catch (error) {
        console.error(error)
        awaitingMood.value = false
        const fallback = '抱歉，这次助手没有处理成功，请稍后再试。'
        messages.value.push({
          type: 'ai',
          content: fallback,
          recommendations: []
        })
        saveMessage('ai', fallback).catch(err => console.error(err))
      } finally {
        asking.value = false
        await nextTick()
        scrollToBottom()
      }
    }

    const handleClearHistory = async () => {
      try {
        await ElMessageBox.confirm('确定清空当前 AI 对话记录吗？', '提示', { type: 'warning' })
        await clearChatHistory()
        messages.value = []
        awaitingMood.value = false
        ElMessage.success('对话已清空')
      } catch (error) {
        if (error !== 'cancel') {
          console.error(error)
        }
      }
    }

    const viewBookDetail = (bookId) => {
      router.push(`/books/${bookId}`)
    }

    return {
      question,
      messages,
      asking,
      awaitingMood,
      recentBooks,
      messagesContainer,
      exampleQueries,
      useExample,
      handleAsk,
      handleClearHistory,
      viewBookDetail
    }
  }
}
</script>

<style scoped>
.ai-assistant-page {
  padding: 16px;
}

.assistant-shell {
  min-height: calc(100vh - 130px);
}

.assistant-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.assistant-header h2 {
  margin: 0 0 6px 0;
}

.assistant-header p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.assistant-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.messages-panel {
  min-height: 420px;
  max-height: calc(100vh - 320px);
  overflow-y: auto;
  padding: 8px;
  background: #f7f8fa;
  border-radius: 10px;
}

.assistant-empty {
  padding: 18px;
}

.welcome-block h3,
.section-title h3 {
  margin: 0 0 8px 0;
  color: #303133;
}

.welcome-block p,
.section-title span {
  color: #909399;
  font-size: 13px;
}

.example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 18px 0 24px;
}

.example-tag,
.book-tag {
  cursor: pointer;
}

.recent-section {
  margin-top: 10px;
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.recent-book {
  cursor: pointer;
}

.recent-cover {
  width: 100%;
  height: 110px;
  border-radius: 8px;
  overflow: hidden;
  background: #f0f2f5;
  margin-bottom: 8px;
}

.recent-cover :deep(.el-image) {
  width: 100%;
  height: 100%;
}

.cover-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 12px;
}

.recent-meta h4 {
  margin: 0 0 6px 0;
  font-size: 13px;
  color: #303133;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.recent-meta p {
  margin: 0;
  color: #909399;
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.message-row {
  display: flex;
  margin-bottom: 14px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.ai {
  justify-content: flex-start;
}

.message-card {
  max-width: 80%;
  background: #fff;
  border-radius: 12px;
  padding: 12px 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.message-row.user .message-card {
  background: #409eff;
  color: #fff;
}

.message-role {
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 6px;
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

.message-books {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.input-panel {
  border-top: 1px solid #ebeef5;
  padding-top: 14px;
}

.hint-row {
  margin-bottom: 10px;
  color: #e67e22;
  font-size: 12px;
}

.action-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.shortcut {
  font-size: 12px;
  color: #909399;
}

@media (max-width: 900px) {
  .recent-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .message-card {
    max-width: 90%;
  }
}

@media (max-width: 768px) {
  .ai-assistant-page {
    padding: 8px;
  }

  .assistant-header {
    flex-direction: column;
    align-items: stretch;
  }

  .messages-panel {
    min-height: 360px;
    max-height: none;
  }
}

@media (max-width: 480px) {
  .recent-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .action-row {
    justify-content: flex-end;
  }

  .shortcut {
    display: none;
  }
}
</style>
