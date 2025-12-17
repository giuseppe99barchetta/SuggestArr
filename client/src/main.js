import { createApp } from 'vue';
import App from './App.vue';
import ToastPlugin from 'vue-toast-notification';
import 'vue-toast-notification/dist/theme-default.css';
import '@/assets/styles/toast-custom.css';
import axios from 'axios';
import router from './router';
import '@/assets/styles/theme.css';

const app = createApp(App);

if (process.env.NODE_ENV === 'development') {
    axios.defaults.baseURL = 'http://localhost:5000';
}

const options = {
    position: 'top-right',
    duration: 5000,
    dismissible: true,
    pauseOnHover: true,
    queue: true,
};

app.use(ToastPlugin, options);