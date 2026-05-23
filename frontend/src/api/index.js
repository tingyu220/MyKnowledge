import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

// 检测是否需要使用绝对路径
// 手机扫码访问时，window.location.hostname 会是电脑IP，需要直接请求后端
const isMobileAccess = () => {
  const host = window.location.hostname
  return host !== 'localhost' && host !== '127.0.0.1'
}

const getBaseURL = () => {
  if (isMobileAccess()) {
    // 手机访问：使用当前主机+5000端口
    const host = window.location.hostname
    return `http://${host}:5000/api`
  }
  // PC访问：使用相对路径，通过vite代理
  return '/api'
}

const api = axios.create({
  baseURL: getBaseURL(),
  timeout: 10000,
  withCredentials: true
})

api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API错误:', {
      message: error.message,
      response: error.response,
      config: error.config
    })
    
    if (error.response) {
      const status = error.response.status
      const data = error.response.data
      
      if (status === 401) {
        localStorage.removeItem('token')
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
      } else {
        const errorMsg = data?.error || data?.message || '请求失败'
        ElMessage.error(errorMsg)
      }
    } else if (error.request) {
      ElMessage.error('无法连接到服务器，请检查后端服务是否启动（端口5000）')
    } else {
      ElMessage.error('请求配置错误: ' + error.message)
    }
    return Promise.reject(error)
  }
)

export default api
