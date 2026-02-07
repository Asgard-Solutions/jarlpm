import axios from 'axios';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
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
  signup: (data) => api.post('/auth/signup', data),
  login: (data) => api.post('/auth/login', data),
  getCurrentUser: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
  // Email verification
  verifyEmail: (token) => api.post('/auth/verify-email', { token }),
  resendVerification: (email) => api.post('/auth/resend-verification', { email }),
  // Password reset
  forgotPassword: (email) => api.post('/auth/forgot-password', { email }),
  resetPassword: (token, newPassword) => api.post('/auth/reset-password', { token, new_password: newPassword }),
  checkToken: (token) => api.get(`/auth/check-token/${token}`),
  // Legacy - kept for migration
  exchangeSession: (sessionId) => api.post('/auth/session', { session_id: sessionId }),
};

// Subscription API
export const subscriptionAPI = {
  createCheckout: (originUrl, billingCycle = 'monthly') => 
    api.post('/subscription/create-checkout', { origin_url: originUrl, billing_cycle: billingCycle }),
  getCheckoutStatus: (sessionId) => api.get(`/subscription/checkout-status/${sessionId}`),
  getStatus: () => api.get('/subscription/status'),
  getPricing: () => api.get('/subscription/pricing'),
  cancel: (cancelAtPeriodEnd = true) => api.post('/subscription/cancel', { cancel_at_period_end: cancelAtPeriodEnd }),
  reactivate: () => api.post('/subscription/reactivate'),
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

// Story API (all stories - feature-based and standalone)
export const storyAPI = {
  getAllStories: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return api.get(`/stories/all${query ? `?${query}` : ''}`);
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

// Persona API
export const personaAPI = {
  // Settings
  getSettings: () => api.get('/personas/settings'),
  updateSettings: (data) => api.put('/personas/settings', data),
  
  // Generate personas from epic
  generateFromEpic: (epicId, count = 3) => 
    api.post(`/personas/epic/${epicId}/generate`, { count }),
  
  // CRUD
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return api.get(`/personas${query ? `?${query}` : ''}`);
  },
  listForEpic: (epicId) => api.get(`/personas/epic/${epicId}`),
  get: (personaId) => api.get(`/personas/${personaId}`),
  update: (personaId, data) => api.put(`/personas/${personaId}`, data),
  delete: (personaId) => api.delete(`/personas/${personaId}`),
  regeneratePortrait: (personaId, prompt = null) => 
    api.post(`/personas/${personaId}/regenerate-portrait`, { prompt }),
};

// Scoring API (RICE & MoSCoW)
export const scoringAPI = {
  // Get scoring options for UI
  getOptions: () => api.get('/scoring/options'),
  
  // Epic MoSCoW scoring
  getEpicMoSCoW: (epicId) => api.get(`/scoring/epic/${epicId}/moscow`),
  updateEpicMoSCoW: (epicId, score) => api.put(`/scoring/epic/${epicId}/moscow`, { score }),
  suggestEpicMoSCoW: (epicId) => {
    return fetch(`${API}/scoring/epic/${epicId}/moscow/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
  },
  
  // Feature scoring (MoSCoW + RICE)
  getFeatureScores: (featureId) => api.get(`/scoring/feature/${featureId}`),
  updateFeatureMoSCoW: (featureId, score) => api.put(`/scoring/feature/${featureId}/moscow`, { score }),
  updateFeatureRICE: (featureId, data) => api.put(`/scoring/feature/${featureId}/rice`, data),
  suggestFeatureScores: (featureId) => {
    return fetch(`${API}/scoring/feature/${featureId}/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
  },
  
  // User Story RICE scoring
  getStoryRICE: (storyId) => api.get(`/scoring/story/${storyId}`),
  updateStoryRICE: (storyId, data) => api.put(`/scoring/story/${storyId}/rice`, data),
  suggestStoryRICE: (storyId) => {
    return fetch(`${API}/scoring/story/${storyId}/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
  },
  
  // Bug RICE scoring
  getBugRICE: (bugId) => api.get(`/scoring/bug/${bugId}`),
  updateBugRICE: (bugId, data) => api.put(`/scoring/bug/${bugId}/rice`, data),
  suggestBugRICE: (bugId) => {
    return fetch(`${API}/scoring/bug/${bugId}/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
  },
  
  // Bulk scoring for Epic features
  bulkScoreEpic: (epicId) => api.post(`/scoring/epic/${epicId}/bulk-score`),
  applyBulkScores: (epicId, suggestions) => api.post(`/scoring/epic/${epicId}/apply-scores`, suggestions),
  
  // Comprehensive bulk scoring (Features, Stories, Bugs)
  bulkScoreAll: (epicId) => api.post(`/scoring/epic/${epicId}/bulk-score-all`),
  applyAllScores: (epicId, data) => api.post(`/scoring/epic/${epicId}/apply-all-scores`, data),
  
  // List-first scoring endpoints
  getScoredItems: () => api.get('/scoring/scored-items'),
  getItemsForScoring: () => api.get('/scoring/items-for-scoring'),
  getEpicScores: (epicId) => api.get(`/scoring/epic/${epicId}/scores`),
  scoreStandaloneStory: (storyId, data) => api.post(`/scoring/standalone-story/${storyId}/score`, data),
  scoreStandaloneBug: (bugId, data) => api.post(`/scoring/standalone-bug/${bugId}/score`, data),
};

// AI Poker Planning API
export const pokerAPI = {
  // Get AI personas
  getPersonas: () => api.get('/poker/personas'),
  
  // Get epics with completed poker sessions
  getCompletedEpics: () => api.get('/poker/completed-epics'),
  
  // Get epics that need estimation
  getEpicsWithoutEstimation: () => api.get('/poker/epics-without-estimation'),
  
  // Get all poker sessions for an epic
  getEpicSessions: (epicId) => api.get(`/poker/epic/${epicId}/sessions`),
  
  // Estimate a story by ID
  estimateStory: (storyId) => {
    return fetch(`${API}/poker/estimate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ story_id: storyId }),
      credentials: 'include',
    });
  },
  
  // Estimate custom story text
  estimateCustom: (title, description, acceptanceCriteria = []) => {
    const params = new URLSearchParams({
      story_title: title,
      story_description: description,
    });
    acceptanceCriteria.forEach(c => params.append('acceptance_criteria', c));
    
    return fetch(`${API}/poker/estimate-custom?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
  },
  
  // Save estimate to database
  saveEstimate: (storyId, storyPoints, sessionId = null) => api.post('/poker/save-estimate', {
    story_id: storyId,
    story_points: storyPoints,
    session_id: sessionId
  }),
  
  // Get poker sessions for a story
  getSessions: (storyId) => api.get(`/poker/sessions/${storyId}`),
  
  // Get specific poker session details
  getSession: (sessionId) => api.get(`/poker/session/${sessionId}`),
};

// Initiative Library API
export const initiativeAPI = {
  // List with filters and pagination
  list: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return api.get(`/initiatives${query ? `?${query}` : ''}`);
  },
  
  // Get single initiative
  get: (epicId) => api.get(`/initiatives/${epicId}`),
  
  // Update status
  updateStatus: (epicId, status) => 
    api.patch(`/initiatives/${epicId}/status`, { status }),
  
  // Duplicate initiative
  duplicate: (epicId, newTitle = null) => 
    api.post(`/initiatives/${epicId}/duplicate`, { new_title: newTitle }),
  
  // Archive/unarchive
  archive: (epicId) => api.patch(`/initiatives/${epicId}/archive`),
  unarchive: (epicId) => api.patch(`/initiatives/${epicId}/unarchive`),
  
  // Delete permanently
  delete: (epicId) => api.delete(`/initiatives/${epicId}`),
  
  // Get summary stats
  getSummary: () => api.get('/initiatives/stats/summary'),
};

// Delivery Reality API
export const deliveryRealityAPI = {
  // Get global summary
  getSummary: () => api.get('/delivery-reality/summary'),
  
  // List all initiatives with delivery reality
  listInitiatives: () => api.get('/delivery-reality/initiatives'),
  
  // Get specific initiative delivery reality
  getInitiative: (epicId) => api.get(`/delivery-reality/initiative/${epicId}`),
  
  // Scope Plan endpoints
  getScopePlan: (epicId) => api.get(`/delivery-reality/initiative/${epicId}/scope-plan`),
  saveScopePlan: (epicId, data) => api.post(`/delivery-reality/initiative/${epicId}/scope-plan`, data),
  clearScopePlan: (epicId) => api.delete(`/delivery-reality/initiative/${epicId}/scope-plan`),
  
  // Enhanced UX - Scope Decision Summary
  getScopeSummary: (epicId) => api.get(`/delivery-reality/initiative/${epicId}/scope-summary`),
  
  // AI-powered features
  generateCutRationale: (epicId) => api.post(`/delivery-reality/initiative/${epicId}/ai/cut-rationale`),
  generateAlternativeCuts: (epicId) => api.post(`/delivery-reality/initiative/${epicId}/ai/alternative-cuts`),
  generateRiskReview: (epicId) => api.post(`/delivery-reality/initiative/${epicId}/ai/risk-review`),
};

// Sprint API
export const sprintAPI = {
  // Get current sprint summary
  getCurrentSprint: () => api.get('/sprints/current'),
  
  // Update story sprint assignment
  updateStorySprint: (storyId, sprintNumber) => api.put(`/sprints/story/${storyId}/sprint`, { sprint_number: sprintNumber }),
  
  // Update story status
  updateStoryStatus: (storyId, status, blockedReason) => api.put(`/sprints/story/${storyId}/status`, { status, blocked_reason: blockedReason }),
  
  // Commit story to current sprint
  commitStory: (storyId) => api.post(`/sprints/story/${storyId}/commit`),
  
  // Get stories from Delivery Reality scope plan
  getFromDeliveryReality: (epicId) => api.get(`/sprints/from-delivery-reality/${epicId}`),
  
  // Get saved AI insights for current sprint
  getSavedInsights: () => api.get('/sprints/insights/current'),
  
  // Get saved AI insights for specific sprint
  getInsightsBySprint: (sprintNumber) => api.get(`/sprints/insights/${sprintNumber}`),
  
  // AI Features (generate and save)
  generateKickoffPlan: () => api.post('/sprints/ai/kickoff-plan'),
  generateStandupSummary: () => api.post('/sprints/ai/standup-summary'),
  generateWipSuggestions: () => api.post('/sprints/ai/wip-suggestions'),
};

// Dashboard API
export const dashboardAPI = {
  // Get complete dashboard data
  getData: () => api.get('/dashboard'),
};

// Lean Canvas API
export const leanCanvasAPI = {
  // Generate Lean Canvas from Epic using LLM
  generate: (epicId) => api.post('/lean-canvas/generate', { epic_id: epicId }),
  
  // List all Lean Canvases
  list: () => api.get('/lean-canvas/list'),
  
  // Get epics without a canvas
  getEpicsWithoutCanvas: () => api.get('/lean-canvas/epics-without-canvas'),
  
  // Get saved Lean Canvas for an Epic
  get: (epicId) => api.get(`/lean-canvas/${epicId}`),
  
  // Save or update Lean Canvas
  save: (epicId, canvas, source = 'manual') => api.post('/lean-canvas/save', {
    epic_id: epicId,
    canvas,
    source
  }),
};

export const prdAPI = {
  // List all PRDs
  list: () => api.get('/prd/list'),
  
  // Get epics without a PRD
  getEpicsWithoutPRD: () => api.get('/prd/epics-without-prd'),
  
  // Get saved PRD for an Epic
  get: (epicId) => api.get(`/prd/${epicId}`),
  
  // Save or update PRD (legacy markdown format)
  save: (epicId, content, title = null, version = '1.0', status = 'draft') => api.post('/prd/save', {
    epic_id: epicId,
    content,
    title,
    version,
    status
  }),
  
  // Update structured PRD (JSON format)
  updateStructured: (epicId, prd, title = null, version = null) => api.put(`/prd/update/${epicId}`, {
    prd,
    title,
    version
  }),
  
  // Delete PRD
  delete: (epicId) => api.delete(`/prd/${epicId}`),
  
  // Generate PRD with AI
  generate: (epicId) => api.post(`/prd/generate/${epicId}`),
};

// Integrations API
export const integrationsAPI = {
  // Status
  getStatus: () => api.get('/integrations/status'),
  getProviderStatus: (provider) => api.get(`/integrations/status/${provider}`),
  
  // Linear
  connectLinear: (callbackUrl) => api.post('/integrations/linear/connect', { frontend_callback_url: callbackUrl }),
  disconnectLinear: () => api.post('/integrations/linear/disconnect'),
  configureLinear: (data) => api.put('/integrations/linear/configure', data),
  testLinear: () => api.get('/integrations/linear/test'),
  getLinearTeams: () => api.get('/integrations/linear/teams'),
  getLinearProjects: (teamId) => api.get(`/integrations/linear/teams/${teamId}/projects`),
  getLinearLabels: (teamId) => api.get(`/integrations/linear/teams/${teamId}/labels`),
  getLinearOrganizationLabels: () => api.get('/integrations/linear/labels'),
  
  // Jira
  connectJira: (callbackUrl) => api.post('/integrations/jira/connect', { frontend_callback_url: callbackUrl }),
  disconnectJira: () => api.post('/integrations/jira/disconnect'),
  configureJira: (data) => api.put('/integrations/jira/configure', data),
  testJira: () => api.get('/integrations/jira/test'),
  getJiraSites: () => api.get('/integrations/jira/sites'),
  getJiraProjects: () => api.get('/integrations/jira/projects'),
  getJiraIssueTypes: (projectKey) => api.get(`/integrations/jira/projects/${projectKey}/issue-types`),
  getJiraFields: () => api.get('/integrations/jira/fields'),
  
  // Azure DevOps
  connectAzureDevOps: (data) => api.post('/integrations/azure-devops/connect', data),
  disconnectAzureDevOps: () => api.post('/integrations/azure-devops/disconnect'),
  configureAzureDevOps: (data) => api.put('/integrations/azure-devops/configure', data),
  testAzureDevOps: () => api.get('/integrations/azure-devops/test'),
  getAzureDevOpsProjects: () => api.get('/integrations/azure-devops/projects'),
  getAzureDevOpsTeams: (projectName) => api.get(`/integrations/azure-devops/projects/${projectName}/teams`),
  getAzureDevOpsIterations: (projectName, teamName = null) => {
    const params = teamName ? `?team_name=${encodeURIComponent(teamName)}` : '';
    return api.get(`/integrations/azure-devops/projects/${projectName}/iterations${params}`);
  },
  getAzureDevOpsAreas: (projectName) => api.get(`/integrations/azure-devops/projects/${projectName}/areas`),
  getAzureDevOpsWorkItemTypes: (projectName) => api.get(`/integrations/azure-devops/projects/${projectName}/work-item-types`),
  getAzureDevOpsFields: (projectName) => api.get(`/integrations/azure-devops/projects/${projectName}/fields`),
  
  // Push operations
  previewPush: (provider, data) => api.post(`/integrations/${provider}/preview`, data),
  push: (provider, data) => api.post(`/integrations/${provider}/push`, data),
  getPushHistory: (provider = null, limit = 20) => {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (provider) params.append('provider', provider);
    return api.get(`/integrations/push-history?${params.toString()}`);
  },
  
  // Mappings
  getEntityMappings: (entityId) => api.get(`/integrations/mappings/${entityId}`),
};

export default api;
