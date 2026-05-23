import api from './index'

export const analyzeBook = (bookId) => {
  // AI 分析可能较慢，单独延长超时
  return api.post(`/ai/analyze/${bookId}`, {}, { timeout: 30000 })
}

export const recommendBooks = (query, limit = 5) => {
  // 推荐可能较慢，单独延长超时
  return api.post('/ai/recommend', { query, limit }, { timeout: 30000 })
}

export const answerQuestion = (question) => {
  // 问答可能较慢，单独延长超时
  return api.post('/ai/qa', { question }, { timeout: 30000 })
}

export const chatWithAssistant = (message, recentMessages = [], awaitingMood = false) => {
  return api.post(
    '/ai/assistant/chat',
    { message, recent_messages: recentMessages, awaiting_mood: awaitingMood },
    { timeout: 45000 }
  )
}

// 获取对话历史
export const getChatHistory = (limit = 50) => {
  return api.get('/ai/chat/history', { params: { limit } })
}

// 保存对话消息
export const saveChatMessage = (type, content, recommendations = []) => {
  return api.post('/ai/chat/messages', { type, content, recommendations })
}

// 清空对话历史
export const clearChatHistory = () => {
  return api.delete('/ai/chat/history')
}
