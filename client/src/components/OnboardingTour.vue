<template>
  <teleport to="body">
    <template v-if="active && currentStep">
      <!-- Dark backdrop — click to skip -->
      <div class="fixed inset-0 z-[9000] cursor-pointer" @click="skip"></div>

      <!-- Spotlight "hole" via box-shadow -->
      <div class="pointer-events-none fixed z-[9001] rounded-[10px] shadow-[0_0_0_9999px_rgba(0,0,0,0.72)] transition-[top,left,width,height] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]" :style="spotlightStyle"></div>

      <!-- Tooltip card -->
      <transition
        mode="out-in"
        enter-active-class="transition duration-200"
        leave-active-class="transition duration-150"
        enter-from-class="opacity-0 scale-[0.94] translate-y-1.5"
        leave-to-class="opacity-0 scale-[0.94] -translate-y-1"
      >
        <div :key="currentIndex" class="theme-dark fixed z-[9002] rounded-card border border-white/12 bg-[rgba(18,24,38,0.97)] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.05)] backdrop-blur-xl" :style="tooltipStyle" @click.stop>
          <!-- Arrow indicator -->
          <div class="absolute h-0 w-0 border-8 border-transparent" :class="arrowClass"></div>

          <!-- Header: pips + step count -->
          <div class="mb-3 flex items-center justify-between">
            <div class="flex gap-[5px]">
              <span
                v-for="(_, i) in steps"
                :key="i"
                class="h-1.5 w-1.5 rounded-full transition"
                :class="i === currentIndex ? 'scale-[1.3] bg-brand' : i < currentIndex ? 'bg-good/70' : 'bg-white/20'"
              ></span>
            </div>
            <span class="text-[0.72rem] text-white/35 tabular-nums">{{ currentIndex + 1 }} / {{ steps.length }}</span>
          </div>

          <h3 class="m-0 mb-1.5 text-base font-bold text-white">{{ currentStep.title }}</h3>
          <p class="m-0 mb-4 text-[0.85rem] leading-relaxed text-white/65">{{ currentStep.description }}</p>

          <div class="flex items-center justify-between gap-2">
            <button class="cursor-pointer border-0 bg-transparent p-0 text-[0.78rem] text-white/35 transition-colors hover:text-white/65" @click="skip">Skip tour</button>
            <div class="flex gap-2">
              <button v-if="currentIndex > 0" class="cursor-pointer rounded-lg border border-white/18 bg-transparent px-3.5 py-1.5 text-[0.82rem] font-medium text-white/70 transition hover:border-white/30 hover:bg-white/6" @click="prev">
                ← Back
              </button>
              <button class="cursor-pointer rounded-lg border-0 bg-brand px-4 py-1.5 text-[0.82rem] font-semibold text-white transition hover:-translate-y-px hover:brightness-110" @click="next">
                {{ isLast ? 'Finish ✓' : 'Next →' }}
              </button>
            </div>
          </div>
        </div>
      </transition>
    </template>
  </teleport>
</template>

<script>
const TOUR_STORAGE_KEY = 'suggestarr_tour_done';
const TOOLTIP_WIDTH = 300;
const TOOLTIP_EST_HEIGHT = 190;
const SPOTLIGHT_PAD = 8;

