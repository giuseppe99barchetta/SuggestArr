<template>
  <div class="form-group-modern" v-click-outside="closeDropdown">
    <label v-if="label" :for="id" class="modern-label">
      <span class="label-content">
        <span class="label-text">{{ label }}</span>
        <span v-if="required" class="required-dot"></span>
      </span>
    </label>
    
    <div 
      class="custom-dropdown" 
      :class="{ 
        'is-open': isOpen, 
        'is-disabled': disabled, 
        'has-error': error 
      }"
      @click="toggleDropdown"
    >
      <!-- Selected value display -->
      <div class="dropdown-trigger">
        <div class="select-background"></div>
        <div class="select-glow"></div>
        
        <div class="selected-value">
          <span v-if="selectedLabel" class="value-text">{{ selectedLabel }}</span>
          <span v-else class="placeholder-text">{{ placeholder || 'Select an option' }}</span>
        </div>
        
        <div class="dropdown-icon-wrapper">
          <div class="icon-background"></div>
          <i class="fas fa-chevron-down dropdown-icon"></i>
        </div>
      </div>
      
      <!-- Custom dropdown menu -->
      <transition name="dropdown-slide">
        <div v-if="isOpen" class="dropdown-menu">
          <div class="dropdown-menu-inner">
            <div class="dropdown-scroll">
              <div
                v-for="(option, index) in options"
                :key="getOptionKey(option)"
                class="dropdown-item"
                :class="{ 
                  'is-selected': isSelected(option),
                  'is-disabled': option.disabled,
                  'is-highlighted': highlightedIndex === index
                }"
                @click.stop="selectOption(option)"
                @mouseenter="highlightedIndex = index"
              >
                <div class="item-content">
                  <span class="item-label">{{ getOptionLabel(option) }}</span>
                  <i v-if="isSelected(option)" class="fas fa-check item-check"></i>
                </div>
                <div class="item-ripple"></div>
              </div>
              
              <div v-if="options.length === 0" class="dropdown-empty">
                <i class="fas fa-inbox"></i>
                <span>No options available</span>
              </div>
            </div>
          </div>
        </div>
      </transition>
    </div>
    
    <transition name="fade-slide-up">
      <div v-if="helpText && !error" class="modern-help">
        <i class="fas fa-lightbulb"></i>
        <span>{{ helpText }}</span>
      </div>
    </transition>
    
    <transition name="shake">
      <div v-if="error" class="modern-error">
        <i class="fas fa-exclamation-triangle"></i>
        <span>{{ error }}</span>
      </div>
    </transition>
  </div>
</template>

<script>
export default {
  name: 'BaseDropdown',
  props: {
    modelValue: {
      type: [String, Number, Boolean],
      default: ''
    },
    options: {
      type: Array,
      required: true,
      default: () => []
    },
    label: {
      type: String,
      default: ''
    },
    placeholder: {
      type: String,
      default: ''
    },
    helpText: {
      type: String,
      default: ''
    },
    error: {
      type: String,
      default: ''
    },
    required: {
      type: Boolean,
      default: false
    },
    disabled: {
      type: Boolean,
      default: false
    },
    id: {
      type: String,
      default: () => `dropdown-${Math.random().toString(36).substr(2, 9)}`
    },
    optionKey: {
      type: String,
      default: 'value'
    },
    optionLabel: {
      type: String,
      default: 'label'
    },
    optionValue: {
      type: String,
      default: 'value'
    }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return {
      isOpen: false,
      highlightedIndex: -1
    };
  },
  computed: {
    selectedLabel() {
      const selected = this.options.find(opt => 
        this.getOptionValue(opt) === this.modelValue
      );
      return selected ? this.getOptionLabel(selected) : '';
    }
  },
  methods: {
    toggleDropdown() {
      if (this.disabled) return;
      this.isOpen = !this.isOpen;
      if (this.isOpen) {
        this.$nextTick(() => {
          this.scrollToSelected();
        });
      }
    },
    closeDropdown() {
      this.isOpen = false;
      this.highlightedIndex = -1;
    },
    selectOption(option) {
      if (option.disabled) return;
      
      const value = this.getOptionValue(option);
      this.$emit('update:modelValue', value);
      this.$emit('change', value);
      this.closeDropdown();
    },
    isSelected(option) {
      return this.getOptionValue(option) === this.modelValue;
    },
    scrollToSelected() {
      const selectedIndex = this.options.findIndex(opt => 
        this.getOptionValue(opt) === this.modelValue
      );
      if (selectedIndex !== -1) {
        this.highlightedIndex = selectedIndex;
      }
    },
    getOptionKey(option) {
      if (typeof option === 'object' && option !== null) {
        return option[this.optionKey] || option[this.optionValue] || option[this.optionLabel];
      }
      return option;
    },
    getOptionLabel(option) {
      if (typeof option === 'object' && option !== null) {
        return option[this.optionLabel] || option[this.optionValue] || option[this.optionKey];
      }
      return option;
    },
    getOptionValue(option) {
      if (typeof option === 'object' && option !== null) {
        return option[this.optionValue] || option[this.optionKey] || option[this.optionLabel];
      }
      return option;
    }
  },
  directives: {
    'click-outside': {
      mounted(el, binding) {
        el.clickOutsideEvent = (event) => {
          if (!(el === event.target || el.contains(event.target))) {
            binding.value();
          }
        };
        document.addEventListener('click', el.clickOutsideEvent);
      },
      unmounted(el) {
        document.removeEventListener('click', el.clickOutsideEvent);
      }
    }
  }
};
</script>

