import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip,
    ResponsiveContainer, Cell, PieChart, Pie
} from 'recharts'
import {
    Upload, Play, AlertTriangle, CheckCircle, Network, Shield, Zap,
    FileText, Building2, ArrowRight, Clock, XCircle, Eye, Target,
    TrendingUp, GitBranch, AlertCircle, RefreshCw, Download
} from 'lucide-react'
import { runSimulation, uploadSimulation } from '../api'

const STEP_LABELS = [
    { label: 'Upload Data', icon: Upload, desc: 'Ingest CSV / demo dataset' },
    { label: 'Build Graph', icon: Network, desc: 'Construct knowledge graph' },
    { label: 'Detect Fraud', icon: Shield, desc: 'Run 4-level reconciliation' },
    { label: 'Results', icon: Target, desc: 'View fraud analysis' },
]

const FRAUD_COLORS = {
    CIRCULAR_TRADE: '#991b1b',
    PHANTOM_INVOICE: '#7c3aed',
    ITC_OVERCLAIM: '#ea580c',
    VALUE_MISMATCH: '#d97706',
}

const FRAUD_ICONS = {
    CIRCULAR_TRADE: GitBranch,
    PHANTOM_INVOICE: XCircle,
    ITC_OVERCLAIM: AlertTriangle,
    VALUE_MISMATCH: TrendingUp,
}

