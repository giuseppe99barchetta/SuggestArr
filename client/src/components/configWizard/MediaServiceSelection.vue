<template>
    <div>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div v-for="service in services" 
                 :key="service.name"
                 role="button"
                 :aria-label="`Select ${service.name} ${service.comingSoon ? '(Coming Soon)' : ''}`"
                 :aria-pressed="config.SELECTED_SERVICE === service.value"
                 :tabindex="service.comingSoon ? -1 : 0"
                 @keypress.enter="selectService(service)"
                 @keypress.space.prevent="selectService(service)"
                 class="relative flex h-[100px] cursor-pointer flex-col items-center justify-center gap-1.5 overflow-hidden rounded-xl border-2 pb-2 transition duration-300 sm:h-[120px]"
                 :class="[
                     config.SELECTED_SERVICE === service.value && !service.comingSoon
                         ? 'border-brand bg-brand/6 shadow-[0_0_0_3px] shadow-brand/25'
                         : 'border-white/10 bg-[rgba(15,20,30,0.82)]',
                     service.comingSoon ? 'pointer-events-none opacity-60' : 'hover:-translate-y-2 hover:border-brand-ink hover:shadow-[0_12px_24px_rgba(0,0,0,0.3)]'
                 ]"
                 @click="selectService(service)">

                <!-- Logo image -->
                <img :src="service.logo" :alt="service.name" class="pointer-events-none h-[55%] w-[55%] object-contain" />

                <!-- Service Name -->
                <div class="text-center text-[0.8rem] font-medium tracking-wide text-white/85 sm:text-[0.85rem]">{{ service.name }}</div>

                <!-- Coming Soon Overlay -->
                <div v-if="service.comingSoon" class="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-xl bg-black/85 text-xl font-bold text-gray-400 backdrop-blur-xs">
                    <i aria-hidden="true" class="fas fa-lock mb-2"></i>
                    <p>Coming Soon</p>
                </div>

                <!-- New Badge -->
                <div v-if="service.isNew && !service.comingSoon" class="absolute top-3 right-3 z-[15] animate-pulse rounded-full bg-gradient-to-br from-brand to-indigo-500 px-3 py-1.5 text-xs font-bold text-white shadow-[0_2px_8px] shadow-brand/40">
                    ✨ NEW
                </div>

                <!-- Selected Checkmark -->
                <div v-if="config.SELECTED_SERVICE === service.value && !service.comingSoon"
                     class="absolute top-3 left-3 z-[15] flex h-8 w-8 items-center justify-center rounded-full bg-good text-base text-white shadow-[0_2px_8px] shadow-good/40">
                    <i aria-hidden="true" class="fas fa-check-circle"></i>
                </div>

            </div>
        </div>
    </div>
</template>

<script>
import jellyfinLogo from "@/assets/logos/jellyfin-logo.svg";
import plexLogo from "@/assets/logos/plex-logo.svg";
import embyLogo from "@/assets/logos/emby-logo.svg";

export default {
    props: {
        config: { type: Object, required: true },
    },
    emits: ['update-config'],
    data() {
        return {
            services: [
                { name: 'Jellyfin', value: 'jellyfin', logo: jellyfinLogo, comingSoon: false, isNew: false },
                { name: 'Plex', value: 'plex', logo: plexLogo, comingSoon: false, isNew: false },
                { name: 'Emby', value: 'emby', logo: embyLogo, comingSoon: false, isNew: false },
            ]
        };
    },
    methods: {
        selectService(service) {
            if (!service.comingSoon) {
                this.$emit('update-config', 'SELECTED_SERVICE', service.value);
            }
        }
    }
};
</script>
