<template>
    <div>
        <h3 class="text-xl font-bold text-gray-200 mb-4">Select the media service you want to use:</h3>
        <div class="media-services grid grid-cols-2 gap-4">
            <div v-for="service in services" :key="service.name"
                :class="['service-box', { 'selected': config.SELECTED_SERVICE === service.value && !service.comingSoon, 'coming-soon': service.comingSoon }]"
                :style="{ backgroundImage: `url(${service.logo})` }" 
                @click="selectService(service)">
                <div v-if="service.comingSoon" class="coming-soon-overlay">
                    <p>Coming Soon</p>
                </div>
                <!-- Plex Beta Badge -->
                <div v-if="service.value === 'plex'" class="beta-badge">
                    ✨ Beta
                </div>

            </div>
        </div>

        <div class="flex justify-between mt-8 space-x-4">
            <button @click="$emit('next-step')"
                class="bg-indigo-600 hover:bg-indigo-500 text-white font-bold py-4 px-8 rounded-lg w-full">
                Next Step
            </button>
        </div>
    </div>
</template>

<script>
export default {
    props: ['config'],
    data() {
        return {
            services: [
                { name: 'Jellyfin', value: 'jellyfin', logo: require('@/assets/logos/jellyfin-logo.png'), comingSoon: false },
                { name: 'Plex', value: 'plex', logo: require('@/assets/logos/plex-logo.png'), comingSoon: false },
                { name: 'Emby', value: 'emby', logo: require('@/assets/logos/emby-logo.png'), comingSoon: true },
            ],
            showTooltip: false
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

<style scoped>
.media-services {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
}

.service-box {
    position: relative;
    height: 150px;
    background-size: cover;
    background-position: center;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.3s ease;
}

.service-box:hover {
    transform: scale(1.05);
}

.selected {
    outline: 2px solid rgb(79 70 229);
}

.coming-soon-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: 8px;
    color: white;
    font-size: 1.25rem;
    font-weight: bold;
    z-index: 10;
}

.coming-soon {
    pointer-events: none; /* Disable interactions */
}

.overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: rgba(0, 0, 0, 0.5);
    text-align: center;
    color: white;
    padding: 10px;
    font-size: 1.25rem;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}

.beta-badge {
    position: absolute;
    top: 10px;
    right: 10px;
    background-color: rgb(79 70 229);
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: bold;
    z-index: 10;
    cursor: default;
}

</style>
