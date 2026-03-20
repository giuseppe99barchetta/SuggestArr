<template>
  <label
    class="base-checkbox"
    :class="{ 'base-checkbox--disabled': disabled }"
  >
    <!-- Track: contains hidden native input + custom visual box -->
    <span class="base-checkbox__track">
      <!--
        The native input is visually hidden but remains fully accessible
        to keyboards and screen readers. It handles all native events
        (change, focus, blur) which bubble up to the root label when needed.
      -->
      <input
        class="base-checkbox__input"
        type="checkbox"
        :checked="modelValue"
        :disabled="disabled"
        @change="$emit('update:modelValue', $event.target.checked)"
      />
      <!-- Custom visual box — aria-hidden since the real input is the a11y target -->
      <span class="base-checkbox__box" aria-hidden="true">
        <svg
          class="base-checkbox__icon"
          viewBox="0 0 10 8"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <polyline
            points="1,4 3.5,6.5 9,1"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
    </span>

    <!-- Label content: uses slot for rich content, prop fallback for simple text -->
    <span class="base-checkbox__content">
      <slot>{{ label }}</slot>
      <span v-if="description" class="base-checkbox__description">
        {{ description }}
      </span>
    </span>
  </label>
</template>

<script>
export default {
  name: 'BaseCheckbox',

  props: {
    /**
     * The bound boolean value (v-model).
     */
    modelValue: {
      type: Boolean,
      default: false,
    },

    /**
     * Simple text label rendered next to the checkbox.
     * Use the default slot for rich/HTML content.
     */
    label: {
      type: String,
      default: '',
    },

    /**
     * Secondary descriptive text rendered below the label.
     * Only shown when using the `label` prop (not the slot).
     */
    description: {
      type: String,
      default: '',
    },

    /**
     * Disables interaction and applies reduced-opacity styling.
     */
    disabled: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['update:modelValue'],
};
</script>

<style scoped>
/* ================================================================
   BaseCheckbox — Custom Checkbox Component
   All values use SuggestArr design tokens from variables.css.

   States handled:
   - unchecked   (default)
   - checked     (input:checked)
   - hover       (.base-checkbox:hover)
   - focus-visible (input:focus-visible ~ .base-checkbox__box)
   - disabled    (.base-checkbox--disabled)
================================================================ */

/* ── Root label ───────────────────────────────────────────── */

.base-checkbox {
  display: inline-flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  cursor: pointer;
  user-select: none;
  line-height: var(--line-height-normal);
}

.base-checkbox--disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

/* ── Track: size container for input + box ────────────────── */

.base-checkbox__track {
  /* Explicitly block-like so width/height apply even when the parent
     label is forced to display:block by an ancestor scoped rule. */
  display: inline-flex;
  position: relative;
  flex-shrink: 0;
  width: 1.125rem;  /* 18px */
  height: 1.125rem; /* 18px */
  margin-top: 0.125rem; /* optical alignment with text cap-height */
}

/* ── Hidden native input ──────────────────────────────────── */
/*
   Positioned over the entire track so it captures click/keyboard
   events correctly. Opacity 0 so the browser native checkbox
   is invisible, but it remains in the a11y tree.
*/

.base-checkbox__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  margin: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
  z-index: 1;
}

.base-checkbox--disabled .base-checkbox__input {
  cursor: not-allowed;
}

/* ── Custom visual box ────────────────────────────────────── */

.base-checkbox__box {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  background: var(--surface-interactive);
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
  pointer-events: none;
}

/* Hover state */
.base-checkbox:not(.base-checkbox--disabled):hover .base-checkbox__box {
  border-color: var(--color-border-heavy);
  background: var(--surface-hover);
}

/* Focus-visible state (keyboard navigation — WCAG 2.1 AA) */
.base-checkbox__input:focus-visible ~ .base-checkbox__box {
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
  outline: none;
}

/* Checked state */
.base-checkbox__input:checked ~ .base-checkbox__box {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

/* ── Checkmark SVG icon ───────────────────────────────────── */

.base-checkbox__icon {
  width: 0.625rem;  /* 10px */
  height: 0.5rem;   /* 8px */
  color: white;
  opacity: 0;
  transform: scale(0.5);
  transition:
    opacity var(--transition-fast),
    transform var(--transition-fast);
  pointer-events: none;
}

.base-checkbox__input:checked ~ .base-checkbox__box .base-checkbox__icon {
  opacity: 1;
  transform: scale(1);
}

/* ── Label text ───────────────────────────────────────────── */

.base-checkbox__content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2xs);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  line-height: var(--line-height-normal);
}

/* Secondary / description text below the label */
.base-checkbox__description {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-normal);
  color: var(--color-text-muted);
  line-height: var(--line-height-normal);
}
</style>
