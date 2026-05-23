import api from './index'

export const login = (username, password) => {
  return api.post('/auth/login', { username, password })
}

export const register = (username, password, email) => {
  return api.post('/auth/register', { username, password, email })
}

export const logout = () => {
  return api.post('/auth/logout')
}

export const getCurrentUser = () => {
  return api.get('/auth/me')
}

