<template>
  <label
    class="base-checkbox group inline-flex cursor-pointer select-none items-start gap-2 leading-normal"
    :class="{ 'pointer-events-none cursor-not-allowed opacity-50': disabled }"
  >
    <!-- Track: contains hidden native input + custom visual box -->
    <span class="relative mt-0.5 inline-flex h-[1.125rem] w-[1.125rem] shrink-0">
      <!--
        The native input is visually hidden but remains fully accessible
        to keyboards and screen readers. It handles all native events
        (change, focus, blur) which bubble up to the root label when needed.
      -->
      <input
        class="peer absolute inset-0 z-[1] m-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
        type="checkbox"
        :checked="modelValue"
        :disabled="disabled"
        @change="$emit('update:modelValue', $event.target.checked)"
      />
      <!-- Custom visual box — aria-hidden since the real input is the a11y target -->
      <span class="pointer-events-none absolute inset-0 flex items-center justify-center rounded-[6px] border-[1.5px] border-edge-strong bg-panel-2 transition group-hover:border-ink-4 group-hover:bg-raised peer-checked:border-brand peer-checked:bg-brand peer-focus-visible:border-brand peer-focus-visible:ring-3 peer-focus-visible:ring-brand/40 peer-checked:[&>svg]:scale-100 peer-checked:[&>svg]:opacity-100" aria-hidden="true">
        <svg
          class="pointer-events-none h-2 w-2.5 scale-50 text-white opacity-0 transition"
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
    <span class="flex flex-col gap-0.5 text-sm font-medium leading-normal text-ink">
      <slot>{{ label }}</slot>
      <span v-if="description" class="text-xs font-normal leading-normal text-ink-4">
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
