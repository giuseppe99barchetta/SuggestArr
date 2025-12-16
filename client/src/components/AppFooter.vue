<template>
    <footer class="footer">

        <!-- Button to show logs -->
        <div class="logs-button-container">
            <button @click="toggleLogs" class="logs-button">
                <font-awesome-icon :icon="['fas', 'file-alt']" class="logs-icon" />
                <span class="logs-text">View Logs</span>
            </button>
        </div>

        <div class="footer-content">
            <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" aria-label="GitHub">
                <font-awesome-icon :icon="['fab', 'github']" class="footer-icon" />
            </a>
            <a href="https://hub.docker.com/repository/docker/ciuse99/suggestarr/" target="_blank" aria-label="Docker">
                <font-awesome-icon :icon="['fab', 'docker']" class="footer-icon" />
            </a>
            <a href="https://www.reddit.com/r/selfhosted/comments/1g3dn1t/automate_media_recommendations_and_downloads_with/" target="_blank" aria-label="Reddit">
                <font-awesome-icon :icon="['fab', 'reddit']" class="footer-icon" />
            </a>
            <a href="https://discord.gg/JXwFd3PnXY" target="_blank" aria-label="Discord">
                <font-awesome-icon :icon="['fab', 'discord']" class="footer-icon" />
            </a>
        </div>

        <!-- Modal for logs -->
        <div v-if="showLogs" class="modal-overlay" @click.self="toggleLogs">
            <div class="modal">
                <div class="modal-header">
                    <h2 class="modal-title">System Logs</h2>
                    <button class="close-button" @click="toggleLogs">&times;</button>
                </div>
                <div class="modal-body">
                    <LogsComponent />
                </div>
            </div>
        </div>
    </footer>
</template>

<script>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faGithub, faDocker, faReadme, faReddit, faDiscord } from '@fortawesome/free-brands-svg-icons';
import { faFileAlt } from '@fortawesome/free-solid-svg-icons';
import { library } from '@fortawesome/fontawesome-svg-core';
import LogsComponent from './LogsComponent.vue'; // Import your LogsComponent

// Add the icons to the library
library.add(faGithub, faDocker, faReadme, faReddit, faFileAlt, faDiscord);

export default {
    components: {
        FontAwesomeIcon,
        LogsComponent
    },
    data() {
        return {
            showLogs: false // To control the modal visibility
        };
    },
    methods: {
        toggleLogs() {
            this.showLogs = !this.showLogs; // Toggles the modal visibility
        }
    }
};
</script>

<style scoped>
.logs-button-container {
    margin-bottom: 20px; /* Separa il pulsante dalle icone */
    display: flex;
    justify-content: center; /* Centra il pulsante */
}
.logs-button {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: transparent;
    color: var(--color-text-primary);
    padding: 10px 20px;
    font-size: 1.1rem;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}

.logs-button:hover {
    background-color: #4f46e5;
    color: var(--color-text-primary);
    border-color: #4f46e5;
}

/* Stili per l'icona e il testo del pulsante */
.logs-icon {
    margin-right: 10px;
    font-size: 1.5rem;
}

.logs-text {
    font-size: 1.1rem;
}

/* Footer styles */
.footer {
    padding: 20px;
    text-align: center;
    margin-top: 40px;
}

.footer-content {
    display: flex;
    justify-content: center;
    gap: 20px;
}

.footer-icon {
    font-size: 1.5rem;
    color: var(--color-text-primary);
    transition: color 0.3s ease;
}

.footer-icon:hover {
    color: #4f46e5;
}

/* Modal styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.9); /* Semi-transparent background */
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: 10px;
    z-index: 999;
}

.modal {
    background: rgba(0, 0, 0, 0.8);
    padding: 20px;
    border-radius: 10px;
    max-width: 90%;
    max-height: 90%;
    width: 70%;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.modal-body {
    flex-grow: 1;
    margin-top: 20px;
    overflow-y: auto;
    max-height: 70vh;
}

.modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #4b5563;
    padding-bottom: 10px;
}

.modal-title {
    color: var(--color-text-primary);
    font-size: 1.5rem;
}

.close-button {
    background: none;
    border: none;
    color: var(--color-text-primary);
    font-size: 1.5rem;
    cursor: pointer;
}

.close-button:hover {
    color: #f87171;
}

</style>
