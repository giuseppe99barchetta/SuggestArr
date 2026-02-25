<template>
  <teleport to="body">
    <template v-if="active && currentStep">
      <!-- Dark backdrop — click to skip -->
      <div class="tour-backdrop" @click="skip"></div>

      <!-- Spotlight "hole" via box-shadow -->
      <div class="tour-spotlight" :style="spotlightStyle"></div>

      <!-- Tooltip card -->
      <transition name="tour-tooltip-pop" mode="out-in">
        <div :key="currentIndex" class="tour-tooltip" :style="tooltipStyle" @click.stop>
          <!-- Arrow indicator -->
          <div class="tour-arrow" :class="`arrow-${arrowSide}`"></div>

          <!-- Header: pips + step count -->
          <div class="tour-header">
            <div class="tour-pips">
              <span
                v-for="(_, i) in steps"
                :key="i"
                class="tour-pip"
                :class="{ 'is-active': i === currentIndex, 'is-done': i < currentIndex }"
              ></span>
            </div>
            <span class="tour-count">{{ currentIndex + 1 }} / {{ steps.length }}</span>
          </div>

          <h3 class="tour-title">{{ currentStep.title }}</h3>
          <p class="tour-desc">{{ currentStep.description }}</p>

          <div class="tour-footer">
            <button class="tour-skip" @click="skip">Skip tour</button>
            <div class="tour-nav">
              <button v-if="currentIndex > 0" class="tour-btn-outline" @click="prev">
                ← Back
              </button>
              <button class="tour-btn-primary" @click="next">
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

<style scoped>
/* ── Backdrop ─────────────────────────────────────────────────────────────── */
.tour-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9000;
  cursor: pointer;
}

/* ── Spotlight ────────────────────────────────────────────────────────────── */
.tour-spotlight {
  position: fixed;
  z-index: 9001;
  border-radius: 10px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.72);
  pointer-events: none;
  transition: top 0.32s cubic-bezier(0.4, 0, 0.2, 1),
              left 0.32s cubic-bezier(0.4, 0, 0.2, 1),
              width 0.32s cubic-bezier(0.4, 0, 0.2, 1),
              height 0.32s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Tooltip card ─────────────────────────────────────────────────────────── */
.tour-tooltip {
  position: fixed;
  z-index: 9002;
  background: rgba(18, 24, 38, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;
  padding: 1.25rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

/* Arrow */
.tour-arrow {
  position: absolute;
  width: 0;
  height: 0;
}

.arrow-top {
  /* Tooltip is below target, arrow points up */
  top: -8px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-bottom: 8px solid rgba(255, 255, 255, 0.12);
}

.arrow-top::after {
  content: '';
  position: absolute;
  top: 1px;
  left: -7px;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-bottom: 7px solid rgb(18, 24, 38);
}

.arrow-bottom {
  /* Tooltip is above target, arrow points down */
  bottom: -8px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-top: 8px solid rgba(255, 255, 255, 0.12);
}

.arrow-bottom::after {
  content: '';
  position: absolute;
  bottom: 1px;
  left: -7px;
  border-left: 7px solid transparent;
  border-right: 7px solid transparent;
  border-top: 7px solid rgb(18, 24, 38);
}

.arrow-left {
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-right: 8px solid rgba(255, 255, 255, 0.12);
}

.arrow-right {
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 8px solid rgba(255, 255, 255, 0.12);
}

/* Header row */
.tour-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.tour-pips {
  display: flex;
  gap: 5px;
}

.tour-pip {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  transition: background 0.2s, transform 0.2s;
}

.tour-pip.is-active {
  background: var(--color-primary, #3b82f6);
  transform: scale(1.3);
}

.tour-pip.is-done {
  background: rgba(16, 185, 129, 0.7);
}

.tour-count {
  font-size: 0.72rem;
  color: rgba(255, 255, 255, 0.35);
  font-variant-numeric: tabular-nums;
}

/* Content */
.tour-title {
  color: #fff;
  font-size: 1rem;
  font-weight: 700;
  margin: 0 0 0.4rem;
}

.tour-desc {
  color: rgba(255, 255, 255, 0.65);
  font-size: 0.85rem;
  line-height: 1.55;
  margin: 0 0 1rem;
}

/* Footer */
.tour-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.tour-skip {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.35);
  font-size: 0.78rem;
  cursor: pointer;
  padding: 0;
  transition: color 0.18s;
}

.tour-skip:hover {
  color: rgba(255, 255, 255, 0.65);
}

.tour-nav {
  display: flex;
  gap: 0.5rem;
}

.tour-btn-outline {
  padding: 0.4rem 0.875rem;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.18s, border-color 0.18s;
}

.tour-btn-outline:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.3);
}

.tour-btn-primary {
  padding: 0.4rem 1rem;
  border: none;
  border-radius: 8px;
  background: var(--color-primary, #3b82f6);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.18s, transform 0.18s;
}

.tour-btn-primary:hover {
  filter: brightness(1.12);
  transform: translateY(-1px);
}

/* ── Tooltip enter/leave transition ──────────────────────────────────────── */
.tour-tooltip-pop-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.tour-tooltip-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.tour-tooltip-pop-enter-from {
  opacity: 0;
  transform: scale(0.94) translateY(6px);
}

.tour-tooltip-pop-leave-to {
  opacity: 0;
  transform: scale(0.94) translateY(-4px);
}
</style>
