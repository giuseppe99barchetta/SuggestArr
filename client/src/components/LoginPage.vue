<template>
  <div class="login-container">
    <div class="login-card">
      <img src="@/assets/logo.png" alt="SuggestArr" class="login-logo" />

      <h1>{{ isSetupMode ? 'Create Admin Account' : 'Sign In' }}</h1>
      <p class="login-subtitle">
        {{ isSetupMode ? 'Set up your admin credentials to get started.' : 'Enter your credentials to continue.' }}
      </p>

      <form @submit.prevent="handleSubmit" class="login-form">
        <div class="form-group">
          <label>Username</label>
          <input
            v-model="username"
            type="text"
            class="form-input"
            placeholder="Username"
            autocomplete="username"
            required
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label>Password</label>
          <input
            v-model="password"
            type="password"
            class="form-input"
            placeholder="Password"
            autocomplete="current-password"
            required
            :disabled="loading"
          />
        </div>

        <p v-if="error" class="login-error">
          <i class="fas fa-exclamation-circle"></i> {{ error }}
        </p>

        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          <i :class="loading ? 'fas fa-spinner fa-spin' : (isSetupMode ? 'fas fa-user-plus' : 'fas fa-sign-in-alt')"></i>
          {{ loading ? 'Please wait…' : (isSetupMode ? 'Create Account' : 'Sign In') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

export default {
  name: 'LoginPage',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const { login, setupAdmin, getAuthStatus, accessToken } = useAuth()

    const username = ref('')
    const password = ref('')
    const loading = ref(false)
    const error = ref('')
    const isSetupMode = ref(false)

    onMounted(async () => {
      // If already authenticated, go straight to dashboard
      if (accessToken.value) {
        router.replace(route.query.redirect || '/dashboard')
        return
      }
      const status = await getAuthStatus().catch(() => ({ auth_setup_complete: true }))
      isSetupMode.value = !status.auth_setup_complete
    })

    async function handleSubmit() {
      error.value = ''
      loading.value = true
      try {
        if (isSetupMode.value) {
          await setupAdmin(username.value, password.value)
          // After creating admin, log in automatically
          await login(username.value, password.value)
        } else {
          await login(username.value, password.value)
        }
        router.replace(route.query.redirect || '/dashboard')
      } catch (err) {
        error.value = err.response?.data?.error || 'Authentication failed. Please try again.'
      } finally {
        loading.value = false
      }
    }

    return { username, password, loading, error, isSetupMode, handleSubmit }
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-primary);
  background-image: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
}

.login-card {
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--border-radius-lg);
  padding: 2.5rem 2rem;
  width: 100%;
  max-width: 380px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.login-logo {
  height: 60px;
  margin-bottom: 1.25rem;
  display: initial !important;
}

h1 {
  color: var(--color-text-primary);
  font-size: 1.5rem;
  margin: 0 0 0.4rem;
}

.login-subtitle {
  color: var(--color-text-muted);
  font-size: 0.875rem;
  margin: 0 0 1.75rem;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  text-align: left;
}

.form-group label {
  display: block;
  color: var(--color-text-secondary);
  font-size: 0.85rem;
  margin-bottom: 0.35rem;
}

.login-error {
  color: var(--color-danger);
  font-size: 0.85rem;
  margin: 0;
}

.login-btn {
  width: 100%;
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}
</style>
