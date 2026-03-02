<template>
    <div>
        <div class="media-services grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div v-for="service in services" 
                 :key="service.name"
                 role="button"
                 :aria-label="`Select ${service.name} ${service.comingSoon ? '(Coming Soon)' : ''}`"
                 :aria-pressed="config.SELECTED_SERVICE === service.value"
                 :tabindex="service.comingSoon ? -1 : 0"
                 @keypress.enter="selectService(service)"
                 @keypress.space.prevent="selectService(service)"
                 :class="[
                     'service-box',
                     {
                         'selected': config.SELECTED_SERVICE === service.value && !service.comingSoon,
                         'coming-soon': service.comingSoon
                     }
                 ]"
                 @click="selectService(service)">

                <!-- Logo image -->
                <img :src="service.logo" :alt="service.name" class="service-logo" />

                <!-- Service Name -->
                <div class="service-name">{{ service.name }}</div>

                <!-- Coming Soon Overlay -->
                <div v-if="service.comingSoon" class="coming-soon-overlay">
                    <i class="fas fa-lock mb-2"></i>
                    <p>Coming Soon</p>
                </div>

                <!-- New Badge -->
                <div v-if="service.isNew && !service.comingSoon" class="new-badge">
                    ✨ NEW
                </div>

                <!-- Selected Checkmark -->
                <div v-if="config.SELECTED_SERVICE === service.value && !service.comingSoon"
                     class="selected-checkmark">
                    <i class="fas fa-check-circle"></i>
                </div>

            </div>
        </div>

        <!-- Navigation Buttons (hidden in wizard mode — wizard shell provides navigation) -->
        <div v-if="!wizardMode" class="flex justify-between mt-8 gap-4">
          <button
            @click="$emit('previous-step')"
            class="btn-secondary w-full flex items-center justify-center gap-2 py-4 px-8"
          >
            <i class="fas fa-arrow-left"></i>
            Back
          </button>

          <button
            @click="$emit('next-step')"
            :disabled="!config.SELECTED_SERVICE"
            class="btn-primary w-full flex items-center justify-center gap-2 py-4 px-8"
            :class="{ 'opacity-50 cursor-not-allowed': !config.SELECTED_SERVICE }"
          >
            Next Step
            <i class="fas fa-arrow-right"></i>
          </button>
        </div>
    </div>
</template>

<script>
export default {
    props: {
        config: { type: Object, required: true },
        // When true, the component's own nav buttons are hidden.
        // The wizard shell provides Back / Continue navigation instead.
        wizardMode: { type: Boolean, default: false },
    },
    emits: ['update-config', 'next-step', 'previous-step'],
    data() {
        return {
            services: [
                { name: 'Jellyfin', value: 'jellyfin', logo: require('@/assets/logos/jellyfin-logo.svg'), comingSoon: false, isNew: false },
                { name: 'Plex', value: 'plex', logo: require('@/assets/logos/plex-logo.svg'), comingSoon: false, isNew: false },
                { name: 'Emby', value: 'emby', logo: require('@/assets/logos/emby-logo.svg'), comingSoon: false, isNew: false },
            ]
        };
    },
    methods: {
        selectService(service) {
            if (!service.comingSoon) {
                this.$emit('update-config', 'SELECTED_SERVICE', service.value);
            }
        },
        getServiceName(value) {
            const service = this.services.find(s => s.value === value);
            return service ? service.name : '';
        }
    }
};
</script>

<style scoped>
.media-services {
    display: grid;
    gap: 1rem;
}

.service-box {
    position: relative;
    height: 120px;
    background-color: rgba(15, 20, 30, 0.82);
    border: 2px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s ease;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding-bottom: 8px;
}

.service-logo {
    width: 55%;
    height: 55%;
    object-fit: contain;
    pointer-events: none;
}

.service-box:hover:not(.coming-soon) {
    transform: translateY(-8px);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
    border-color: var(--color-primary-hover)
}

.service-box:focus {
    outline: 1px solid rgb(79, 70, 229);
}

.selected {
    border-color: rgb(79, 70, 229);
    box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.25);
    background-color: rgba(79, 70, 229, 0.06);
}

.coming-soon-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(4px);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    border-radius: 12px;
    color: #9ca3af;
    font-size: 1.25rem;
    font-weight: bold;
    z-index: 10;
}

.coming-soon {
    pointer-events: none;
    opacity: 0.6;
}

.new-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    background: linear-gradient(135deg, rgb(79, 70, 229), rgb(99, 102, 241));
    color: white;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: bold;
    z-index: 15;
    box-shadow: 0 2px 8px rgba(79, 70, 229, 0.4);
    animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}

.selected-checkmark {
    position: absolute;
    top: 12px;
    left: 12px;
    background-color: rgb(34, 197, 94);
    color: white;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    z-index: 15;
    box-shadow: 0 2px 8px rgba(34, 197, 94, 0.4);
}

.service-name {
    color: rgba(255, 255, 255, 0.85);
    text-align: center;
    font-size: 0.85rem;
    font-weight: 500;
    letter-spacing: 0.03em;
}

@media (max-width: 640px) {
    .service-box {
        height: 100px;
    }

    .service-name {
        font-size: 0.8rem;
    }
}
</style>
