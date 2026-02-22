import { createRouter, createWebHistory } from 'vue-router';
import axios from 'axios';
import { createApp } from 'vue';
import App from '../App.vue';
import 'vue-toast-notification/dist/theme-bootstrap.css';
import ToastPlugin from 'vue-toast-notification';

// Lazy load components for code splitting
const RequestsPage = () => import('@/components/RequestsPage.vue');
const ConfigWizard = () => import('@/components/ConfigWizard.vue');
const DashboardPage = () => import('@/components/DashboardPage.vue');

function configureAxiosSubpath() {
    const metaTag = document.querySelector('meta[name="suggestarr-subpath"]');
    const subpath = metaTag ? (metaTag.getAttribute('content') || '') : '';

    if (process.env.NODE_ENV === 'development') {
        axios.defaults.baseURL = 'http://localhost:5000' + subpath;
    } else {
        axios.defaults.baseURL = subpath || '/';
    }
    return subpath;
}

async function loadConfig() {
    try {
        const response = await axios.get('/api/config/fetch');
        localStorage.setItem('suggestarr_config', JSON.stringify(response.data));
        return response.data.SUBPATH || '';
    } catch (error) {
        throw new Error('Unable to load the configuration file');
    }
}

async function checkSetupStatus() {
    try {
        const response = await axios.get('/api/config/status');
        return response.data;
    } catch (error) {
        console.error('Error checking setup status:', error);
        return { setup_completed: false, is_complete: false };
    }
}

async function createAppRouter() {
    const subpath = configureAxiosSubpath();
    await loadConfig();
    const setupStatus = await checkSetupStatus();

    const routes = [
        {
            path: `/requests`,
            name: 'RequestsPage',
            component: RequestsPage,
            meta: { requiresSetup: true }
        },
        {
            path: `/`,
            name: 'Home',
            component: DashboardPage,
            meta: { requiresSetup: true }
        },
        {
            path: `/setup`,
            name: 'Setup',
            component: ConfigWizard,
            meta: { setupOnly: true }
        },
        {
            path: `/dashboard`,
            name: 'Dashboard',
            component: DashboardPage,
            meta: { requiresSetup: true }
        },
        {
            path: `/dashboard/:tab?`,
            name: 'DashboardTab',
            component: DashboardPage,
            meta: { requiresSetup: true }
        },
        // Redirect legacy routes
        {
            path: `/wizard`,
            redirect: '/setup'
        }
    ];

    const router = createRouter({
        history: createWebHistory(subpath || '/'),
        routes
    });

    // Add navigation guards
    router.beforeEach(async (to, from, next) => {
        // For development, we might want to skip setup checks
        if (process.env.NODE_ENV === 'development' && to.query.skipSetup) {
            return next();
        }

        const currentStatus = await checkSetupStatus();

        // If setup is not completed and route requires setup, redirect to setup
        if (to.meta.requiresSetup && !currentStatus.setup_completed) {
            return next('/setup');
        }

        // If setup is completed and route is setup-only, redirect to settings
        if (to.meta.setupOnly && currentStatus.setup_completed) {
            return next('/dashboard');
        }

        next();
    });

    return router;
}

export default createAppRouter().then(router => {
    const app = createApp(App);
    app.use(router);
    app.mount('#app');
    const options = {
        position: 'top-right',
        timeout: 5000,
        closeOnClick: false,
        pauseOnHover: true,
        draggable: false,
        showCloseButtonOnHover: true,
        closeButton: 'button',
        icon: true,
        rtl: false,
    };

    app.use(ToastPlugin, options);
    return router;
}).catch(error => {
    console.error('Error loading router:', error);
});