<style scoped>
/* Form Group */
.form-group-modern {
  margin-bottom: 1.5rem;
  position: relative;
}

/* Label */
.modern-label {
  display: inline-flex;
  align-items: center;
  margin-bottom: 0.625rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-text-primary);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.label-content {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.label-text {
  background: linear-gradient(135deg, #e5e7eb 0%, #9ca3af 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.required-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.2); opacity: 0.8; }
}

/* Custom Dropdown */
.custom-dropdown {
  position: relative;
  cursor: pointer;
  user-select: none;
}

.custom-dropdown.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}

/* Dropdown Trigger */
.dropdown-trigger {
  position: relative;
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.select-background {
  position: absolute;
  inset: 0;
  backdrop-filter: blur(12px) saturate(120%);
  border: 1px solid rgba(229, 231, 235, 0.1);
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
}

.select-glow {
  position: absolute;
  inset: -2px;
  border-radius: 12px;
  opacity: 0;
  transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  filter: blur(8px);
  z-index: 0;
}

.custom-dropdown.is-open .select-glow,
.custom-dropdown:hover .select-glow {
  opacity: 1;
}

.custom-dropdown.is-open .select-background,
.dropdown-trigger:hover .select-background {
  border-color: rgba(229, 231, 235, 0.25);
  box-shadow: 
    0 0 0 3px rgba(229, 231, 235, 0.05),
    0 8px 24px -4px rgba(0, 0, 0, 0.4);
}

.custom-dropdown.has-error .select-background {
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(31, 41, 55, 0.7) 100%);
  border-color: rgba(239, 68, 68, 0.4);
}

/* Selected Value */
.selected-value {
  position: relative;
  padding: 0.875rem 3rem 0.875rem 1.125rem;
  z-index: 2;
}

.value-text {
  color: #f3f4f6;
  font-size: 0.9375rem;
  font-weight: 500;
}

.placeholder-text {
  color: #9ca3af;
  font-size: 0.9375rem;
  font-weight: 400;
}

/* Icon */
.dropdown-icon-wrapper {
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  z-index: 3;
}

.icon-background {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(229, 231, 235, 0.05) 0%, rgba(156, 163, 175, 0.05) 100%);
  border-radius: 8px;
  opacity: 0;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.custom-dropdown:hover .icon-background {
  opacity: 1;
}

.dropdown-icon {
  font-size: 0.75rem;
  color: #9ca3af;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;
}

.custom-dropdown:hover .dropdown-icon {
  color: #e5e7eb;
}

.custom-dropdown.is-open .dropdown-icon {
  transform: rotate(180deg);
  color: #f3f4f6;
  filter: drop-shadow(0 0 8px rgba(229, 231, 235, 0.3));
}

/* Dropdown Menu */
.dropdown-menu {
  position: absolute;
  top: calc(100% + 0.5rem);
  left: 0;
  right: 0;
  z-index: 1000;
}

.dropdown-menu-inner {
  background: linear-gradient(
    135deg,
    rgba(28, 28, 29, 0.98) 0%,
    rgba(30, 30, 31, 0.99) 100%
  );
  backdrop-filter: blur(24px) saturate(120%);
  border: 1px solid rgba(148, 163, 184, 0.2); 
  border-radius: 12px;
  box-shadow: 
    0 0 0 1px rgba(148, 163, 184, 0.1),
    0 20px 40px -12px rgba(0, 0, 0, 0.7),
    0 0 60px -20px rgba(148, 163, 184, 0.15);
  overflow: hidden;
}


.dropdown-scroll {
  max-height: 320px;
  overflow-y: auto;
  padding: 0.5rem;
}

/* Custom Scrollbar - Grigio */
.dropdown-scroll::-webkit-scrollbar {
  width: 6px;
}

.dropdown-scroll::-webkit-scrollbar-track {
  background: rgba(55, 65, 81, 0.3);
  border-radius: 10px;
  margin: 0.5rem 0;
}

.dropdown-scroll::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, rgba(156, 163, 175, 0.6) 0%, rgba(107, 114, 128, 0.6) 100%);
  border-radius: 10px;
  transition: all 0.3s ease;
}

