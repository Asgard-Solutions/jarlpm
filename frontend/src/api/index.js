import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Create axios instance with credentials
const api = axios.create({
  baseURL: API,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Auth API
export const authAPI = {
  exchangeSession: (sessionId) => api.post('/auth/session', { session_id: sessionId }),
  getCurrentUser: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
};

// Subscription API
export const subscriptionAPI = {
  createCheckout: (originUrl) => api.post('/subscription/create-checkout', { origin_url: originUrl }),
  getCheckoutStatus: (sessionId) => api.get(`/subscription/checkout-status/${sessionId}`),
  getStatus: () => api.get('/subscription/status'),
};

// LLM Provider API
export const llmProviderAPI = {
  list: () => api.get('/llm-providers'),
  create: (data) => api.post('/llm-providers', data),
  validate: (data) => api.post('/llm-providers/validate', data),
  delete: (configId) => api.delete(`/llm-providers/${configId}`),
  activate: (configId) => api.put(`/llm-providers/${configId}/activate`),
};

// Product Delivery Context API
export const deliveryContextAPI = {
  get: () => api.get('/delivery-context'),
  update: (data) => api.put('/delivery-context', data),
};

// Epic API
export const epicAPI = {
  list: () => api.get('/epics'),
  create: (title) => api.post('/epics', { title }),
  get: (epicId) => api.get(`/epics/${epicId}`),
  delete: (epicId) => api.delete(`/epics/${epicId}`),
  chat: (epicId, content) => {
    // Return fetch for streaming
    return fetch(`${API}/epics/${epicId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      credentials: 'include',
    });
  },
  confirmProposal: (epicId, proposalId, confirmed) => 
    api.post(`/epics/${epicId}/confirm-proposal`, { proposal_id: proposalId, confirmed }),
  getTranscript: (epicId) => api.get(`/epics/${epicId}/transcript`),
  getDecisions: (epicId) => api.get(`/epics/${epicId}/decisions`),
  listArtifacts: (epicId) => api.get(`/epics/${epicId}/artifacts`),
  createArtifact: (epicId, data) => api.post(`/epics/${epicId}/artifacts`, data),
  deleteArtifact: (epicId, artifactId) => api.delete(`/epics/${epicId}/artifacts/${artifactId}`),
};

export default api;
