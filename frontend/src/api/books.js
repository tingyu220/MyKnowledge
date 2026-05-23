import api from './index'

export const getBooks = (params) => {
  return api.get('/books', { params })
}

export const getBook = (id) => {
  return api.get(`/books/${id}`)
}

export const addBook = (isbnOrPayload) => {
  // 添加图书需爬取多数据源，耗时可超过 10s，单独延长超时
  // 支持两种调用方式：
  // 1. addBook(isbn) - 自动爬取，参数为字符串
  // 2. addBook({ isbn, title, author, ..., manual: true }) - 手动输入，参数为对象
  if (typeof isbnOrPayload === 'string') {
    // 自动模式：包装成 { isbn } 对象
    return api.post('/books/add', { isbn: isbnOrPayload }, { timeout: 60000 })
  }
  // 手动模式：直接发送对象
  return api.post('/books/add', isbnOrPayload, { timeout: 60000 })
}

export const updateBook = (id, data) => {
  return api.put(`/books/${id}`, data)
}

export const refreshBook = (id) => {
  // 重新爬取图书信息，耗时可超过 10s，单独延长超时
  return api.post(`/books/${id}/refresh`, {}, { timeout: 60000 })
}

export const deleteBook = (id) => {
  return api.delete(`/books/${id}`)
}

export const getCategories = () => {
  return api.get('/books/categories')
}

export const getTags = () => {
  return api.get('/books/tags')
}

