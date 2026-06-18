import axios from 'axios';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
    baseURL: API_BASE_URL,
});

api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
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
    getEvents: () => api.get('/api/manager/events'),
    getEventSpecializations: (eventId) =>
        api.get(`/api/manager/events/${eventId}/specializations`),
    getEventStatistics: (eventId) =>
        api.get(`/api/manager/events/${eventId}/attempts`),
    getEventConfigs: (eventId) =>
        api.get(`/api/manager/events/${eventId}/configs`),
    saveEventConfig: (config) =>
        api.post('/api/manager/events', config),
    deleteEventConfig: (eventId, testId) => {
        return api.delete(`/api/manager/events/${eventId}/configs/${testId}`);
    }
};

export const candidatesAPI = {
    getCandidates: () => api.get('/api/manager/users'),
    getCandidateDetails: (candidateId) => api.get(`/api/manager/users/${candidateId}`),
};

export const authAPI = {
    register: (name, surname, email, password) =>
        api.post('/register', { name, surname, email, password }),
    login: (email, password) => api.post('/login', { email, password }),
    ssoExchange: (ticket) => api.post('/sso/exchange', { ticket }),
};

export const testsAPI = {
    createTest: (testData) => api.post('/api/manager/tests', testData),
    getTests: () => api.get('/api/manager/tests'),
    getTest: (testId) => api.get(`/api/manager/tests/${testId}`),
    updateTest: (testId, testData) => api.put(`/api/manager/tests/${testId}`, testData),
    deleteTest: (testId) => api.post(`/api/manager/tests/delete/${testId}`),
    getTestAttempts: (testId) => api.get(`/api/manager/tests/${testId}/attempts`),
    getAttempts: () => api.get('/api/intern/tests'),
    getTestSelection: (eventId, specializationId, applicationId) =>
        api.get('/api/intern/tests/selection', {
            params: {
                event_id: eventId,
                ...(specializationId ? { specialization_id: specializationId } : {}),
                ...(applicationId ? { application_id: applicationId } : {}),
            },
        }),
    startAttempt: (link, applicationId) =>
        api.get(`/api/intern/tests/${link}`, {
            params: applicationId ? { application_id: applicationId } : {},
        }),
    finishAttempt: (attemptData) => api.post('/api/intern/attempt/finish', attemptData),
};

export const internAPI = {
    getUserEvents: () => api.get('/api/intern/users/events'),
    createUserEvent: (eventData) => api.post('/api/intern/users/events', eventData),
};

export default api;