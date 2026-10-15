<template>
  <div class="relative" ref="dropdownWrapper" v-bind="$attrs">
    <label v-if="label" :for="id" class="mb-2 inline-flex items-center text-sm font-medium text-ink-2">
      {{ label }}
    </label>

    <div
      ref="dropdownTrigger"
      class="group relative cursor-pointer select-none"
      :class="{ 'pointer-events-none cursor-not-allowed opacity-50': disabled }"
      :tabindex="disabled ? -1 : 0"
      :aria-expanded="isOpen.toString()"
      :aria-haspopup="'menu'"
      :aria-controls="dropdownMenuId"
      role="button"
      @click="toggleDropdown"
      @keydown.enter.prevent="handleTriggerKeyDown"
      @keydown.space.prevent="handleTriggerKeyDown"
      @keydown.escape="handleEscapeKey"
      @keydown.down.prevent="handleArrowDown"
      @keydown.up.prevent="handleArrowUp"
    >
      <div
        class="relative min-w-0 rounded-ctl border bg-canvas py-[0.6875rem] pr-11 pl-3 text-sm transition-colors group-hover:border-brand-ink"
        :class="isOpen ? 'border-brand-ink' : 'border-edge-strong'"
      >
        <span v-if="selectedLabel" class="block truncate text-ink">{{ selectedLabel }}</span>
        <span v-else class="block truncate text-ink-4">{{ placeholder || 'Select an option' }}</span>
        <i
          class="fas fa-chevron-down absolute top-1/2 right-4 -translate-y-1/2 text-xs transition-transform duration-300"
          :class="isOpen ? 'rotate-180 text-ink' : 'text-ink-3 group-hover:text-ink-2'"
        ></i>
      </div>
    </div>

    <div v-if="helpText" class="mt-2 flex items-center gap-2 rounded-lg border-l-[3px] border-ink-3 bg-white/5 px-4 py-2.5 text-[0.8125rem] text-ink-2">
      <i class="fas fa-info-circle"></i>
      <span>{{ helpText }}</span>
    </div>
  </div>

  <Teleport :to="menuTarget">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      leave-active-class="transition duration-150 ease-in"
      enter-from-class="-translate-y-2 scale-95 opacity-0"
      leave-to-class="-translate-y-1 scale-[0.98] opacity-0"
    >
      <div
        v-if="isOpen"
        :id="dropdownMenuId"
        ref="dropdownMenu"
        class="fixed z-[9999] overflow-hidden rounded-ctl border border-edge-strong bg-panel-2 shadow-[0_16px_40px_-12px_rgba(0,0,0,0.7)]"
        :style="menuStyle"
        role="menu"
        :aria-labelledby="id"
      >
        <div class="flex max-h-60 flex-col gap-0.5 overflow-y-auto p-1 md:max-h-80">
          <div
            v-for="(option, index) in options"
            :key="getOptionKey(option)"
            :ref="el => { if (el) menuItemRefs[index] = el }"
            class="flex cursor-pointer items-center justify-between rounded-[7px] px-3.5 py-3 text-sm transition-colors active:scale-[0.98] md:px-3 md:py-2"
            :class="[
              isSelected(option) ? 'bg-brand-soft font-semibold text-ink' : highlightedIndex === index ? 'bg-raised text-ink-2' : 'text-ink-2 hover:bg-raised',
              { 'pointer-events-none cursor-not-allowed opacity-40': option.disabled }
            ]"
            role="menuitem"
            :tabindex="highlightedIndex === index ? 0 : -1"
            :aria-selected="isSelected(option).toString()"
            :aria-disabled="option.disabled ? 'true' : undefined"
            @click.stop="selectOption(option)"
            @keydown.enter.prevent="selectOption(option)"
            @keydown.space.prevent="selectOption(option)"
            @mouseenter="highlightedIndex = index"
          >
            <span>{{ getOptionLabel(option) }}</span>
            <i v-if="isSelected(option)" class="fas fa-check text-brand-ink"></i>
          </div>

          <div v-if="options.length === 0" class="flex flex-col items-center gap-2 px-4 py-8 text-center text-ink-3">
            <i class="fas fa-inbox text-[2rem] opacity-50"></i>
            <span>No options available</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
