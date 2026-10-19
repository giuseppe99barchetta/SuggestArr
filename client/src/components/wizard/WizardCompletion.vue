<template>
  <div class="mx-auto my-8 box-border max-w-[600px] rounded-2xl border border-white/8 bg-[rgba(15,20,30,0.82)] p-8 text-center backdrop-blur-md">
    <div class="mb-6 text-[5rem] text-good">
      <i aria-hidden="true" class="fas fa-check-circle inline-block animate-pop"></i>
    </div>

    <h1 class="mb-2 text-[2rem] font-extrabold text-ink md:text-[2.5rem]">Setup Complete!</h1>
    <p class="mb-10 text-[1.1rem] leading-relaxed text-ink-4">
      SuggestArr is now configured and ready to suggest content from your media server.
    </p>

    <div class="mb-10 rounded-ctl border border-edge bg-white/3 p-6 text-left">
      <h3 class="mb-4 text-[1.1rem] font-semibold text-ink">What's Next?</h3>
      <ul class="m-0 list-none pl-5 text-ink-3 [&>li]:relative [&>li]:mb-3 [&>li]:before:absolute [&>li]:before:-left-5 [&>li]:before:text-good [&>li]:before:content-['→']">
        <li>View and manage your suggestions in the <strong>Requests</strong> page</li>
        <li>Fine-tune your preferences in <strong>Settings</strong></li>
        <li>Run your first content suggestion manually</li>
      </ul>
    </div>

    <div class="flex flex-col-reverse items-center justify-center gap-3 md:flex-row md:gap-4">
      <button @click="$emit('go-settings')" class="inline-flex flex-1 cursor-pointer items-center justify-center gap-2.5 rounded-lg px-7 py-3.5 text-[0.95rem] font-semibold transition max-md:w-full md:max-w-[220px] border border-edge-strong bg-transparent text-ink hover:border-ink-4 hover:bg-panel-2">
        <i aria-hidden="true" class="fas fa-cog"></i>
        Go to Settings
      </button>
      <button @click="$emit('go-requests')" class="inline-flex flex-1 cursor-pointer items-center justify-center gap-2.5 rounded-lg px-7 py-3.5 text-[0.95rem] font-semibold transition max-md:w-full md:max-w-[220px] border-0 bg-good text-white hover:-translate-y-0.5 hover:shadow-[0_4px_12px_rgba(16,185,129,0.2)] hover:brightness-110">
        <i aria-hidden="true" class="fas fa-list-alt"></i>
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
