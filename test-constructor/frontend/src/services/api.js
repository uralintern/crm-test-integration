import axios from 'axios';

const API_BASE_URL = 'http://localhost:8080';

const api = axios.create({
    baseURL: API_BASE_URL,
})

api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
        }
        return Promise.reject(error);
    }
);
export const eventsAPI = {
    getEvents: () =>
        api.get('/api/manager/events'),
}

export const authAPI = {
    register: (name, surname, email, password) =>
        api.post('/register', { name, surname, email, password }),

    login: (email, password) =>
        api.post('/login', { email, password }),
}

export const testsAPI = {
    // Manager endpoints
    createTest: (testData) =>
        api.post('/api/manager/tests', testData),

    getTests: () =>
        api.get('/api/manager/tests'),

    deleteTest: (testId) =>
        api.post(`/api/manager/tests/delete/${testId}`),

    // Intern endpoints
    getAttempts: () =>
        api.get('/api/intern/tests'),

    startAttempt: (link) =>
        api.get(`/api/intern/tests/${link}`),

    finishAttempt: (attemptData) =>
        api.post('/api/intern/attempt/finish', attemptData),
}

export default api;