<template>
  <div class="completion-wrapper"> <div class="success-icon">
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
  margin: 2rem auto; /* Aggiunto margine verticale */
  padding: 0 1rem;
  box-sizing: border-box;
}

.success-icon {
  color: var(--color-success);
  font-size: 5rem; /* Leggermente più grande */
  margin-bottom: 1.5rem;
}

/* Animazione checkmark migliorata */
.success-icon i {
  display: inline-block;
  animation: checkmark 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes checkmark {
  0% { transform: scale(0); opacity: 0; }
  100% { transform: scale(1); opacity: 1; }
}

h1 {
  color: var(--color-text-primary);
  font-size: 2.5rem;
  margin-bottom: 0.5rem;
  font-weight: 800;
}

.completion-subtitle {
  color: var(--color-text-muted);
  font-size: 1.1rem;
  margin-bottom: 2.5rem;
  line-height: 1.6;
}

.next-steps {
  text-align: left;
  background: rgba(255, 255, 255, 0.03); /* Più sottile */
  border: 1px solid var(--color-border-light);
  border-radius: var(--border-radius-sm);
  padding: 1.5rem;
  margin-bottom: 2.5rem;
}

.next-steps h3 {
  color: var(--color-text-primary);
  margin-bottom: 1rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.next-steps ul {
  color: var(--color-text-secondary);
  margin: 0;
  padding-left: 1.2rem;
  list-style-type: none; /* Pulizia icone custom */
}

.next-steps li {
  margin-bottom: 0.75rem;
  position: relative;
}

/* Bullet points custom più eleganti */
.next-steps li::before {
  content: '→';
  position: absolute;
  left: -1.2rem;
  color: var(--color-success);
}

.completion-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  align-items: center;
}

.action-btn {
  padding: 0.875rem 1.75rem;
  border-radius: 8px; /* Un po' più morbido */
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.95rem;
  flex: 1; /* I bottoni prendono lo stesso spazio */
  justify-content: center;
  max-width: 220px;
}

.action-btn.primary {
  background: var(--color-success);
  color: white;
}

.action-btn.primary:hover {
  filter: brightness(1.1);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.2);
}

.action-btn.secondary {
  background: transparent;
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-medium);
}

.action-btn.secondary:hover {
  background: var(--color-bg-interactive);
  border-color: var(--color-text-muted);
}

/* Responsive */
@media (max-width: 768px) {
  .completion-actions {
    flex-direction: column-reverse; /* Inverte per avere l'azione principale in alto */
    gap: 0.75rem;
  }

  .action-btn {
    max-width: 100%;
    width: 100%;
  }

  h1 {
    font-size: 2rem;
  }
}
</style>