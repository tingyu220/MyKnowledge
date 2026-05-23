import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Layout from '../views/Layout.vue'
import Dashboard from '../views/Dashboard.vue'
import BookList from '../views/BookList.vue'
import BookDetail from '../views/BookDetail.vue'
import BookAdd from '../views/BookAdd.vue'
import EbookManage from '../views/EbookManage.vue'
import EbookViewer from '../views/EbookViewer.vue'
import AIRecommend from '../views/AIRecommend.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: Dashboard
      },
      {
        path: 'books',
        name: 'BookList',
        component: BookList
      },
      {
        path: 'books/add',
        name: 'BookAdd',
        component: BookAdd
      },
      {
        path: 'books/:id',
        name: 'BookDetail',
        component: BookDetail
      },
      {
        path: 'ebooks',
        name: 'EbookManage',
        component: EbookManage
      },
      {
        path: 'ebooks/:id/view',
        name: 'EbookViewer',
        component: EbookViewer
      },
      {
        path: 'ai',
        name: 'AIRecommend',
        component: AIRecommend
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router

