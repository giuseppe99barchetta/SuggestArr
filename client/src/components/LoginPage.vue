<template>
  <div class="login-container">
    <div class="login-card">
      <img src="@/assets/logo.png" alt="SuggestArr" class="login-logo" />

      <h1>{{ cardTitle }}</h1>
      <p class="login-subtitle">{{ cardSubtitle }}</p>

      <!-- Login / Setup / Register form -->
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
            :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
            required
            :disabled="loading"
          />
        </div>

        <div v-if="isRegisterMode" class="form-group">
          <label>Confirm Password</label>
          <input
            v-model="confirmPassword"
            type="password"
            class="form-input"
            placeholder="Repeat password"
            autocomplete="new-password"
            required
            :disabled="loading"
          />
        </div>

        <p v-if="error" class="login-error">
          <i class="fas fa-exclamation-circle"></i> {{ error }}
        </p>

        <p v-if="successMsg" class="login-success">
          <i class="fas fa-check-circle"></i> {{ successMsg }}
        </p>

        <button type="submit" class="btn btn-primary login-btn" :disabled="loading">
          <i :class="submitIcon"></i>
          {{ submitLabel }}
        </button>
      </form>

      <!-- Register / Back-to-login toggle -->
      <div v-if="!isSetupMode && allowRegistration" class="login-toggle">
        <span v-if="!isRegisterMode">
          Don't have an account?
          <button class="toggle-link" @click="switchToRegister">Create one</button>
        </span>
        <span v-else>
          Already have an account?
          <button class="toggle-link" @click="switchToLogin">Sign in</button>
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import axios from 'axios'

export default {
  name: 'LoginPage',
  setup() {
    const router = useRouter()
    const route = useRoute()
    const { login, setupAdmin, accessToken } = useAuth()

    const username = ref('')
    const password = ref('')
    const confirmPassword = ref('')
    const loading = ref(false)
    const error = ref('')
    const successMsg = ref('')
    const isSetupMode = ref(false)
    const isRegisterMode = ref(false)
    const allowRegistration = ref(false)

    const cardTitle = computed(() => {
      if (isSetupMode.value) return 'Create Admin Account'
      if (isRegisterMode.value) return 'Create Account'
      return 'Sign In'
    })

    const cardSubtitle = computed(() => {
      if (isSetupMode.value) return 'Set up your admin credentials to get started.'
      if (isRegisterMode.value) return 'Choose a username and password.'
      return 'Enter your credentials to continue.'
    })

    const submitIcon = computed(() => {
      if (loading.value) return 'fas fa-spinner fa-spin'
      if (isSetupMode.value || isRegisterMode.value) return 'fas fa-user-plus'
      return 'fas fa-sign-in-alt'
    })

    const submitLabel = computed(() => {
      if (loading.value) return 'Please wait…'
      if (isSetupMode.value) return 'Create Admin Account'
      if (isRegisterMode.value) return 'Create Account'
      return 'Sign In'
    })

    onMounted(async () => {
      if (accessToken.value) {
        router.replace(route.query.redirect || '/dashboard')
        return
      }
      try {
        const response = await axios.get('/api/auth/status')
        isSetupMode.value = !response.data.auth_setup_complete
        allowRegistration.value = !!response.data.allow_registration
        console.log('allow_registration:', response.data.allow_registration)
      } catch {
        isSetupMode.value = false
        allowRegistration.value = false
      }
    })

    function switchToRegister() {
      error.value = ''
      successMsg.value = ''
      username.value = ''
      password.value = ''
      confirmPassword.value = ''
      isRegisterMode.value = true
    }

    function switchToLogin() {
      error.value = ''
      successMsg.value = ''
      username.value = ''
      password.value = ''
      confirmPassword.value = ''
      isRegisterMode.value = false
    }

    async function handleSubmit() {
      error.value = ''
      successMsg.value = ''
      loading.value = true
      try {
        if (isSetupMode.value) {
          await setupAdmin(username.value, password.value)
          await login(username.value, password.value)
          router.replace(route.query.redirect || '/dashboard')
        } else if (isRegisterMode.value) {
          if (password.value !== confirmPassword.value) {
            error.value = 'Passwords do not match.'
            return
          }
          await axios.post('/api/auth/register', { username: username.value, password: password.value })
          successMsg.value = 'Account created! You can now sign in.'
          switchToLogin()
        } else {
          await login(username.value, password.value)
          router.replace(route.query.redirect || '/dashboard')
        }
      } catch (err) {
        error.value = err.response?.data?.error || 'Authentication failed. Please try again.'
      } finally {
        loading.value = false
      }
    }

    return {
      username, password, confirmPassword,
      loading, error, successMsg,
      isSetupMode, isRegisterMode, allowRegistration,
      cardTitle, cardSubtitle, submitIcon, submitLabel,
      handleSubmit, switchToRegister, switchToLogin,
    }
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

.form-control {
  width: 100%;
  padding: 0.75rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-size: 1rem;
  transition: var(--transition-base);
}

.form-control:focus {
  outline: none;
  border-color: var(--color-primary);
  background: var(--color-bg-active);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-control:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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

.login-success {
  color: var(--color-success);
  font-size: 0.85rem;
  margin: 0;
}

.login-toggle {
  margin-top: 1.25rem;
  text-align: center;
  font-size: 0.85rem;
  color: var(--color-text-muted);
}

.toggle-link {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-primary);
  font-size: inherit;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.toggle-link:hover {
  color: #c4b5fd;
}
</style>
