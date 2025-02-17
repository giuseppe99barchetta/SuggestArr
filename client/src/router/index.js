import { createRouter, createWebHistory } from 'vue-router';
import RequestsPage from '@/components/RequestsPage.vue';
import ConfigWizard from '@/components/ConfigWizard.vue';
import axios from 'axios';
import { createApp } from 'vue';
import App from '../App.vue';
import 'vue-toast-notification/dist/theme-bootstrap.css';
import ToastPlugin from 'vue-toast-notification';

async function loadConfig() {
    if (process.env.NODE_ENV === 'development') {
        axios.defaults.baseURL = 'http://localhost:5000';
    }
    
    try {
        const response = await axios.get('/api/config/fetch');
        return response.data.SUBPATH || '';
    } catch (error) {
        throw new Error('Unable to load the configuration file');
    }
}

async function createAppRouter() {
    const subpath = await loadConfig();

    const routes = [
        { path: `/requests`, name: 'RequestsPage', component: RequestsPage },
        { path: `/`, name: 'Home', component: ConfigWizard },
    ];

    return createRouter({
        history: createWebHistory(subpath || '/'),
        routes
    });
}

createAppRouter().then(router => {
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
}).catch(error => {
    console.error('Error loading the router:', error);
});
