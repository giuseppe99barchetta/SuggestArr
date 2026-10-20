<template>
  <div class="min-w-0">
    <button
      type="button"
      class="flex min-h-10 w-fit cursor-pointer items-center gap-2 rounded-ctl border-0 bg-transparent p-0 text-xs font-medium text-ink-3 transition-colors hover:text-ink"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="open = !open"
    >
      <i aria-hidden="true" class="fas fa-sliders-h text-ink-4"></i>
      Reminder options
      <i aria-hidden="true" class="fas fa-chevron-down text-[10px] transition-transform motion-reduce:transition-none" :class="open ? 'rotate-180' : ''"></i>
    </button>
    <!-- 0fr -> 1fr animates height without measuring; visibility keeps the closed panel out of tab order and the a11y tree. -->
    <div
      :id="panelId"
      class="grid transition-[grid-template-rows,opacity,visibility] duration-250 ease-out motion-reduce:transition-none"
      :class="open ? 'visible grid-rows-[1fr] opacity-100' : 'invisible grid-rows-[0fr] opacity-0'"
    >
      <div class="min-h-0 overflow-hidden">
        <div class="mt-1 rounded-ctl border border-edge bg-canvas/40 p-1">
          <button
            v-for="action in actions"
            :key="action.id"
            type="button"
            class="flex min-h-11 w-full cursor-pointer items-center gap-3 rounded-ctl border-0 bg-transparent px-3 py-2.5 text-left text-[13px] text-ink-2 transition-colors hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="saving"
            @click="$emit('select', action.id)"
          >
            <i aria-hidden="true" class="w-4 shrink-0 text-center text-ink-4" :class="action.icon"></i>
            {{ action.label }}
          </button>
        </div>
        <p class="m-0 mt-2 text-xs leading-relaxed text-ink-4">You can change this later in My profile.</p>
      </div>
    </div>
  </div>
</template>

<script>
let nextId = 0;

export default {
  name: 'SupportReminderOptions',
  props: {
    saving: { type: Boolean, default: false },
    allowSnooze: { type: Boolean, default: false },
  },
  emits: ['select'],
  data: () => ({ open: false, panelId: `reminder-options-${++nextId}` }),
  computed: {
    actions() {
      return [
        ...(this.allowSnooze ? [{ id: 'remind_later', label: 'Remind me in 30 days', icon: 'far fa-clock' }] : []),
        { id: 'supported', label: 'I already supported', icon: 'fas fa-check' },
        { id: 'disable', label: "Don't show these reminders", icon: 'far fa-bell-slash' },
      ];
    },
  },
};
</script>

