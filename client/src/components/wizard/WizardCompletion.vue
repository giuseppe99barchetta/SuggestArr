<template>
  <div>
    <div class="success-icon">
      <i class="fas fa-check-circle"></i>
    </div>

    <h1>Setup Complete!</h1>
    <p class="completion-subtitle">
      SuggestArr is now configured and ready to suggest content from your media server.
    </p>

    <div class="next-steps">
      <h3>What's Next?</h3>
      <ul>
        <li>View and manage your suggestions in the <strong>Requests</strong> page</li>
        <li>Fine-tune your preferences in <strong>Settings</strong></li>
        <li>Run your first content suggestion manually</li>
      </ul>
    </div>

    <div class="completion-actions">
      <button @click="$emit('go-settings')" class="action-btn secondary">
        <i class="fas fa-cog"></i>
        Go to Settings
      </button>
      <button @click="$emit('go-requests')" class="action-btn primary">
        <i class="fas fa-list-alt"></i>
        View Suggestions
      </button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'WizardCompletion',
  emits: ['go-settings', 'go-requests'],
};
</script>

<style scoped>
.completion-wrapper {
  text-align: center;
  max-width: 600px;
  margin: 0 auto;
}

.success-icon {
  color: var(--color-success);
  font-size: 4rem;
  margin-bottom: 1rem;
}

.success-icon i {
  animation: checkmark 0.5s ease-in-out;
}

@keyframes checkmark {
  0% { transform: scale(0) rotate(-45deg); }
  50% { transform: scale(1.2) rotate(-45deg); }
  100% { transform: scale(1) rotate(0deg); }
}

.completion-wrapper h1 {
  color: var(--color-text-primary);
  font-size: 2.5rem;
  margin-bottom: 1rem;
  font-weight: bold;
}

.completion-subtitle {
  color: var(--color-text-muted);
  font-size: 1.2rem;
  margin-bottom: 2rem;
  line-height: 1.6;
}

.next-steps {
  text-align: left;
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--border-radius-sm);
  padding: 1.5rem;
  margin-bottom: 2rem;
}

.next-steps h3 {
  color: var(--color-text-primary);
  margin-bottom: 1rem;
  font-size: 1.2rem;
}

.next-steps ul {
  color: #e5e7eb;
  margin: 0;
  padding-left: 1.5rem;
  line-height: 1.6;
}

.next-steps li {
  margin-bottom: 0.5rem;
}

.completion-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.action-btn {
  padding: 1rem 2rem;
  border-radius: var(--border-radius-sm);
  font-weight: bold;
  cursor: pointer;
  transition: var(--transition-base);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  min-width: 150px;
  justify-content: center;
}

.action-btn.primary {
  background: linear-gradient(135deg, var(--color-success), #059669);
  color: white;
}

.action-btn.primary:hover {
  background: linear-gradient(135deg, #059669, #047857);
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(16, 185, 129, 0.3);
}

.action-btn.secondary {
  background: var(--color-bg-interactive);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

.action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.5);
  transform: translateY(-2px);
}

@media (max-width: 768px) {
  .completion-wrapper {
    padding: 1.5rem;
    margin: 0 1rem;
  }

  .completion-wrapper h1 {
    font-size: 2rem;
  }

  .completion-subtitle {
    font-size: 1rem;
  }

  .completion-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .action-btn {
    min-width: auto;
  }
}
</style>