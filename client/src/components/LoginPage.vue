<template>
  <div class="flex min-h-screen items-center justify-center bg-canvas bg-[radial-gradient(ellipse_at_top,var(--color-brand-soft),transparent_65%)]">
    <div class="w-full max-w-[380px] rounded-card border border-white/12 bg-panel/90 px-8 py-10 text-center shadow-[0_8px_32px_rgba(0,0,0,0.4)] backdrop-blur-md">
      <img src="@/assets/logo.png" alt="SuggestArr" class="mx-auto mb-5 h-[60px]" />

      <h1 class="m-0 mb-1.5 text-2xl text-ink">{{ cardTitle }}</h1>
      <p class="m-0 mb-7 text-sm text-ink-4">{{ cardSubtitle }}</p>

      <!-- Login / Setup / Register form -->
      <form @submit.prevent="handleSubmit" class="flex flex-col gap-4 text-left">
        <label class="ui-label" for="login-username">
          Username
          <input
            id="login-username"
            v-model="username"
            type="text"
            class="ui-input"
            placeholder="Username"
            autocomplete="username"
            required
            :disabled="loading"
          />
        </label>

        <label class="ui-label" for="login-password">
          Password
          <input
            id="login-password"
            v-model="password"
            type="password"
            class="ui-input"
            placeholder="Password"
            :autocomplete="isRegisterMode ? 'new-password' : 'current-password'"
            required
            :disabled="loading"
          />
        </label>

        <label v-if="isRegisterMode" class="ui-label" for="login-confirm-password">
          Confirm Password
          <input
            id="login-confirm-password"
            v-model="confirmPassword"
            type="password"
            class="ui-input"
            placeholder="Repeat password"
            autocomplete="new-password"
            required
            :disabled="loading"
          />
        </label>

        <p v-if="error" class="m-0 text-[0.85rem] text-bad">
          <i aria-hidden="true" class="fas fa-exclamation-circle"></i> {{ error }}
        </p>

        <p v-if="successMsg" class="m-0 text-[0.85rem] text-good">
          <i aria-hidden="true" class="fas fa-check-circle"></i> {{ successMsg }}
        </p>

        <button type="submit" class="ui-btn-primary mt-2 w-full" :disabled="loading">
          <i aria-hidden="true" :class="submitIcon"></i>
          {{ submitLabel }}
        </button>
      </form>

      <!-- Register / Back-to-login toggle -->
      <div v-if="!isSetupMode && allowRegistration" class="mt-5 text-center text-[0.85rem] text-ink-4">
        <span v-if="!isRegisterMode">
          Don't have an account?
          <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline underline-offset-2 hover:text-ink" @click="switchToRegister">Create one</button>
        </span>
        <span v-else>
          Already have an account?
          <button type="button" class="cursor-pointer border-0 bg-transparent p-0 text-brand-ink underline underline-offset-2 hover:text-ink" @click="switchToLogin">Sign in</button>
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
