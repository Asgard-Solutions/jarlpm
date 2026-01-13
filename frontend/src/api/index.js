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
  getPermissions: (epicId) => api.get(`/epics/${epicId}/permissions`),
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

// Feature API (new lifecycle-based features)
export const featureAPI = {
  // Epic-level operations
  listForEpic: (epicId) => api.get(`/features/epic/${epicId}`),
  create: (epicId, data) => api.post(`/features/epic/${epicId}`, data),
  generate: (epicId, count = 5) => {
    // Return fetch for streaming
    return fetch(`${API}/features/epic/${epicId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count }),
      credentials: 'include',
    });
  },
  
  // Individual feature operations
  get: (featureId) => api.get(`/features/${featureId}`),
  update: (featureId, data) => api.put(`/features/${featureId}`, data),
  delete: (featureId) => api.delete(`/features/${featureId}`),
  approve: (featureId) => api.post(`/features/${featureId}/approve`),
  
  // Feature conversation
  getConversation: (featureId) => api.get(`/features/${featureId}/conversation`),
  chat: (featureId, content) => {
    // Return fetch for streaming
    return fetch(`${API}/features/${featureId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      credentials: 'include',
    });
  },
};

// User Story API (lifecycle-based stories from features)
export const userStoryAPI = {
  // Feature-level operations
  listForFeature: (featureId) => api.get(`/stories/feature/${featureId}`),
  create: (featureId, data) => api.post(`/stories/feature/${featureId}`, data),
  generate: (featureId, count = 5) => {
    // Return fetch for streaming
    return fetch(`${API}/stories/feature/${featureId}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count }),
      credentials: 'include',
    });
  },
  
  // Individual story operations
  get: (storyId) => api.get(`/stories/${storyId}`),
  update: (storyId, data) => api.put(`/stories/${storyId}`, data),
  delete: (storyId) => api.delete(`/stories/${storyId}`),
  approve: (storyId) => api.post(`/stories/${storyId}/approve`),
  
  // Story conversation
  getConversation: (storyId) => api.get(`/stories/${storyId}/conversation`),
  chat: (storyId, content) => {
    // Return fetch for streaming
    return fetch(`${API}/stories/${storyId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      credentials: 'include',
    });
  },
  
  // Standalone story operations
  listStandalone: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return api.get(`/stories/standalone${query ? `?${query}` : ''}`);
  },
  getStandalone: (storyId) => api.get(`/stories/standalone/${storyId}`),
  createStandalone: (data) => api.post('/stories/standalone', data),
  updateStandalone: (storyId, data) => api.put(`/stories/standalone/${storyId}`, data),
  deleteStandalone: (storyId) => api.delete(`/stories/standalone/${storyId}`),
  approveStandalone: (storyId) => api.post(`/stories/standalone/${storyId}/approve`),
  chatStandalone: (storyId, content) => {
    return fetch(`${API}/stories/standalone/${storyId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
      credentials: 'include',
    });
  },
  
  // AI-assisted story creation
  aiChat: (content, conversationHistory = []) => {
    return fetch(`${API}/stories/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, conversation_history: conversationHistory }),
      credentials: 'include',
    });
  },
  createFromProposal: (proposal) => api.post('/stories/ai/create-from-proposal', proposal),
};

// Bug API
export const bugAPI = {
  // CRUD
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return api.get(`/bugs${query ? `?${query}` : ''}`);
  },
  get: (bugId) => api.get(`/bugs/${bugId}`),
  create: (data) => api.post('/bugs', data),
  update: (bugId, data) => api.patch(`/bugs/${bugId}`, data),
  delete: (bugId) => api.delete(`/bugs/${bugId}`),
  
  // Status transitions
  transition: (bugId, newStatus, notes = null) => 
    api.post(`/bugs/${bugId}/transition`, { new_status: newStatus, notes }),
  getHistory: (bugId) => api.get(`/bugs/${bugId}/history`),
  
  // Links
  addLinks: (bugId, links) => api.post(`/bugs/${bugId}/links`, { links }),
  removeLink: (bugId, linkId) => api.delete(`/bugs/${bugId}/links/${linkId}`),
  getLinks: (bugId) => api.get(`/bugs/${bugId}/links`),
  
  // Entity queries
  getForEntity: (entityType, entityId) => api.get(`/bugs/by-entity/${entityType}/${entityId}`),
  
  // AI assistance
  refineDescription: (bugId) => {
    return fetch(`${API}/bugs/${bugId}/ai/refine-description`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
  },
  suggestSeverity: (bugId) => api.post(`/bugs/${bugId}/ai/suggest-severity`),
  
  // AI-assisted bug creation
  aiChat: (content, conversationHistory = []) => {
    return fetch(`${API}/bugs/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, conversation_history: conversationHistory }),
      credentials: 'include',
    });
  },
  createFromProposal: (proposal) => api.post('/bugs/ai/create-from-proposal', proposal),
};

export default api;
