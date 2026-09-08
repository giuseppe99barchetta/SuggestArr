<template>
  <section class="settings-group settings-panel" :class="`settings-panel--${tone}`">
    <button
      class="settings-panel__toggle"
      type="button"
      :aria-expanded="expanded.toString()"
      :aria-controls="contentId"
      @click="expanded = !expanded"
    >
      <span class="settings-panel__heading">
        <span class="settings-panel__icon"><i :class="icon"></i></span>
        <span>
          <span class="settings-panel__title">{{ title }}</span>
          <span class="settings-panel__description">{{ description }}</span>
        </span>
      </span>
      <i class="fas fa-chevron-right settings-panel__chevron" :class="{ expanded }"></i>
    </button>

    <Transition name="settings-panel-collapse">
      <div v-show="expanded" :id="contentId" class="settings-panel__collapse">
        <div class="settings-panel__collapse-inner">
          <div class="settings-panel__content"><slot /></div>
        </div>
      </div>
    </Transition>
  </section>
</template>

<script>
export default {
  name: 'SettingsPanel',
  props: {
    title: { type: String, required: true },
    description: { type: String, required: true },
    icon: { type: String, required: true },
    panelId: { type: String, required: true },
    tone: { type: String, default: 'default' },
  },
  data() {
    return { expanded: false };
  },
  computed: {
    contentId() {
      return `${this.panelId}-content`;
    },
  },
};
</script>

<style scoped>
.settings-group.settings-panel {
  grid-column: 1 / -1;
  overflow: hidden;
  padding: var(--spacing-lg);
  background: var(--surface-glass-subtle);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.settings-panel__toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--spacing-sm);
  color: var(--color-text-primary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.settings-panel__toggle:hover,
.settings-panel__toggle:focus-visible {
  background: var(--surface-glass-subtle);
}

.settings-panel__toggle:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

.settings-panel__heading {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: var(--spacing-md);
}

.settings-panel__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: var(--input-height-md);
  height: var(--input-height-md);
  color: var(--color-primary-light);
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
}

.settings-panel--warning .settings-panel__icon {
  color: var(--color-warning-light);
  background: var(--color-warning-alpha-10);
  border-color: var(--color-warning);
}

.settings-panel__title,
.settings-panel__description {
  display: block;
}

.settings-panel__title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
}

.settings-panel__description {
  margin-top: var(--spacing-xs);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.settings-panel__chevron {
  flex: 0 0 auto;
  margin-left: var(--spacing-md);
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.settings-panel__chevron.expanded {
  transform: rotate(90deg);
}

.settings-panel__collapse {
  display: grid;
  grid-template-rows: 1fr;
  opacity: 1;
}

.settings-panel__collapse-inner {
  min-height: 0;
  overflow: hidden;
}

.settings-panel__content {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--color-border-light);
}

.settings-panel-collapse-enter-active,
.settings-panel-collapse-leave-active {
  transition:
    grid-template-rows var(--transition-slow),
    opacity var(--transition-base);
}

.settings-panel-collapse-enter-from,
.settings-panel-collapse-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
}

@media (max-width: 700px) {
  .settings-group.settings-panel {
    padding: var(--spacing-md);
  }
}
</style>