const fmt = v => {
    if (v == null) return '—'
    if (typeof v === 'number') {
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
        if (v >= 100000) return `₹${(v / 100000).toFixed(2)} L`
        return `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
    }
    return v
}

export default function LiveSimulation() {
    const [step, setStep] = useState(0)
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)
    const [animatingGraph, setAnimatingGraph] = useState(false)
    const [visibleNodes, setVisibleNodes] = useState([])
    const [visibleEdges, setVisibleEdges] = useState([])
    const [selectedFraud, setSelectedFraud] = useState(null)
    const canvasRef = useRef(null)
    const animRef = useRef(null)
    const fileInputRef = useRef(null)

    // Run demo simulation
    const handleDemo = async () => {
        setError(null)
        setLoading(true)
        setStep(1)
        try {
            // Step 1→2 — building graph
            await new Promise(r => setTimeout(r, 800))
            setStep(2)

            // Step 2→3 — detecting fraud
            const res = await runSimulation()
            setResult(res.data)

            await new Promise(r => setTimeout(r, 600))
            setStep(3)

            // Animate graph nodes appearing
            animateGraph(res.data.graph)
        } catch (e) {
            setError(e.response?.data?.detail || e.message || 'Simulation failed')
            setStep(0)
        } finally {
            setLoading(false)
        }
    }

    // Upload CSV
    const handleUpload = async (e) => {
        const file = e.target.files?.[0]
        if (!file) return
        setError(null)
        setLoading(true)
        setStep(1)
        try {
            await new Promise(r => setTimeout(r, 500))
            setStep(2)

            const formData = new FormData()
            formData.append('file', file)
            const res = await uploadSimulation(formData)
            setResult(res.data)

            await new Promise(r => setTimeout(r, 600))
            setStep(3)
            animateGraph(res.data.graph)
        } catch (e) {
            setError(e.response?.data?.detail || e.message || 'Upload failed')
            setStep(0)
        } finally {
            setLoading(false)
        }
    }

    // Animate nodes and edges appearing one by one
    const animateGraph = useCallback((graph) => {
        if (!graph) return
        setAnimatingGraph(true)
        setVisibleNodes([])
        setVisibleEdges([])

        const nodes = graph.nodes || []
        const edges = graph.edges || []
        let nodeIdx = 0
        let edgeIdx = 0

        const interval = setInterval(() => {
            if (nodeIdx < nodes.length) {
                const n = nodes[nodeIdx]
                if (n) setVisibleNodes(prev => [...prev, n])
                nodeIdx++
            } else if (edgeIdx < edges.length) {
                const e = edges[edgeIdx]
                if (e) setVisibleEdges(prev => [...prev, e])
                edgeIdx++
            } else {
                clearInterval(interval)
                setAnimatingGraph(false)
            }
        }, 120)

        animRef.current = interval
        return () => clearInterval(interval)
    }, [])

    useEffect(() => {
        return () => {
            if (animRef.current) clearInterval(animRef.current)
        }
    }, [])

    // Draw graph on canvas
    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas || !result?.graph) return

        const ctx = canvas.getContext('2d')
        const w = canvas.width = canvas.offsetWidth * 2
        const h = canvas.height = canvas.offsetHeight * 2
        ctx.scale(2, 2)
        const hw = w / 4, hh = h / 4

        // Position nodes in circle layout
        const nodes = visibleNodes.filter(Boolean)
        const edges = visibleEdges.filter(Boolean)
        const nodePositions = {}
        const radius = Math.min(hw, hh) * 0.65

        nodes.forEach((node, i) => {
            if (!node?.id) return
            const angle = (2 * Math.PI * i) / Math.max(result.graph.nodes.length, 1) - Math.PI / 2
            nodePositions[node.id] = {
                x: hw + radius * Math.cos(angle),
                y: hh + radius * Math.sin(angle),
            }
        })

        // Clear
        ctx.clearRect(0, 0, w / 2, h / 2)

        // Draw edges
        edges.forEach(edge => {
            const from = nodePositions[edge.from]
            const to = nodePositions[edge.to]
            if (!from || !to) return

            ctx.beginPath()
            ctx.moveTo(from.x, from.y)
            ctx.lineTo(to.x, to.y)
            ctx.strokeStyle = edge.is_circular ? '#ef4444' : '#cbd5e1'
            ctx.lineWidth = edge.is_circular ? 3 : 1.5
            if (edge.is_circular) ctx.setLineDash([])
            else ctx.setLineDash([4, 4])
            ctx.stroke()
            ctx.setLineDash([])

            // Arrow
            const angle = Math.atan2(to.y - from.y, to.x - from.x)
            const mx = (from.x + to.x) / 2
            const my = (from.y + to.y) / 2
            ctx.beginPath()
            ctx.moveTo(mx + 6 * Math.cos(angle), my + 6 * Math.sin(angle))
            ctx.lineTo(mx - 6 * Math.cos(angle - Math.PI / 6), my - 6 * Math.sin(angle - Math.PI / 6))
            ctx.lineTo(mx - 6 * Math.cos(angle + Math.PI / 6), my - 6 * Math.sin(angle + Math.PI / 6))
            ctx.fillStyle = edge.is_circular ? '#ef4444' : '#94a3b8'
            ctx.fill()

            // Edge label
            ctx.font = '9px Inter, sans-serif'
            ctx.fillStyle = '#64748b'
            ctx.textAlign = 'center'
            ctx.fillText(`${edge.invoices} inv`, mx, my - 8)
        })

        // Draw nodes
        nodes.forEach(node => {
            const pos = nodePositions[node.id]
            if (!pos) return
            const r = node.type === 'phantom' ? 18 : 22

            // Glow for high-risk
            if (node.risk_level === 'critical' || node.risk_level === 'high') {
                ctx.beginPath()
                ctx.arc(pos.x, pos.y, r + 6, 0, 2 * Math.PI)
                ctx.fillStyle = node.risk_level === 'critical' ? 'rgba(239,68,68,0.15)' : 'rgba(245,158,11,0.15)'
                ctx.fill()
            }

            // Node circle
            ctx.beginPath()
            ctx.arc(pos.x, pos.y, r, 0, 2 * Math.PI)
            const nodeColor = node.type === 'phantom' ? '#6b7280'
                : node.risk_level === 'critical' ? '#ef4444'
                    : node.risk_level === 'high' ? '#f59e0b'
                        : node.risk_level === 'medium' ? '#3b82f6'
                            : '#22c55e'
            ctx.fillStyle = nodeColor
            ctx.fill()
            ctx.strokeStyle = '#fff'
            ctx.lineWidth = 2
            ctx.stroke()

            // Node label
            ctx.font = 'bold 10px Inter, sans-serif'
            ctx.fillStyle = '#1e293b'
            ctx.textAlign = 'center'
            ctx.fillText(node.label, pos.x, pos.y + r + 14)

            // Risk badge
            ctx.font = 'bold 9px Inter, sans-serif'
            ctx.fillStyle = '#fff'
            ctx.fillText(node.type === 'phantom' ? '?' : Math.round(node.risk_score * 100), pos.x, pos.y + 3)
        })

    }, [visibleNodes, visibleEdges, result])

    const reset = () => {
        setStep(0)
        setResult(null)
        setError(null)
        setVisibleNodes([])
        setVisibleEdges([])
        setSelectedFraud(null)
        if (animRef.current) clearInterval(animRef.current)
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                        <Network size={22} className="text-purple-600" />
                        Live Simulation — Real-Time Fraud Detection
                    </h2>
                    <p className="text-sm text-slate-500 mt-0.5">Upload a dataset or run a demo — watch the knowledge graph detect fraud in real time</p>
                </div>
                {step > 0 && (
                    <button onClick={reset} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg text-xs font-medium text-slate-600 transition">
                        <RefreshCw size={13} /> Reset
                    </button>
                )}
            </div>

            {/* Progress Steps */}
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                <div className="flex items-center justify-between">
                    {STEP_LABELS.map(({ label, icon: Icon, desc }, i) => {
                        const isActive = step === i
                        const isDone = step > i
                        return (
                            <React.Fragment key={i}>
                                <div className="flex items-center gap-3">
                                    <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${isDone ? 'bg-emerald-100 text-emerald-600' : isActive ? 'bg-blue-100 text-blue-600 ring-2 ring-blue-300 animate-pulse' : 'bg-slate-100 text-slate-400'}`}>
                                        {isDone ? <CheckCircle size={18} /> : <Icon size={18} />}
                                    </div>
                                    <div>
                                        <p className={`text-xs font-semibold ${isDone ? 'text-emerald-700' : isActive ? 'text-blue-700' : 'text-slate-400'}`}>{label}</p>
                                        <p className="text-[9px] text-slate-400">{desc}</p>
                                    </div>
                                </div>
                                {i < 3 && <ArrowRight size={16} className="text-slate-300 mx-2" />}
                            </React.Fragment>
                        )
                    })}
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
                    <AlertTriangle size={18} className="text-red-500" />
                    <span className="text-sm text-red-700">{error}</span>
                </div>
            )}

            {/* Step 0: Upload / Demo */}
            {step === 0 && !loading && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {/* Demo Card */}
                    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-6 hover:shadow-lg transition cursor-pointer" onClick={handleDemo}>
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                                <Play size={24} className="text-blue-600 ml-0.5" />
                            </div>
                            <div>
                                <h3 className="text-base font-bold text-blue-800">Run Demo Simulation</h3>
                                <p className="text-xs text-blue-500">3 companies • ~80 invoices • circular trades + phantom invoices</p>
                            </div>
                        </div>
                        <div className="space-y-2">
                            {[
                                { name: 'Alpha Traders Pvt. Ltd.', gstin: '07AAACA1234A1Z5', state: 'Delhi', industry: 'Electronics' },
                                { name: 'Beta Industries', gstin: '29BBBBB5678B2Z3', state: 'Karnataka', industry: 'Manufacturing' },
                                { name: 'Gamma Exports', gstin: '27CCCCC9012C3Z1', state: 'Maharashtra', industry: 'Textiles' },
                            ].map(c => (
                                <div key={c.gstin} className="flex items-center gap-2 bg-white/70 rounded-lg px-3 py-2 border border-blue-100">
                                    <Building2 size={13} className="text-blue-400" />
                                    <span className="text-xs font-semibold text-slate-700">{c.name}</span>
                                    <span className="text-[9px] font-mono text-slate-400 ml-auto">{c.gstin}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Upload Card */}
                    <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl border border-purple-200 p-6 hover:shadow-lg transition">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center">
                                <Upload size={24} className="text-purple-600" />
                            </div>
                            <div>
                                <h3 className="text-base font-bold text-purple-800">Upload Your Dataset</h3>
                                <p className="text-xs text-purple-500">CSV with GSTIN, invoice_id, buyer, seller, value, tax, ITC</p>
                            </div>
                        </div>
                        <div className="bg-white/60 rounded-xl border-2 border-dashed border-purple-200 p-6 text-center hover:border-purple-400 transition cursor-pointer"
                            onClick={() => fileInputRef.current?.click()}>
                            <Upload size={28} className="text-purple-300 mx-auto mb-2" />
                            <p className="text-xs font-medium text-purple-600">Click to upload CSV file</p>
                            <p className="text-[9px] text-purple-400 mt-1">Max 10MB • UTF-8 encoded</p>
                        </div>
                        <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleUpload} />
                        <div className="mt-3 bg-white/50 rounded-lg p-2">
                            <p className="text-[9px] text-slate-500 font-mono">
                                Fields: seller_gstin, buyer_gstin, invoice_id, invoice_value, tax_amount, itc_claimed, date
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Loading state */}
            {loading && (
                <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
                    <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-sm font-semibold text-slate-700">
                        {step === 1 ? 'Ingesting data & building knowledge graph...' : 'Running fraud detection algorithms...'}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-1">This typically takes 2–5 seconds</p>
                </div>
            )}

            {/* Step 3: Results */}
            {step === 3 && result && (
                <>
                    {/* Summary Banner */}
                    <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-xl p-5 text-white shadow-lg">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                                <Zap size={20} className="text-amber-400" />
                                <span className="text-sm font-bold">Simulation Complete</span>
                            </div>
                            <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1">
                                <Clock size={12} className="text-slate-400" />
                                <span className="text-xs font-mono">{result.processing_time_s}s</span>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                            {[
                                { label: 'Invoices', value: result.invoice_count },
                                { label: 'Companies', value: result.companies?.length || 0 },
                                { label: 'Frauds Found', value: result.fraud_count, danger: true },
                                { label: 'Circular Trades', value: result.summary?.circular_trades || 0 },
                                { label: 'Phantom Inv.', value: result.summary?.phantom_invoices || 0 },
                                { label: 'ITC Overclaims', value: result.summary?.itc_overclaims || 0 },
                                { label: 'ITC at Risk', value: fmt(result.summary?.total_itc_at_risk) },
                            ].map(({ label, value, danger }) => (
                                <div key={label} className="text-center">
                                    <p className={`text-xl font-bold ${danger ? 'text-red-400' : 'text-white'}`}>{value}</p>
                                    <p className="text-[9px] text-slate-400 uppercase font-medium mt-1">{label}</p>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Knowledge Graph + Fraud List */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                        {/* Graph Canvas */}
                        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                            <div className="flex items-center justify-between mb-3">
                                <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                                    <Network size={15} className="text-purple-500" />
                                    Knowledge Graph — Live View
                                    {animatingGraph && <span className="text-[9px] text-blue-500 animate-pulse ml-2">● Building...</span>}
                                </h3>
                                <div className="flex gap-2">
                                    {[
                                        { color: '#ef4444', label: 'Critical' },
                                        { color: '#f59e0b', label: 'High' },
                                        { color: '#3b82f6', label: 'Medium' },
                                        { color: '#22c55e', label: 'Low' },
                                        { color: '#6b7280', label: 'Phantom' },
                                    ].map(({ color, label }) => (
                                        <div key={label} className="flex items-center gap-1">
                                            <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                                            <span className="text-[9px] text-slate-400">{label}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <canvas ref={canvasRef} className="w-full rounded-lg bg-slate-50 border border-slate-100" style={{ height: 380 }} />
                            <div className="mt-2 flex items-center gap-3 text-[9px] text-slate-400">
                                <span className="flex items-center gap-1"><div className="w-6 h-0.5 bg-red-500" /> Circular trade edge</span>
                                <span className="flex items-center gap-1"><div className="w-6 h-0.5 bg-slate-300 border-t border-dashed border-slate-400" /> Normal edge</span>
                                <span className="flex items-center gap-1">Node number = risk score %</span>
                            </div>
                        </div>

                        {/* Fraud Cases */}
                        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm max-h-[500px] overflow-y-auto">
                            <h3 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
                                <AlertTriangle size={15} className="text-red-500" />
                                Detected Fraud Cases ({result.frauds?.length || 0})
                            </h3>
                            <div className="space-y-2">
                                {(result.frauds || []).map((fraud, i) => {
                                    const FraudIcon = FRAUD_ICONS[fraud.type] || AlertTriangle
                                    const isSelected = selectedFraud?.id === fraud.id
                                    return (
                                        <div key={fraud.id || i}
                                            className={`rounded-xl border p-3 cursor-pointer transition-all ${isSelected ? 'border-red-300 bg-red-50 shadow-md' : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50'}`}
                                            onClick={() => setSelectedFraud(isSelected ? null : fraud)}>
                                            <div className="flex items-center gap-2 mb-1.5">
                                                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: (FRAUD_COLORS[fraud.type] || '#64748b') + '15' }}>
                                                    <FraudIcon size={14} style={{ color: FRAUD_COLORS[fraud.type] || '#64748b' }} />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-xs font-bold text-slate-700 truncate">{fraud.type.replace(/_/g, ' ')}</p>
                                                    <p className={`text-[9px] font-semibold ${fraud.severity === 'CRITICAL' ? 'text-red-600' : fraud.severity === 'HIGH' ? 'text-orange-600' : 'text-amber-600'}`}>
                                                        {fraud.severity} • Confidence: {(fraud.confidence * 100).toFixed(0)}%
                                                    </p>
                                                </div>
                                                <span className="text-xs font-bold text-red-700">{fmt(fraud.itc_at_risk)}</span>
                                            </div>
                                            {isSelected && (
                                                <div className="mt-2 bg-white rounded-lg p-2.5 border border-slate-100 text-[10px] text-slate-600 leading-relaxed">
                                                    <p className="mb-1.5">{fraud.description}</p>
                                                    {fraud.entities && (
                                                        <div className="mt-1.5">
                                                            <p className="font-semibold text-slate-500 mb-1">Involved Entities:</p>
                                                            {fraud.entities.map((e, j) => (
                                                                <div key={j} className="flex items-center gap-1.5 ml-2">
                                                                    <Building2 size={10} className="text-slate-400" />
                                                                    <span className="font-medium">{e.name}</span>
                                                                    <span className="font-mono text-slate-400">({e.gstin})</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                    {fraud.invoices && (
                                                        <div className="mt-1.5">
                                                            <p className="font-semibold text-slate-500 mb-1">Flagged Invoices:</p>
                                                            {fraud.invoices.map((inv, j) => (
                                                                <div key={j} className="flex items-center gap-1.5 ml-2 text-[9px]">
                                                                    <FileText size={9} className="text-slate-400" />
                                                                    <span className="font-mono">{inv.id}</span>
                                                                    <span className="text-slate-400">—</span>
                                                                    <span>{fmt(inv.value)}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                    <div className="mt-2 bg-slate-50 rounded p-1.5 text-[9px]">
                                                        <p className="font-semibold text-slate-500">Real-World Action:</p>
                                                        <p className="text-slate-600">
                                                            {fraud.type === 'CIRCULAR_TRADE' && '→ Flag all entities for simultaneous audit. Block ITC claims on circular invoices. Generate SCN under Section 74.'}
                                                            {fraud.type === 'PHANTOM_INVOICE' && '→ Block ITC immediately under Rule 36(4). Report GSTIN for cancellation. Generate DRC-01 notice.'}
                                                            {fraud.type === 'ITC_OVERCLAIM' && '→ Issue demand notice for excess ITC + 18% interest. Flag for quarterly monitoring.'}
                                                            {fraud.type === 'VALUE_MISMATCH' && '→ Issue reconciliation notice to both parties. Request revised returns within 30 days.'}
                                                        </p>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    </div>

                    {/* Risk Scorecard */}
                    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                        <h3 className="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
                            <Shield size={15} className="text-blue-500" />
                            Entity Risk Assessment
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            {(result.risk_scores || []).map((rs) => {
                                const riskColor = rs.risk_level === 'critical' ? 'red' : rs.risk_level === 'high' ? 'amber' : rs.risk_level === 'medium' ? 'blue' : 'emerald'
                                const colors = {
                                    red: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-100 text-red-700', bar: 'bg-red-500' },
                                    amber: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-100 text-amber-700', bar: 'bg-amber-500' },
                                    blue: { bg: 'bg-blue-50', border: 'border-blue-200', badge: 'bg-blue-100 text-blue-700', bar: 'bg-blue-500' },
                                    emerald: { bg: 'bg-emerald-50', border: 'border-emerald-200', badge: 'bg-emerald-100 text-emerald-700', bar: 'bg-emerald-500' },
                                }
                                const c = colors[riskColor]
                                return (
                                    <div key={rs.gstin} className={`${c.bg} border ${c.border} rounded-xl p-4`}>
                                        <div className="flex items-center gap-2 mb-3">
                                            <Building2 size={16} className="text-slate-500" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-bold text-slate-800 truncate">{rs.name}</p>
                                                <p className="text-[9px] font-mono text-slate-400">{rs.gstin}</p>
                                            </div>
                                            <span className={`${c.badge} text-[9px] font-bold px-2 py-0.5 rounded-full uppercase`}>
                                                {rs.risk_level}
                                            </span>
                                        </div>
                                        <div className="mb-2">
                                            <div className="flex justify-between text-xs mb-1">
                                                <span className="text-slate-500">Risk Score</span>
                                                <span className="font-bold text-slate-700">{(rs.risk_score * 100).toFixed(0)}%</span>
                                            </div>
                                            <div className="h-2.5 bg-white rounded-full overflow-hidden">
                                                <div className={`h-full rounded-full ${c.bar} transition-all duration-1000`} style={{ width: `${rs.risk_score * 100}%` }} />
                                            </div>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-[10px]">
                                            <div className="bg-white/70 rounded-lg p-1.5 text-center">
                                                <span className="text-slate-400">Frauds:</span>
                                                <span className="font-bold text-red-600 ml-1">{rs.fraud_count}</span>
                                            </div>
                                            <div className="bg-white/70 rounded-lg p-1.5 text-center">
                                                <span className="text-slate-400">ITC Risk:</span>
                                                <span className="font-bold text-slate-700 ml-1">{fmt(rs.itc_at_risk)}</span>
                                            </div>
                                        </div>
                                        <div className="mt-2 text-[9px] text-slate-500">
                                            Top factor: <span className="font-semibold text-slate-700">{rs.top_factor?.replace(/_/g, ' ')}</span>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>

                    {/* Use Cases */}
                    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl border border-indigo-200 p-5">
                        <h3 className="text-sm font-bold text-slate-700 mb-4 flex items-center gap-2">
                            <Eye size={15} className="text-indigo-500" />
                            Real-World Use Cases from This Simulation
                        </h3>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {[
                                {
                                    title: 'GST Department Intervention',
                                    icon: Shield,
                                    desc: `Circular trade ring detected between ${result.companies?.length || 3} entities. Officers can issue simultaneous audit notices, preventing tip-offs. ITC blocking order under Rule 86A can be invoked immediately.`,
                                    action: 'Issue SCN under Section 74(1)',
                                },
                                {
                                    title: 'ITC Blocking (Rule 86A)',
                                    icon: XCircle,
                                    desc: `Phantom invoices from unregistered GSTIN detected. System auto-recommends blocking ₹${((result.summary?.total_itc_at_risk || 0) / 100000).toFixed(1)}L in ITC credit. Electronic credit ledger should be frozen pending investigation.`,
                                    action: 'Block ITC + initiate DRC-01',
                                },
                                {
                                    title: 'Audit Case Generation',
                                    icon: FileText,
                                    desc: 'Complete evidence package auto-generated: graph subgraph, invoice trail, SHAP explanations, and timeline. Ready for DGGI/State audit team deployment within seconds.',
                                    action: 'Export audit package (PDF)',
                                },
                            ].map(({ title, icon: Icon, desc, action }) => (
                                <div key={title} className="bg-white rounded-xl border border-indigo-100 p-4">
                                    <div className="flex items-center gap-2 mb-2">
                                        <div className="w-8 h-8 rounded-lg bg-indigo-100 flex items-center justify-center">
                                            <Icon size={16} className="text-indigo-600" />
                                        </div>
                                        <h4 className="text-xs font-bold text-slate-700">{title}</h4>
                                    </div>
                                    <p className="text-[10px] text-slate-600 leading-relaxed mb-3">{desc}</p>
                                    <div className="bg-indigo-50 rounded-lg px-2.5 py-1.5 text-[9px] font-semibold text-indigo-700 flex items-center gap-1">
                                        <ArrowRight size={10} /> {action}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
