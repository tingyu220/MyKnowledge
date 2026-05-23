import api from './index'

export const getDashboardSummary = (top = 10) => {
  return api.get('/dashboard/summary', { params: { top } })
}

export const getRecommendations = () => {
  return api.get('/dashboard/recommendations')
}

