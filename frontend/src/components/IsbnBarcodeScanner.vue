<template>
  <el-dialog
    v-model="visible"
    title="扫描 ISBN 条码"
    width="95%"
    :close-on-click-modal="false"
    destroy-on-close
    @close="stop"
    class="scanner-dialog"
  >
    <div class="scanner-wrap">
      <div v-if="error" class="scanner-error">
        <el-icon size="40"><WarningFilled /></el-icon>
        <p>{{ error }}</p>
        <el-button type="primary" size="small" @click="retry" v-if="canRetry">重试</el-button>
      </div>
      <div v-else-if="readerReady" class="scanner-view">
        <component
          :is="readerComponent"
          :key="readerKey"
          @loaded="onReaderLoaded"
          @onloading="onReaderLoading"
          @result="onResult"
        />
      </div>
      <div v-else class="scanner-loading">
        <el-icon class="loading-icon" size="40"><Loading /></el-icon>
        <p>正在启动摄像头…</p>
        <p class="hint">请允许调用摄像头权限</p>
      </div>
    </div>
    <template #footer>
      <el-button @click="close">取消</el-button>
    </template>
  </el-dialog>
</template>

<script>
import { ref, watch, shallowRef, onUnmounted } from 'vue'
import { WarningFilled, Loading } from '@element-plus/icons-vue'

/** 从条码/二维码中提取 ISBN（与后端 normalize 一致：NFKC、GTIN-14、长串中的 978/979） */
function extractIsbn(str) {
  if (!str || typeof str !== 'string') return null
  let s = str.normalize('NFKC').replace(/[^0-9X]/gi, '').toUpperCase()
  if (!s) return null
  if (s.length === 14 && /^\d{14}$/.test(s) && s[0] === '0') {
    s = s.slice(1)
  }
  if (s.length > 13) {
    const m = s.match(/(?:978|979)\d{10}/)
    if (m) s = m[0]
    else return null
  }
  if (s.length === 10 && /^\d{9}[\dX]$/.test(s)) return s
  if (s.length === 13 && /^\d{13}$/.test(s)) return s
  return null
}

