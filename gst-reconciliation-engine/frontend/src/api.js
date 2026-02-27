import axios from 'axios'

const api = axios.create({
    baseURL: '/api/v1',
    timeout: 30000,
})

// ── Reconciliation ──
export const runReconciliation = (gstin, period, level) =>
    api.post('/reconciliation/run', null, { params: { gstin, return_period: period, level } })

export const getGSTINs = () => api.get('/reconciliation/gstins')
export const getPeriods = () => api.get('/reconciliation/periods')
export const getMismatches = (gstin, period, params = {}) =>
    api.get('/reconciliation/mismatches', { params: { gstin, return_period: period, ...params } })

// ── Dashboard ──
export const getDashboardSummary = (gstin, period) =>
    api.get('/dashboard/summary', { params: { gstin, return_period: period } })

export const getGraphData = (gstin, depth = 2) =>
    api.get('/dashboard/graph', { params: { gstin, depth } })

export const getVendorScorecard = (gstin, page = 1) =>
    api.get('/dashboard/vendor-scorecard', { params: { gstin, page } })

export const getMismatchTrends = (gstin) =>
    api.get('/dashboard/trends', { params: { gstin } })

// ── Audit ──
export const getFindings = (gstin, period) =>
    api.get('/audit/findings', { params: { gstin, return_period: period } })

export const getTraversalPath = (mismatchId) =>
    api.get('/audit/traversal', { params: { mismatch_id: mismatchId } })

// ── Risk ──
export const getVendorRisk = (gstin) => api.get(`/risk/vendor/${gstin}`)
export const getRiskHeatmap = () => api.get('/risk/heatmap')
export const getRiskCommunities = () => api.get('/risk/communities')
export const trainModel = () => api.post('/risk/train')

// ── Ingestion ──
export const seedDatabase = (params) => api.post('/ingestion/seed', null, { params })

export default api