.dropdown-scroll::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, rgba(156, 163, 175, 0.8) 0%, rgba(107, 114, 128, 0.8) 100%);
}

/* Dropdown Item */
.dropdown-item {
  position: relative;
  padding: 0.875rem 1rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  background: transparent;
}

.dropdown-item:not(:last-child) {
  margin-bottom: 0.25rem;
}

.item-content {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  z-index: 2;
}

.item-label {
  color: #e5e7eb;
  font-size: 0.9375rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.item-check {
  font-size: 0.875rem;
  color: #f3f4f6;
  animation: check-bounce 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes check-bounce {
  0% { transform: scale(0); }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

/* Item States - Grigio */
.dropdown-item.is-highlighted {
  background: linear-gradient(
    135deg,
    rgba(75, 85, 99, 0.25) 0%,
    rgba(55, 65, 81, 0.2) 100%
  );
}

.dropdown-item.is-selected {
  background: linear-gradient(
    135deg,
    rgba(107, 114, 128, 0.35) 0%,
    rgba(75, 85, 99, 0.25) 100%
  );
  border: 1px solid rgba(229, 231, 235, 0.1);
}

.dropdown-item.is-selected .item-label {
  color: #ffffff;
  font-weight: 600;
}

.dropdown-item.is-disabled {
  opacity: 0.4;
  cursor: not-allowed;
  pointer-events: none;
}

.dropdown-item:not(.is-disabled):hover {
  background: linear-gradient(
    135deg,
    rgba(107, 114, 128, 0.4) 0%,
    rgba(75, 85, 99, 0.3) 100%
  );
  transform: translateX(4px);
}

.dropdown-item:not(.is-disabled):active {
  transform: scale(0.98) translateX(4px);
}

/* Ripple effect - Grigio */
.item-ripple {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle, rgba(229, 231, 235, 0.3) 0%, transparent 70%);
  opacity: 0;
  transform: scale(0);
  pointer-events: none;
}

.dropdown-item:active .item-ripple {
  animation: ripple 0.6s ease-out;
}

@keyframes ripple {
  0% {
    opacity: 1;
    transform: scale(0);
  }
  100% {
    opacity: 0;
    transform: scale(2);
  }
}

/* Empty State */
.dropdown-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem 1rem;
  color: #9ca3af;
  text-align: center;
}

.dropdown-empty i {
  font-size: 2rem;
  opacity: 0.5;
}

/* Dropdown Animation */
.dropdown-slide-enter-active {
  animation: dropdown-appear 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.dropdown-slide-leave-active {
  animation: dropdown-disappear 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes dropdown-appear {
  0% {
    opacity: 0;
    transform: translateY(-12px) scale(0.95);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes dropdown-disappear {
  0% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
  100% {
    opacity: 0;
    transform: translateY(-8px) scale(0.98);
  }
}

/* Help/Error - Grigio */
.modern-help {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.625rem 1rem;
  background: linear-gradient(135deg, rgba(75, 85, 99, 0.2) 0%, rgba(55, 65, 81, 0.15) 100%);
  border-left: 3px solid #9ca3af;
  border-radius: 8px;
  font-size: 0.8125rem;
  color: #d1d5db;
}

.modern-help i {
  color: #e5e7eb;
}

.modern-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.625rem 1rem;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%);
  border-left: 3px solid var(--color-danger);
  border-radius: 8px;
  font-size: 0.8125rem;
  color: var(--color-danger);
  font-weight: 500;
}

/* Transitions */
.fade-slide-up-enter-active,
.fade-slide-up-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.fade-slide-up-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}

.fade-slide-up-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.shake-enter-active {
  animation: shake 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-4px); }
  20%, 40%, 60%, 80% { transform: translateX(4px); }
}

/* Responsive */
@media (max-width: 768px) {
  .dropdown-scroll {
    max-height: 240px;
  }

  .dropdown-item {
    padding: 0.75rem 0.875rem;
  }

  .item-label {
    font-size: 0.875rem;
  }
}
</style>
