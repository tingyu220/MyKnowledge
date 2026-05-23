<template>
  <el-container>
    <el-header>
      <div class="header-content">
        <!-- Logo区域 -->
        <div class="header-brand">
          <!-- 移动端菜单按钮 -->
          <el-button class="mobile-menu-btn" @click="toggleSidebar" text>
            <el-icon size="22"><Fold /></el-icon>
          </el-button>
          <div class="logo">
            <el-icon size="28"><Reading /></el-icon>
          </div>
          <h1 class="site-title">个人图书管理系统</h1>
        </div>

        <!-- 用户信息区域 -->
        <div class="header-actions">
          <el-dropdown @command="handleCommand" trigger="click">
            <span class="user-info">
              <el-avatar :size="32" class="user-avatar">
                <el-icon size="18"><User /></el-icon>
              </el-avatar>
              <span class="username">{{ currentUser?.username || '用户' }}</span>
              <el-icon class="arrow-icon"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>

    <!-- 移动端遮罩层 -->
    <div class="sidebar-overlay" :class="{ show: sidebarVisible }" @click="sidebarVisible = false"></div>

    <el-container>
      <el-aside :class="{ show: sidebarVisible }">
        <el-menu
          :default-active="activeMenu"
          router
          background-color="#545c64"
          text-color="#fff"
          active-text-color="#ffd04b"
          @select="onMenuSelect"
        >
          <el-menu-item index="/dashboard">
            <el-icon><DataAnalysis /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/books">
            <el-icon><Reading /></el-icon>
            <span>图书管理</span>
          </el-menu-item>
          <el-menu-item index="/ebooks">
            <el-icon><Document /></el-icon>
            <span>电子书管理</span>
          </el-menu-item>
          <el-menu-item index="/ai">
            <el-icon><ChatLineRound /></el-icon>
            <span>AI助手</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, ArrowDown, Reading, Document, ChatLineRound, DataAnalysis, Fold, SwitchButton } from '@element-plus/icons-vue'
import { logout } from '../api/auth'

export default {
  name: 'Layout',
  components: {
    User,
    ArrowDown,
    Reading,
    Document,
    ChatLineRound,
    DataAnalysis,
    Fold,
    SwitchButton
  },
  setup() {
    const router = useRouter()
    const route = useRoute()
    const currentUser = ref(null)
    const sidebarVisible = ref(false)

    const activeMenu = computed(() => route.path)

    const toggleSidebar = () => {
      sidebarVisible.value = !sidebarVisible.value
    }

    const onMenuSelect = () => {
      if (window.innerWidth <= 768) {
        sidebarVisible.value = false
      }
    }

    onMounted(() => {
      const userStr = localStorage.getItem('user')
      if (userStr) {
        currentUser.value = JSON.parse(userStr)
      }
    })

    const handleCommand = async (command) => {
      if (command === 'logout') {
        try {
          await logout()
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          ElMessage.success('已退出登录')
          router.push('/login')
        } catch (error) {
          console.error(error)
        }
      }
    }

    return {
      currentUser,
      activeMenu,
      sidebarVisible,
      toggleSidebar,
      onMenuSelect,
      handleCommand
    }
  }
}
</script>

<style scoped>
/* 基础布局 */
.el-header {
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  color: white;
  line-height: 60px;
  padding: 0 24px;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.3);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1400px;
  margin: 0 auto;
  height: 100%;
}

/* Logo区域 */
.header-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.site-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: white;
  letter-spacing: 1px;
  white-space: nowrap;
}

/* 用户信息区域 */
.header-actions {
  display: flex;
  align-items: center;
}

.user-info {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
  color: white;
}

.user-info:hover {
  background: rgba(255, 255, 255, 0.2);
}

.user-avatar {
  background: rgba(255, 255, 255, 0.3);
  color: white;
}

.username {
  font-size: 14px;
  font-weight: 500;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arrow-icon {
  font-size: 12px;
  transition: transform 0.3s;
}

.user-info:hover .arrow-icon {
  transform: rotate(180deg);
}

/* 侧边栏 */
.el-aside {
  background-color: #2c3e50;
  transition: width 0.3s;
  overflow: hidden;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1);
}

/* 主内容区 */
.el-main {
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
  padding: 20px;
}

/* 桌面端适配 */
@media (min-width: 769px) {
  .el-aside {
    display: block;
  }

  .mobile-menu-btn {
    display: none !important;
  }
}

/* 移动端适配 */
@media (max-width: 768px) {
  .el-header {
    padding: 0 16px;
    line-height: 56px;
  }

  .site-title {
    font-size: 15px;
  }

  .logo {
    width: 36px;
    height: 36px;
  }

  .logo .el-icon {
    font-size: 20px;
  }

  .username {
    display: none;
  }

  .user-info {
    padding: 4px 8px;
    background: transparent;
  }

  .user-info:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .el-main {
    padding: 12px;
  }

  .mobile-menu-btn {
    display: flex !important;
  }

  .el-aside {
    position: fixed;
    left: -200px;
    top: 56px;
    bottom: 0;
    z-index: 1000;
    width: 200px !important;
    transition: left 0.3s;
    background-color: #2c3e50;
  }

  .el-aside.show {
    left: 0;
  }

  .sidebar-overlay {
    display: none;
    position: fixed;
    top: 56px;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }

  .sidebar-overlay.show {
    display: block;
  }
}
</style>