export default {
  name: 'IsbnBarcodeScanner',
  components: { WarningFilled, Loading },
  props: {
    modelValue: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'scan'],
  setup(props, { emit }) {
    const visible = ref(false)
    const readerReady = ref(false)
    const readerComponent = shallowRef(null)
    const readerKey = ref(0)
    const error = ref('')
    const canRetry = ref(false)
    const readerLoaded = ref(false)
    let startupTimer = null

    console.log('IsbnBarcodeScanner 创建, modelValue:', props.modelValue)

    const clearStartupTimer = () => {
      if (startupTimer) {
        clearTimeout(startupTimer)
        startupTimer = null
      }
    }

    const setCameraError = (err) => {
      const host = window.location.host
      const origin = window.location.origin
      const name = err?.name || err?.code

      if (name === 'insecure-context') {
        error.value = `当前地址 ${origin} 没有被浏览器识别为可信安全上下文，摄像头不会弹权限框。请重启前端以按当前 IP 重建证书；如果手机仍提示证书不受信任，需要先在手机上信任该证书。`
        canRetry.value = true
        return
      }

      if (name === 'permission-denied') {
        error.value = '浏览器已拒绝摄像头权限。请在手机浏览器站点设置中允许摄像头，然后重新打开扫码。'
        canRetry.value = true
        return
      }

      if (name === 'unsupported-media-devices') {
        error.value = '当前浏览器不支持摄像头调用，或页面不在受支持的安全环境中。'
        canRetry.value = false
        return
      }

      if (name === 'NotAllowedError' || name === 'SecurityError') {
        error.value = `浏览器阻止了 ${host} 的摄像头访问。若系统没有弹权限框，通常是因为当前 HTTPS 证书对这个 IP 不可信。请重新生成证书后再试。`
        canRetry.value = true
        return
      }

      if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        error.value = '没有检测到可用摄像头，请确认手机摄像头可用后重试。'
        canRetry.value = true
        return
      }

      error.value = '摄像头启动失败。若页面未弹出权限请求，请优先检查当前 HTTPS 证书是否对这个 IP 受信任。'
      canRetry.value = true
    }

    const preflightCameraAccess = async () => {
      if (!window.isSecureContext) {
        const insecureError = new Error('Insecure context')
        insecureError.code = 'insecure-context'
        throw insecureError
      }

      if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
        const unsupportedError = new Error('MediaDevices API unavailable')
        unsupportedError.code = 'unsupported-media-devices'
        throw unsupportedError
      }

      if (navigator.permissions?.query) {
        try {
          const permission = await navigator.permissions.query({ name: 'camera' })
          if (permission.state === 'denied') {
            const deniedError = new Error('Camera permission denied')
            deniedError.code = 'permission-denied'
            throw deniedError
          }
        } catch (permissionError) {
          if (
            permissionError?.code === 'permission-denied' ||
            permissionError?.name === 'permission-denied'
          ) {
            throw permissionError
          }
        }
      }
    }

    const startStartupGuard = () => {
      clearStartupTimer()
      startupTimer = setTimeout(() => {
        if (visible.value && readerReady.value && !readerLoaded.value) {
          setCameraError({ name: 'NotAllowedError' })
          readerReady.value = false
          readerComponent.value = null
        }
      }, 5000)
    }

    const close = () => {
      console.log('close 被调用')
      visible.value = false
      emit('update:modelValue', false)
    }

    const stop = () => {
      console.log('stop 被调用')
      clearStartupTimer()
      readerReady.value = false
      readerComponent.value = null
      readerLoaded.value = false
      error.value = ''
      canRetry.value = false
    }

    const retry = () => {
      console.log('retry 被调用')
      stop()
      loadScanner()
    }

    const loadScanner = async () => {
      console.log('loadScanner 开始')
      error.value = ''
      canRetry.value = false
      readerReady.value = false
      readerComponent.value = null
      readerLoaded.value = false

      try {
        await preflightCameraAccess()
      } catch (preflightError) {
        console.error('摄像头预检查失败:', preflightError)
        setCameraError(preflightError)
        return
      }

      import('vue3-barcode-qrcode-reader')
        .then((mod) => {
          console.log('扫码库加载成功, 模块内容:', Object.keys(mod))
          // 尝试多种可能的导出方式
          const C = mod.StreamQrcodeBarcodeReader || 
                    mod.default?.StreamQrcodeBarcodeReader ||
                    (mod.default && (mod.default.StreamQrcodeBarcodeReader || mod.default.StreamBarcodeReader)) ||
                    mod.default
          console.log('找到的组件:', C, '类型:', typeof C)
          if (C && (typeof C === 'function' || (typeof C === 'object' && C !== null))) {
            console.log('设置 readerComponent')
            readerComponent.value = C
            readerKey.value += 1
            readerReady.value = true
            startStartupGuard()
            console.log('readerReady 设置为 true')
          } else {
            console.log('组件未找到, mod:', mod)
            error.value = '扫码组件未找到'
            canRetry.value = true
          }
        })
        .catch((e) => {
          console.error('扫码组件加载错误:', e)
          setCameraError(e)
        })
    }

    const onReaderLoaded = () => {
      readerLoaded.value = true
      clearStartupTimer()
    }

    const onReaderLoading = (loading) => {
      if (loading) {
        readerLoaded.value = true
        clearStartupTimer()
      }
    }

    const onResult = (payload) => {
      const raw = (payload && (payload.rawValue ?? payload.decodedText ?? payload.text)) || (typeof payload === 'string' ? payload : '')
      console.log('[扫码器] 原始结果:', raw, '类型:', typeof raw)
      const isbn = extractIsbn(raw)
      console.log('[扫码器] 解析结果:', isbn)
      if (isbn) {
        emit('scan', isbn)
        close()
      }
    }

    watch(
      () => props.modelValue,
      (val) => {
        visible.value = !!val
        if (!val) {
          stop()
          return
        }
        loadScanner()
      },
      { immediate: true }
    )

    watch(visible, (v) => {
      if (!v) emit('update:modelValue', false)
    })

    onUnmounted(stop)

    return {
      visible,
      readerReady,
      readerComponent,
      readerKey,
      error,
      canRetry,
      close,
      stop,
      retry,
      onReaderLoaded,
      onReaderLoading,
      onResult
    }
  }
}
</script>

<style scoped>
.scanner-dialog {
  max-width: 500px;
}

.scanner-wrap {
  min-height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #1a1a1a;
  border-radius: 12px;
  overflow: hidden;
}

.scanner-view {
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

.scanner-view :deep(video) {
  width: 100%;
  max-height: 350px;
  object-fit: cover;
}

.scanner-loading,
.scanner-error {
  color: #fff;
  padding: 2rem;
  text-align: center;
}

.scanner-loading p {
  margin: 12px 0 0 0;
}

.scanner-loading .hint {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

.loading-icon {
  animation: rotate 1.5s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.scanner-error {
  color: #f56c6c;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.scanner-error p {
  margin: 0;
}

/* 移动端适配 */
@media (max-width: 480px) {
  .scanner-wrap {
    min-height: 240px;
  }

  .scanner-view :deep(video) {
    max-height: 280px;
  }
}
</style>
