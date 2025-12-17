<template>
  <footer class="footer">
    <!-- Logs Button 
    <div v-if="!isDashboardPage" class="logs-button-container">
      <button @click="toggleLogs" class="btn-logs">
        <font-awesome-icon icon="file-alt" class="logs-icon" />
        <span class="logs-text">View Logs</span>
      </button>
    </div>
    -->

    <!-- Social Links -->
    <div class="footer-content">
      <a 
        href="https://github.com/giuseppe99barchetta/SuggestArr" 
        target="_blank" 
        rel="noopener noreferrer"
        aria-label="GitHub"
        class="footer-link"
      >
        <font-awesome-icon :icon="['fab', 'github']" />
      </a>
      <a 
        href="https://hub.docker.com/repository/docker/ciuse99/suggestarr/" 
        target="_blank" 
        rel="noopener noreferrer"
        aria-label="Docker"
        class="footer-link"
      >
        <font-awesome-icon :icon="['fab', 'docker']" />
      </a>

      <a 
        href="https://discord.gg/JXwFd3PnXY" 
        target="_blank" 
        rel="noopener noreferrer"
        aria-label="Discord"
        class="footer-link"
      >
        <font-awesome-icon :icon="['fab', 'discord']" />
      </a>
    </div>

    <!-- Logs Modal -->
    <Transition name="modal">
      <div v-if="showLogs" class="modal-overlay" @click.self="toggleLogs">
        <div class="modal-container" @click.stop>
          <!-- Modal Header -->
          <div class="modal-header">
            <div class="modal-header-left">
              <div class="modal-icon">
                <font-awesome-icon icon="file-alt" />
              </div>
              <div>
                <h2 class="modal-title">System Logs</h2>
              </div>
            </div>
            
            <button @click="toggleLogs" class="btn-close" aria-label="Close modal">
              <font-awesome-icon icon="times" />
            </button>
          </div>

          <!-- Modal Body -->
          <div class="modal-body">
            <LogsComponent />
          </div>

          <!-- Modal Footer (Optional) -->
          <div class="modal-footer">
            <button @click="toggleLogs" class="btn-modal-action">
              <font-awesome-icon icon="times" />
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </footer>
</template>

<script>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faGithub, faDocker, faReddit, faDiscord } from '@fortawesome/free-brands-svg-icons';
import { faFileAlt, faTimes, faCircle } from '@fortawesome/free-solid-svg-icons';
import { library } from '@fortawesome/fontawesome-svg-core';
import LogsComponent from './LogsComponent.vue';

library.add(faGithub, faDocker, faReddit, faFileAlt, faDiscord, faTimes, faCircle);

export default {
  components: {
    FontAwesomeIcon,
    LogsComponent
  },
  data() {
    return {
      showLogs: false,
      hasNewLogs: false // Set to true when new logs arrive
    };
  },
  computed: {
    isDashboardPage() {
      return this.$route.name === 'Dashboard' || this.$route.path === '/dashboard' || this.$route.path === '/';
    }
  },
  methods: {
    toggleLogs() {
      this.showLogs = !this.showLogs;
      
      // Prevent body scroll when modal is open
      if (this.showLogs) {
        document.body.style.overflow = 'hidden';
        this.$nextTick(() => {
          const overlay = document.querySelector('.modal-overlay');
          if (overlay) {
            overlay.scrollTop = 0;
          }
        });
      } else {
        document.body.style.overflow = '';
      }
    }
  },
  beforeUnmount() {
    // Clean up
    document.body.style.overflow = '';
  }
};
</script>

<style scoped>
/* Footer */
.footer {
  padding: 2rem 1rem;
  text-align: center;
  margin-top: 3rem;
  border-top: 1px solid var(--color-border-light);
}

/* Logs Button */
.logs-button-container {
  margin-bottom: 1.5rem;
  display: flex;
  justify-content: center;
}

.btn-logs {
  display: inline-flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-md);
  color: var(--color-text-primary);
  font-size: 0.9375rem;
  font-weight: 500;
  cursor: pointer;
  transition: var(--transition-base);
  position: relative;
}

.btn-logs:hover {
  background: var(--color-bg-active);
  border-color: var(--color-primary);
  transform: translateY(-2px);
  box-shadow: var(--shadow-base);
}

.logs-icon {
  font-size: 1.125rem;
}

.logs-text {
  font-size: 0.9375rem;
}

.logs-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 12px;
  height: 12px;
  color: var(--color-danger);
  font-size: 0.75rem;
}

.pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* Social Links */
.footer-content {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.footer-link {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-md);
  color: var(--color-text-muted);
  font-size: 1.25rem;
  transition: var(--transition-base);
}

.footer-link:hover {
  background: var(--color-bg-active);
  border-color: var(--color-border-medium);
  color: var(--color-text-primary);
  transform: translateY(-2px);
}

/* Modal Overlay */
.modal-overlay {
  position: fixed !important;
  inset: 0;
  width: 100%;
  height: 100%;
  background: var(--color-bg-overlay-heavy);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  padding: 1rem;
  place-items: center; 
}

/* Modal Container */
.modal-container {
  background: var(--color-bg-content);
  backdrop-filter: blur(20px);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-xl);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  max-width: 1200px;
  width: 100%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Modal Header */
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-bg-overlay-light);
}

.modal-header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.modal-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-md);
  color: var(--color-text-secondary);
  font-size: 1.25rem;
}

.modal-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-text-primary);
}

.modal-subtitle {
  margin: 0.25rem 0 0 0;
  font-size: 0.875rem;
  color: var(--color-text-muted);
}

.btn-close {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-muted);
  font-size: 1.25rem;
  cursor: pointer;
  transition: var(--transition-base);
}

.btn-close:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: var(--color-danger);
  color: var(--color-danger);
  transform: rotate(90deg);
}

/* Modal Body */
.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 2rem;
}

.modal-body::-webkit-scrollbar {
  width: 10px;
}

.modal-body::-webkit-scrollbar-track {
  background: var(--color-bg-overlay-light);
}

.modal-body::-webkit-scrollbar-thumb {
  background: var(--color-primary);
  border-radius: var(--border-radius-sm);
}

.modal-body::-webkit-scrollbar-thumb:hover {
  background: var(--color-primary-hover);
}

/* Modal Footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 2rem;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-bg-overlay-light);
}

.btn-modal-action {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: var(--color-bg-interactive);
  border: 1px solid var(--color-border-medium);
  border-radius: var(--border-radius-sm);
  color: var(--color-text-primary);
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition-base);
}

.btn-modal-action:hover {
  background: var(--color-bg-active);
  border-color: var(--color-primary);
}

/* Modal Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container {
  transform: scale(0.9) translateY(20px);
  opacity: 0;
}

.modal-leave-to .modal-container {
  transform: scale(0.9) translateY(20px);
  opacity: 0;
}

/* Responsive */
@media (max-width: 768px) {
  .modal-container {
    max-width: 100%;
    max-height: 95vh;
    margin: 0;
    border-radius: var(--border-radius-lg);
  }

  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem 1.25rem;
  }

  .modal-title {
    font-size: 1.25rem;
  }

  .modal-icon {
    width: 40px;
    height: 40px;
    font-size: 1rem;
  }

  .footer-content {
    gap: 1rem;
  }

  .footer-link {
    width: 40px;
    height: 40px;
    font-size: 1.125rem;
  }
}
</style>
