import api from './index'

export const getEbooks = (params) => {
  return api.get('/ebooks', { params })
}

export const uploadEbook = (formData) => {
  // 注意：不要手动设置 Content-Type（否则可能丢失 boundary，后端收不到 request.files）
  return api.post('/ebooks/upload', formData, { timeout: 60000 })
}

export const downloadEbook = (id) => {
  return api.get(`/ebooks/${id}`, {
    responseType: 'blob'
  })
}

export const deleteEbook = (id) => {
  return api.delete(`/ebooks/${id}`)
}

export const linkEbookToBook = (ebookId, bookId) => {
  return api.post(`/ebooks/${ebookId}/link`, { ebook_id: ebookId, book_id: bookId })
}

