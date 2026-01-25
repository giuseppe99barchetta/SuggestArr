<template>
  <footer class="footer">
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
  </footer>
</template>

<script>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faGithub, faDocker, faDiscord } from '@fortawesome/free-brands-svg-icons';
import { library } from '@fortawesome/fontawesome-svg-core';

library.add(faGithub, faDocker, faDiscord);

export default {
  components: {
    FontAwesomeIcon,
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.5rem;
}

/* Version Section */
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

/* Responsive */
@media (max-width: 768px) {
  .footer {
    padding: 1.5rem 1rem;
    margin-top: 2rem;
  }

  .footer-version {
    flex-direction: column;
    gap: 0.5rem;
    text-align: center;
  }

  .version-text {
    font-size: 0.8rem;
  }

  .update-check-btn {
    padding: 0.3125rem 0.625rem;
    font-size: 0.8rem;
  }

  .footer-content {
    gap: 1rem;
  }

  .footer-link {
    width: 44px;
    height: 44px;
    font-size: 1.125rem;
    min-width: 44px; /* Ensure minimum touch target */
    min-height: 44px; /* Ensure minimum touch target */
  }
}

@media (max-width: 480px) {
  .footer {
    padding: 1rem;
  }

  .footer-version {
    gap: 0.375rem;
  }

  .version-text {
    font-size: 0.75rem;
  }

  .update-check-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
  }

  .update-badge {
    font-size: 0.6875rem;
    padding: 0.0625rem 0.25rem;
  }

  .footer-content {
    gap: 0.75rem;
  }

  .footer-link {
    width: 40px;
    height: 40px;
    font-size: 1rem;
    min-width: 40px;
    min-height: 40px;
  }
}
</style>
