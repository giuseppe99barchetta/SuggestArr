import { createApp } from 'vue';
import App from './App.vue';
import ToastPlugin from 'vue-toast-notification';
import 'vue-toast-notification/dist/theme-bootstrap.css';
import axios from 'axios';

const app = createApp(App);

axios.defaults.baseURL = 'http://localhost:5000'; // Replace with your backend URL

// Example usage of axios in components
app.config.globalProperties.$axios = axios; 

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
app.mount('#app');