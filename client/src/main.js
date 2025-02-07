import { createApp } from 'vue';
import App from './App.vue';
import ToastPlugin from 'vue-toast-notification';
import 'vue-toast-notification/dist/theme-bootstrap.css';
import axios from 'axios';
import router from './router';

const app = createApp(App);

if (process.env.NODE_ENV === 'development') {
    axios.defaults.baseURL = 'http://localhost:5000';
}

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