export default {
  name: 'BaseDropdown',
  inheritAttrs: false,
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
      highlightedIndex: -1,
      menuItemRefs: [],
      menuStyle: null,
      // A modal <dialog> makes the rest of the page inert, so menus opened inside one must render in it.
      menuTarget: 'body'
    };
  },
  computed: {
    dropdownMenuId() {
      return `${this.id}-menu`;
    },
    selectedLabel() {
      const selected = this.options.find(opt => 
        this.getOptionValue(opt) === this.modelValue
      );
      return selected ? this.getOptionLabel(selected) : '';
    }
  },
  mounted() {
    this.menuTarget = this.$refs.dropdownWrapper.closest('dialog') || 'body';
    this._onDocumentClick = (event) => {
      const wrapper = this.$refs.dropdownWrapper;
      const menu = this.$refs.dropdownMenu;
      if (
        (wrapper && wrapper.contains(event.target)) ||
        (menu && menu.contains(event.target))
      ) {
        return;
      }
      this.closeDropdown();
    };
    document.addEventListener('click', this._onDocumentClick);
  },
  beforeUnmount() {
    document.removeEventListener('click', this._onDocumentClick);
    this._removePositionListeners();
  },
  methods: {
    getFirstDefinedProp(option, propNames) {
      for (const prop of propNames) {
        if (Object.prototype.hasOwnProperty.call(option, prop)) {
          return option[prop];
        }
      }
      return undefined;
    },
    handleTriggerKeyDown() {
      if (this.disabled) return;
      if (!this.isOpen) {
        this.openDropdown();
      } else {
        this.closeDropdown();
      }
    },
    handleEscapeKey() {
      if (this.isOpen) {
        this.closeDropdown();
      }
    },
    handleArrowDown() {
      if (!this.isOpen) {
        this.openDropdown();
      } else {
        this.navigateNext();
      }
    },
    handleArrowUp() {
      if (!this.isOpen) {
        this.openDropdown();
      } else {
        this.navigatePrevious();
      }
    },
    navigateNext() {
      const enabledOptions = this.options.filter(opt => !opt.disabled);
      if (enabledOptions.length === 0) return;
      
      let nextIndex = this.highlightedIndex + 1;
      while (nextIndex < this.options.length && this.options[nextIndex].disabled) {
        nextIndex++;
      }
      
      if (nextIndex >= this.options.length) {
        nextIndex = this.options.findIndex(opt => !opt.disabled);
      }
      
      this.highlightedIndex = nextIndex;
      this.focusMenuItem(nextIndex);
    },
    navigatePrevious() {
      const enabledOptions = this.options.filter(opt => !opt.disabled);
      if (enabledOptions.length === 0) return;
      
      let prevIndex = this.highlightedIndex - 1;
      while (prevIndex >= 0 && this.options[prevIndex].disabled) {
        prevIndex--;
      }
      
      if (prevIndex < 0) {
        for (let i = this.options.length - 1; i >= 0; i--) {
          if (!this.options[i].disabled) {
            prevIndex = i;
            break;
          }
        }
      }
      
      this.highlightedIndex = prevIndex;
      this.focusMenuItem(prevIndex);
    },
    focusMenuItem(index) {
      this.$nextTick(() => {
        const menuItem = this.menuItemRefs[index];
        if (menuItem && typeof menuItem.focus === 'function') {
          menuItem.focus();
        }
      });
    },
    openDropdown() {
      if (this.disabled) return;
      this.isOpen = true;
      this._addPositionListeners();
      this.$nextTick(() => {
        this._updateMenuPosition();
        this.scrollToSelected();
        // Focus the first enabled item or the selected item
        const selectedIndex = this.options.findIndex(opt => this.isSelected(opt) && !opt.disabled);
        if (selectedIndex !== -1) {
          this.highlightedIndex = selectedIndex;
          this.focusMenuItem(selectedIndex);
        } else {
          const firstEnabledIndex = this.options.findIndex(opt => !opt.disabled);
          if (firstEnabledIndex !== -1) {
            this.highlightedIndex = firstEnabledIndex;
            this.focusMenuItem(firstEnabledIndex);
          }
        }
      });
    },
    toggleDropdown() {
      if (this.disabled) return;
      if (this.isOpen) {
        this.closeDropdown();
      } else {
        this.openDropdown();
      }
    },
    closeDropdown() {
      const wasOpen = this.isOpen;
      this.isOpen = false;
      this.highlightedIndex = -1;
      this._removePositionListeners();
      // Return focus to trigger only if the dropdown was actually open,
      // to avoid stealing focus from other elements (e.g. text inputs).
      if (wasOpen) {
        this.$nextTick(() => {
          if (this.$refs.dropdownTrigger) {
            this.$refs.dropdownTrigger.focus();
          }
        });
      }
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
      if (selectedIndex !== -1 && !this.options[selectedIndex].disabled) {
        this.highlightedIndex = selectedIndex;
      }
    },
    getOptionKey(option) {
      if (typeof option === 'object' && option !== null) {
        return this.getFirstDefinedProp(option, [this.optionKey, this.optionValue, this.optionLabel]);
      }
      return option;
    },
    getOptionLabel(option) {
      if (typeof option === 'object' && option !== null) {
        return this.getFirstDefinedProp(option, [this.optionLabel, this.optionValue, this.optionKey]);
      }
      return option;
    },
    getOptionValue(option) {
      if (typeof option === 'object' && option !== null) {
        return this.getFirstDefinedProp(option, [this.optionValue, this.optionKey, this.optionLabel]);
      }
      return option;
    },
    _updateMenuPosition() {
      const trigger = this.$refs.dropdownTrigger;
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      const menuHeight = this.$refs.dropdownMenu?.offsetHeight || 0;
      const spaceBelow = window.innerHeight - rect.bottom;
      const openAbove = menuHeight > spaceBelow && rect.top > spaceBelow;
      this.menuStyle = {
        position: 'fixed',
        top: `${openAbove ? Math.max(4, rect.top - menuHeight - 4) : rect.bottom + 4}px`,
        left: `${rect.left}px`,
        width: `${rect.width}px`,
        zIndex: '9999',
      };
    },
    _addPositionListeners() {
      this._updateMenuPosition();
      window.addEventListener('scroll', this._updateMenuPosition, { capture: true, passive: true });
      window.addEventListener('resize', this._updateMenuPosition, { passive: true });
    },
    _removePositionListeners() {
      window.removeEventListener('scroll', this._updateMenuPosition, { capture: true });
      window.removeEventListener('resize', this._updateMenuPosition);
    },
  }
};
</script>
