<template>
  <div class="auth-page">
    <div class="auth-shell">
      <div class="auth-decoration" aria-hidden="true" />
      <div class="auth-card">
        <p class="auth-brand">个人知识管理系统</p>
        <h1 class="auth-title">{{ activeTab === 'login' ? '登录' : '注册' }}</h1>

        <el-form
          v-show="activeTab === 'login'"
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="auth-form"
          label-position="top"
          hide-required-asterisk
          @submit.prevent
        >
          <el-form-item prop="username">
            <template #label>
              <span class="field-label">用户名</span>
            </template>
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              class="auth-input"
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item prop="password">
            <template #label>
              <span class="field-label">密码</span>
            </template>
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              class="auth-input"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <div class="auth-actions">
            <el-button
              class="auth-btn-primary"
              :loading="loading"
              native-type="button"
              @click="handleLogin"
            >
              登录
            </el-button>
            <button type="button" class="auth-link-muted" @click="onForgotPassword">
              忘记密码？
            </button>
          </div>
          <p class="auth-footer-line">
            还没有账号？
            <button type="button" class="auth-link-accent" @click="switchTab('register')">
              注册
            </button>
          </p>
        </el-form>

        <el-form
          v-show="activeTab === 'register'"
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          class="auth-form"
          label-position="top"
          hide-required-asterisk
          @submit.prevent
        >
          <el-form-item prop="username">
            <template #label>
              <span class="field-label">用户名</span>
            </template>
            <el-input v-model="registerForm.username" placeholder="请输入用户名" size="large" class="auth-input" />
          </el-form-item>
          <el-form-item prop="password">
            <template #label>
              <span class="field-label">密码</span>
            </template>
            <el-input v-model="registerForm.password" type="password" placeholder="请输入密码" size="large" class="auth-input" show-password />
          </el-form-item>
          <el-form-item prop="confirmPassword">
            <template #label>
              <span class="field-label">确认密码</span>
            </template>
            <el-input v-model="registerForm.confirmPassword" type="password" placeholder="请再次输入密码" size="large" class="auth-input" show-password />
          </el-form-item>
          <el-form-item prop="email">
            <template #label>
              <span class="field-label">邮箱（可选）</span>
            </template>
            <el-input v-model="registerForm.email" placeholder="请输入邮箱" size="large" class="auth-input" />
          </el-form-item>
          <div class="auth-actions auth-actions-register">
            <el-button
              class="auth-btn-primary"
              :loading="loading"
              native-type="button"
              @click="handleRegister"
            >
              注册
            </el-button>
          </div>
          <p class="auth-footer-line">
            已有账号？
            <button type="button" class="auth-link-accent" @click="switchTab('login')">
              登录
            </button>
          </p>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '../api/auth'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    const activeTab = ref('login')
    const loading = ref(false)
    const loginFormRef = ref(null)
    const registerFormRef = ref(null)

    const loginForm = reactive({
      username: '',
      password: '',
    })

    const registerForm = reactive({
      username: '',
      password: '',
      confirmPassword: '',
      email: '',
    })

    const loginRules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
    }

    const validateConfirmPassword = (rule, value, callback) => {
      if (value !== registerForm.password) {
        callback(new Error('两次输入的密码不一致'))
      } else {
        callback()
      }
    }

    const registerRules = {
      username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
      password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
      confirmPassword: [
        { required: true, message: '请再次输入密码', trigger: 'blur' },
        { validator: validateConfirmPassword, trigger: 'blur' },
      ],
      email: [{ type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur', required: false }],
    }

    const clearFormsValidate = () => {
      loginFormRef.value?.clearValidate()
      registerFormRef.value?.clearValidate()
    }

    const switchTab = (tab) => {
      activeTab.value = tab
      clearFormsValidate()
    }

    const onForgotPassword = () => {
      ElMessage.info('请联系管理员或通过数据库重置密码')
    }

    const handleLogin = async () => {
      if (!loginFormRef.value) return
      await loginFormRef.value.validate(async (valid) => {
        if (!valid) return
        loading.value = true
        try {
          const res = await login(loginForm.username, loginForm.password)
          localStorage.setItem('token', 'logged_in')
          localStorage.setItem('user', JSON.stringify(res.user))
          ElMessage.success('登录成功')
          router.push('/')
        } catch (error) {
          console.error('登录错误:', error)
          if (!error.response) {
            ElMessage.error('网络错误，请检查后端服务是否启动')
          }
        } finally {
          loading.value = false
        }
      })
    }

    const handleRegister = async () => {
      if (!registerFormRef.value) return
      await registerFormRef.value.validate(async (valid) => {
        if (!valid) return
        loading.value = true
        try {
          await register(registerForm.username, registerForm.password, registerForm.email)
          ElMessage.success('注册成功，请登录')
          activeTab.value = 'login'
          loginForm.username = registerForm.username
          registerForm.username = ''
          registerForm.password = ''
          registerForm.confirmPassword = ''
          registerForm.email = ''
          clearFormsValidate()
        } catch (error) {
          console.error('注册错误:', error)
          if (!error.response) {
            ElMessage.error('网络错误，请检查后端服务是否启动')
          }
        } finally {
          loading.value = false
        }
      })
    }

    return {
      activeTab,
      loading,
      loginForm,
      registerForm,
      loginRules,
      registerRules,
      loginFormRef,
      registerFormRef,
      handleLogin,
      handleRegister,
      switchTab,
      onForgotPassword,
    }
  },
}
</script>

