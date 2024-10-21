<template>
    <footer class="footer">
        <div class="footer-content">
            <a href="https://github.com/giuseppe99barchetta/SuggestArr" target="_blank" aria-label="GitHub">
                <font-awesome-icon :icon="['fab', 'github']" class="footer-icon" />
            </a>
            <a href="https://hub.docker.com/repository/docker/ciuse99/suggestarr/" target="_blank" aria-label="Docker">
                <font-awesome-icon :icon="['fab', 'docker']" class="footer-icon" />
            </a>
            <a href="https://github.com/giuseppe99barchetta/SuggestArr/wiki" target="_blank" aria-label="Wiki">
                <font-awesome-icon :icon="['fab', 'readme']" class="footer-icon" />
            </a>
            <a href="https://www.reddit.com/r/selfhosted/comments/1g3dn1t/automate_media_recommendations_and_downloads_with/" target="_blank" aria-label="Reddit">
                <font-awesome-icon :icon="['fab', 'reddit']" class="footer-icon" />
            </a>
        </div>
    </footer>
</template>

<script>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faGithub, faDocker, faReadme, faReddit } from '@fortawesome/free-brands-svg-icons';
import { library } from '@fortawesome/fontawesome-svg-core';

library.add(faGithub, faDocker, faReadme, faReddit);

export default {
    components: {
        FontAwesomeIcon
    }
};
</script>

<style scoped>
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
    color: #ffffff;
    transition: color 0.3s ease;
}

.footer-icon:hover {
    color: #4f46e5;
    /* Colore al passaggio del mouse */
}
</style>