export default {
  name: 'OnboardingTour',

  props: {
    steps: {
      type: Array,
      required: true,
      // Step shape: { targetId: string, title: string, description: string, position?: 'bottom'|'top'|'left'|'right' }
    },
    active: {
      type: Boolean,
      default: false,
    },
  },

  emits: ['done', 'step-changed'],

  data() {
    return {
      currentIndex: 0,
      targetRect: null,
      resizeHandler: null,
      scrollHandler: null,
    };
  },

  computed: {
    currentStep() {
      return this.steps[this.currentIndex] || null;
    },
    isLast() {
      return this.currentIndex === this.steps.length - 1;
    },

    spotlightStyle() {
      if (!this.targetRect) return { display: 'none' };
      return {
        top:    `${this.targetRect.top    - SPOTLIGHT_PAD}px`,
        left:   `${this.targetRect.left   - SPOTLIGHT_PAD}px`,
        width:  `${this.targetRect.width  + SPOTLIGHT_PAD * 2}px`,
        height: `${this.targetRect.height + SPOTLIGHT_PAD * 2}px`,
      };
    },

    // Returns which side the tooltip sits on (used for the arrow)
    arrowSide() {
      if (!this.targetRect) return 'top';
      const preferred = this.currentStep?.position || 'bottom';
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const { top, bottom } = this.targetRect;
      if (preferred === 'bottom' && bottom + TOOLTIP_EST_HEIGHT + 24 < vh) return 'top';   // arrow points up, tooltip below
      if (preferred === 'top'    && top  - TOOLTIP_EST_HEIGHT - 24 > 0)  return 'bottom'; // arrow points down, tooltip above
      if (preferred === 'left'   && this.targetRect.left - TOOLTIP_WIDTH - 24 > 0)  return 'right';
      if (preferred === 'right'  && this.targetRect.right + TOOLTIP_WIDTH + 24 < vw) return 'left';
      // fallback
      return bottom + TOOLTIP_EST_HEIGHT + 24 < vh ? 'top' : 'bottom';
    },

    // Border-triangle arrow pointing at the target; the light edge matches the card border.
    arrowClass() {
      return {
        top: '-top-2 left-1/2 -translate-x-1/2 border-t-0 border-b-white/12',
        bottom: '-bottom-2 left-1/2 -translate-x-1/2 border-b-0 border-t-white/12',
        left: '-left-2 top-1/2 -translate-y-1/2 border-l-0 border-r-white/12',
        right: '-right-2 top-1/2 -translate-y-1/2 border-r-0 border-l-white/12',
      }[this.arrowSide];
    },

    tooltipStyle() {
      if (!this.targetRect) {
        return { top: '50%', left: '50%', transform: 'translate(-50%, -50%)', width: `${TOOLTIP_WIDTH}px` };
      }

      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const side = this.arrowSide;
      const margin = 16; // gap between spotlight edge and tooltip
      const edgePad = 12; // min distance from viewport edge

      let top, left;

      // Center horizontally on target
      let hCenter = this.targetRect.left + this.targetRect.width / 2 - TOOLTIP_WIDTH / 2;
      hCenter = Math.max(edgePad, Math.min(hCenter, vw - TOOLTIP_WIDTH - edgePad));

      // Center vertically on target
      let vCenter = this.targetRect.top + this.targetRect.height / 2 - TOOLTIP_EST_HEIGHT / 2;
      vCenter = Math.max(edgePad, Math.min(vCenter, vh - TOOLTIP_EST_HEIGHT - edgePad));

      if (side === 'top') {
        // Tooltip below target
        top  = this.targetRect.bottom + SPOTLIGHT_PAD + margin;
        left = hCenter;
      } else if (side === 'bottom') {
        // Tooltip above target
        top  = this.targetRect.top - SPOTLIGHT_PAD - margin - TOOLTIP_EST_HEIGHT;
        left = hCenter;
      } else if (side === 'right') {
        // Tooltip left of target
        top  = vCenter;
        left = this.targetRect.left - SPOTLIGHT_PAD - margin - TOOLTIP_WIDTH;
      } else {
        // Tooltip right of target
        top  = vCenter;
        left = this.targetRect.right + SPOTLIGHT_PAD + margin;
      }

      // Final clamp
      top  = Math.max(edgePad, Math.min(top,  vh - TOOLTIP_EST_HEIGHT - edgePad));
      left = Math.max(edgePad, Math.min(left, vw - TOOLTIP_WIDTH - edgePad));

      return { top: `${top}px`, left: `${left}px`, width: `${TOOLTIP_WIDTH}px` };
    },
  },

  watch: {
    active(val) {
      if (val) {
        this.currentIndex = 0;
        this.$emit('step-changed', 0);
        this.$nextTick(() => this.scrollAndUpdate());
      }
    },
    currentIndex() {
      this.$nextTick(() => this.scrollAndUpdate());
    },
  },

  methods: {
    scrollAndUpdate() {
      if (!this.currentStep) return;
      const el = document.querySelector(`[data-tour-id="${this.currentStep.targetId}"]`);
      if (!el) {
        this.targetRect = null;
        return;
      }
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      setTimeout(() => {
        this.targetRect = el.getBoundingClientRect();
      }, 320);
    },

    next() {
      if (this.isLast) {
        this.finish();
      } else {
        this.currentIndex++;
        this.$emit('step-changed', this.currentIndex);
      }
    },

    prev() {
      if (this.currentIndex > 0) {
        this.currentIndex--;
        this.$emit('step-changed', this.currentIndex);
      }
    },

    skip() {
      localStorage.setItem(TOUR_STORAGE_KEY, '1');
      this.$emit('done');
    },

    finish() {
      localStorage.setItem(TOUR_STORAGE_KEY, '1');
      this.$emit('done');
    },
  },

  mounted() {
    if (this.active) {
      this.$nextTick(() => this.scrollAndUpdate());
    }
    this.resizeHandler = () => { if (this.active) this.scrollAndUpdate(); };
    window.addEventListener('resize', this.resizeHandler);

    // Re-read the target rect on any scroll (capture phase catches inner scrollable containers)
    // so the spotlight stays locked to the element even when the user scrolls inside a modal.
    this.scrollHandler = () => {
      if (!this.active || !this.currentStep) return;
      const el = document.querySelector(`[data-tour-id="${this.currentStep.targetId}"]`);
      if (el) this.targetRect = el.getBoundingClientRect();
    };
    window.addEventListener('scroll', this.scrollHandler, { capture: true, passive: true });
  },

  beforeUnmount() {
    window.removeEventListener('resize', this.resizeHandler);
    window.removeEventListener('scroll', this.scrollHandler, { capture: true });
  },
};
</script>