<style scoped>
/* Day 1358 Sign-in 风格：浅底、白卡片、紫辅色 #4949E8、深字 #0F1128、描边 #C5D0E6 */
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  background: #edf3ff;
  font-family:
    'Inter',
    'Segoe UI',
    system-ui,
    -apple-system,
    sans-serif;
}

.auth-shell {
  position: relative;
  width: 100%;
  max-width: 920px;
  min-height: 560px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-decoration {
  position: absolute;
  right: 8%;
  top: 50%;
  transform: translateY(-50%);
  width: min(42%, 380px);
  height: min(88vh, 640px);
  max-height: 640px;
  background: #4949e8;
  border-radius: 15px;
  box-shadow: 0 16px 60px -20px rgba(10, 10, 10, 0.18);
  z-index: 0;
}

.auth-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 498px;
  padding: 40px 44px 36px;
  background: #fff;
  border-radius: 15px;
  box-shadow: 0 16px 48px -24px rgba(15, 17, 40, 0.12);
  margin-right: auto;
  margin-left: 0;
}

.auth-brand {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  letter-spacing: 0.02em;
}

.auth-title {
  margin: 0 0 28px;
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  color: #0f1128;
  letter-spacing: -0.02em;
}

.auth-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.auth-form :deep(.el-form-item__label) {
  display: block;
  width: 100% !important;
  text-align: left;
  margin-bottom: 8px;
  padding: 0;
  height: auto;
  line-height: 1.3;
}

.field-label {
  font-size: 14px;
  font-weight: 700;
  color: #0f1128;
}

.auth-form :deep(.auth-input .el-input__wrapper) {
  min-height: 52px;
  padding: 4px 16px;
  border-radius: 10px;
  box-shadow: none !important;
  border: 2px solid #c5d0e6;
  background: #fff;
}

.auth-form :deep(.auth-input .el-input__wrapper:hover) {
  border-color: #a8b8d8;
}

.auth-form :deep(.auth-input .el-input__wrapper.is-focus) {
  border-color: #4949e8;
}

.auth-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px 20px;
  margin-top: 8px;
  margin-bottom: 24px;
}

.auth-actions-register {
  margin-bottom: 16px;
}

.auth-btn-primary {
  min-width: 148px;
  height: 48px !important;
  padding: 0 28px !important;
  font-size: 16px !important;
  font-weight: 700 !important;
  border-radius: 999px !important;
  border: none !important;
  background: #4949e8 !important;
  color: #fff !important;
}

.auth-btn-primary:hover,
.auth-btn-primary:focus {
  background: #3d3ad4 !important;
  color: #fff !important;
}

.auth-link-muted {
  border: none;
  background: none;
  padding: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f1128;
  cursor: pointer;
  font-family: inherit;
}

.auth-link-muted:hover {
  color: #4949e8;
  text-decoration: underline;
}

.auth-footer-line {
  margin: 0;
  text-align: center;
  font-size: 15px;
  font-weight: 600;
  color: #0f1128;
}

.auth-link-accent {
  border: none;
  background: none;
  padding: 0;
  margin-left: 4px;
  font-size: 15px;
  font-weight: 700;
  color: #0f1128;
  text-decoration: underline;
  cursor: pointer;
  font-family: inherit;
}

.auth-link-accent:hover {
  color: #4949e8;
}

@media (max-width: 768px) {
  .auth-decoration {
    right: 50%;
    transform: translate(50%, -45%);
    width: 88%;
    height: 420px;
    opacity: 0.92;
  }

  .auth-card {
    margin: 0 auto;
    max-width: 100%;
    padding: 32px 24px 28px;
  }

  .auth-title {
    font-size: 26px;
  }

  .auth-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .auth-btn-primary {
    width: 100%;
  }

  .auth-link-muted {
    text-align: center;
  }
}
</style>
