import { createApp } from 'vue';
import App from './App.vue';
import ToastPlugin from 'vue-toast-notification';
import 'vue-toast-notification/dist/theme-bootstrap.css';
import axios from 'axios';

const app = createApp(App);

// Imposta l'URL di base per tutte le richieste Axios
axios.defaults.baseURL = 'http://localhost:5000';

// Intercettore per aggiungere l'URL di base a tutte le richieste, se necessario
axios.interceptors.request.use((config) => {
    // Verifica se l'URL è relativo (non assoluto) e aggiunge il baseURL
    if (!config.url.startsWith('http')) {
        config.url = `${axios.defaults.baseURL}${config.url}`;
    }
    return config;
}, (error) => Promise.reject(error));

// Rendi Axios disponibile globalmente nei componenti Vue
app.config.globalProperties.$axios = axios; 

// Configura le opzioni del plugin Toast
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

// Usa il plugin Toast con le opzioni specificate
app.use(ToastPlugin, options);

app.mount('#app');
