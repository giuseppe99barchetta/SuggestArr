import { createRouter, createWebHistory } from 'vue-router';
import RequestsPage from '@/components/RequestsPage.vue';
import ConfigWizard from '@/components/ConfigWizard.vue';

const routes = [
    { path: '/requests', name: 'RequestsPage', component: RequestsPage },
    { path: '/', name: 'Home', component: ConfigWizard },
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

export default router;
