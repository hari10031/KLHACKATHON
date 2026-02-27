import React, { useState, useEffect } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, AreaChart, Area, Legend, RadarChart, PolarGrid,
    PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts'
import {
    runReconciliation, getDashboardSummary, getMismatchTrends
} from '../api'
import {
    TrendingUp, TrendingDown, AlertTriangle, ShieldCheck, FileWarning,
    DollarSign, Activity, Play, Download, RefreshCw, Users, Zap, Target,
    Building2, Mail, AlertCircle, CheckCircle, Clock, GitBranch, BarChart3
} from 'lucide-react'

const SEV_COLORS = { CRITICAL: '#991b1b', HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e' }
const TYPE_COLORS = ['#3b82f6', '#8b5cf6', '#ef4444', '#f59e0b', '#10b981', '#ec4899', '#6366f1', '#14b8a6', '#f97316', '#64748b']

// Normalize risk score to 0-100% — clamp strictly
const normalizeRisk = (score) => {
    if (score == null) return 0
    const s = Number(score)
    if (isNaN(s)) return 0
    return Math.min(100, Math.max(0, s))
}

const fmt = v => {
    if (v == null) return '—'
    if (typeof v === 'number') {
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
        if (v >= 100000) return `₹${(v / 100000).toFixed(2)} L`
        return `₹${v.toLocaleString('en-IN')}`
    }
    return v
}

export default function ReconciliationSummary({ gstin, period }) {
    const [summary, setSummary] = useState(null)
    const [running, setRunning] = useState(false)
    const [trends, setTrends] = useState([])
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(true)
    const [showNotice, setShowNotice] = useState(false)

    useEffect(() => {
        if (!gstin) return
        setLoading(true)
        Promise.all([
            getDashboardSummary(gstin, period).then(r => setSummary(r.data)).catch(() => { }),
            getMismatchTrends(gstin).then(r => setTrends(r.data.trends || [])).catch(() => { }),
        ]).finally(() => setLoading(false))
    }, [gstin, period])

    const handleRun = async () => {
        setRunning(true); setError(null)
        try {
            const res = await runReconciliation(gstin, period)
            setSummary(prev => ({ ...prev, reconciliation: res.data }))
        } catch (e) { setError(e.response?.data?.detail || 'Reconciliation failed') }
        setRunning(false)
    }

    const recon = summary?.reconciliation
    const severityData = summary?.mismatches?.map(m => ({ name: m.severity, count: m.cnt, itcRisk: m.itc_risk })) || []
    const typeData = summary?.mismatch_types?.map((m, i) => ({ name: m.type?.replace(/_/g, ' '), count: m.cnt, fill: TYPE_COLORS[i % TYPE_COLORS.length] })) || []
    const totalMismatches = severityData.reduce((s, d) => s + (d.count || 0), 0)
    const totalItcRisk = severityData.reduce((s, d) => s + (d.itcRisk || 0), 0)
    const riskScore = normalizeRisk(summary?.risk?.risk_score)
    const riskLabel = summary?.risk?.risk_label || 'unknown'
    const invoices = summary?.invoices || {}
    const vendorCount = summary?.vendor_count || 0
    const complianceRate = invoices.total_invoices ? Math.max(0, 100 - (totalMismatches / invoices.total_invoices * 100)) : 100
    const entityName = invoices.entity_name && invoices.entity_name !== 'Unknown' ? invoices.entity_name : null
    const criticalCount = severityData.find(d => d.name === 'CRITICAL')?.count || 0
    const highCount = severityData.find(d => d.name === 'HIGH')?.count || 0
    const isCritical = riskScore >= 70

    // Radar data for risk profile
    const radarData = [
        { metric: 'Risk Score', value: riskScore },
        { metric: 'Mismatch Rate', value: invoices.total_invoices ? Math.min(100, (totalMismatches / invoices.total_invoices) * 100) : 0 },
        { metric: 'Critical %', value: totalMismatches ? (criticalCount / totalMismatches) * 100 : 0 },
        { metric: 'ITC Exposure', value: Math.min(100, (totalItcRisk / Math.max(invoices.total_taxable || 1, 1)) * 100) },
        { metric: 'Vendor Risk', value: riskScore },
    ]

    if (loading) return (
        <div className="space-y-6 animate-fade-in">
            {[...Array(3)].map((_, i) => <div key={i} className="h-32 shimmer rounded-xl" />)}
        </div>
    )

    const kpis = [
        { label: 'Total Invoices', value: recon?.total_invoices ?? invoices.total_invoices ?? 0, icon: FileWarning, gradient: 'gradient-blue', change: null, sub: `${fmt(invoices.total_taxable)} taxable` },
        { label: 'Matched', value: recon?.matched ?? '—', icon: ShieldCheck, gradient: 'gradient-green', change: null, sub: 'Clean transactions' },
        { label: 'Fraud Cases', value: recon ? (recon.partial_matched + recon.unmatched) : totalMismatches, icon: AlertTriangle, gradient: 'gradient-red', change: totalMismatches > 0 ? 'critical' : null, sub: `${criticalCount} critical, ${highCount} high` },
        { label: 'ITC at Risk', value: fmt(recon?.itc_at_risk ?? (totalItcRisk || 0)), icon: DollarSign, gradient: 'gradient-amber', change: null, sub: 'Potential fraud amount' },
        { label: 'Active Vendors', value: vendorCount, icon: Users, gradient: 'gradient-purple', change: null, sub: 'In supply chain' },
        { label: 'Risk Score', value: `${riskScore.toFixed(0)}%`, icon: Target, gradient: riskScore > 50 ? 'gradient-red' : riskScore > 30 ? 'gradient-amber' : 'gradient-green', change: riskLabel, sub: riskLabel.toUpperCase() },
    ]

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Title + Actions */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Reconciliation Dashboard</h2>
                    <div className="flex items-center gap-2 mt-1">
                        {entityName && (
                            <span className="flex items-center gap-1.5 text-sm text-slate-700 font-semibold">
                                <Building2 size={14} className="text-blue-500" /> {entityName}
                            </span>
                        )}
                        {entityName && <span className="text-sm text-slate-400">|</span>}
                        <span className="text-sm text-slate-500 font-mono">{gstin}</span>
                        {period && <><span className="text-sm text-slate-400">|</span><span className="text-sm text-slate-500">Period: {period}</span></>}
                    </div>
                </div>
                <div className="flex gap-2">
                    {isCritical && (
                        <button onClick={() => setShowNotice(true)}
                            className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-4 py-2.5 rounded-lg text-sm font-semibold shadow-md shadow-red-200 transition-all">
                            <Mail size={16} /> Issue SCN
                        </button>
                    )}
                    <button onClick={handleRun} disabled={running || !gstin}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold shadow-md shadow-blue-200 disabled:opacity-50 transition-all">
                        {running ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />}
                        {running ? 'Running...' : 'Run Reconciliation'}
                    </button>
                    <button onClick={() => window.open(`/api/v1/audit/report?gstin=${gstin}`, '_blank')}
                        className="flex items-center gap-2 border border-slate-300 text-slate-600 hover:bg-slate-50 px-4 py-2.5 rounded-lg text-sm font-medium transition-all">
                        <Download size={16} /> Export Report
                    </button>
                </div>
            </div>

            {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-center gap-2"><AlertTriangle size={16} />{error}</div>}

            {/* Critical Alert Banner */}
            {isCritical && (
                <div className="bg-red-50 border-2 border-red-300 rounded-xl p-4 flex items-start gap-4 animate-fade-in">
                    <div className="w-12 h-12 rounded-xl gradient-red flex items-center justify-center flex-shrink-0 shadow-lg">
                        <AlertTriangle size={24} className="text-white" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-base font-bold text-red-800">CRITICAL RISK ALERT</h3>
                        <p className="text-sm text-red-600 mt-0.5">
                            {entityName || gstin} has a risk score of <span className="font-extrabold">{riskScore.toFixed(0)}%</span> with
                            {' '}{criticalCount} critical and {highCount} high-severity findings.
                            Total ITC at risk: <span className="font-bold">{fmt(totalItcRisk)}</span>.
                            Immediate action required — consider issuing a Show Cause Notice (SCN).
                        </p>
                    </div>
                    <button onClick={() => setShowNotice(true)}
                        className="flex items-center gap-1.5 bg-red-600 text-white px-4 py-2 rounded-lg text-xs font-bold hover:bg-red-700 transition-all flex-shrink-0">
                        <Mail size={14} /> Send Notice
                    </button>
                </div>
            )}

            {/* KPI Cards */}
            <div className="grid grid-cols-6 gap-4">
                {kpis.map(({ label, value, icon: Icon, gradient, change, sub }) => (
                    <div key={label} className={`${gradient} rounded-xl p-4 text-white shadow-lg card-hover relative overflow-hidden`}>
                        <div className="absolute top-0 right-0 w-20 h-20 rounded-full bg-white/5 -mr-6 -mt-6" />
                        <div className="flex items-center justify-between mb-2">
                            <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center">
                                <Icon size={16} />
                            </div>
                            {change === 'critical' && <div className="w-2 h-2 rounded-full bg-white animate-pulse-dot" />}
                        </div>
                        <p className="text-2xl font-extrabold leading-tight">{value}</p>
                        <p className="text-[11px] text-white/70 mt-1 uppercase tracking-wider font-medium">{label}</p>
                        {sub && <p className="text-[9px] text-white/50 mt-0.5">{sub}</p>}
                        {change && change !== 'critical' && (
                            <span className="absolute bottom-3 right-3 text-[10px] bg-white/20 px-2 py-0.5 rounded-full uppercase font-bold">{change}</span>
                        )}
                    </div>
                ))}
            </div>

            {/* Compliance Rate + Charts Grid */}
            <div className="grid grid-cols-2 gap-6">
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm col-span-1">
                    <h3 className="text-sm font-semibold text-slate-600 mb-4 flex items-center gap-2">
                        <Zap size={14} className="text-blue-500" /> Compliance Health
                    </h3>
                    <div className="flex flex-col items-center">
                        <div className="relative w-32 h-32">
                            <svg viewBox="0 0 36 36" className="w-32 h-32 -rotate-90">
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none" stroke="#e2e8f0" strokeWidth="3" />
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none" stroke={complianceRate > 80 ? '#22c55e' : complianceRate > 50 ? '#f59e0b' : '#ef4444'}
                                    strokeWidth="3" strokeDasharray={`${complianceRate}, 100`} strokeLinecap="round" />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-3xl font-extrabold text-slate-800">{complianceRate.toFixed(0)}%</span>
                                <span className="text-[10px] text-slate-400 uppercase font-semibold">Compliance</span>
                            </div>
                        </div>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                        <div className="bg-slate-50 rounded-lg p-2 text-center">
                            <p className="font-bold text-slate-700">{fmt(invoices.total_taxable)}</p>
                            <p className="text-slate-400">Taxable Value</p>
                        </div>
                        <div className="bg-slate-50 rounded-lg p-2 text-center">
                            <p className="font-bold text-slate-700">{fmt(invoices.total_tax)}</p>
                            <p className="text-slate-400">Total Tax</p>
                        </div>
                    </div>
                </div>

                {/* Severity Donut */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-2 flex items-center gap-2">
                        <AlertTriangle size={14} className="text-red-500" /> Findings by Severity
                    </h3>
                    {severityData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <PieChart>
                                <Pie data={severityData} dataKey="count" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} label={({ name, count }) => `${name}: ${count}`}>
                                    {severityData.map(e => <Cell key={e.name} fill={SEV_COLORS[e.name] || '#94a3b8'} />)}
                                </Pie>
                                <Tooltip formatter={v => v.toLocaleString('en-IN')} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-16">No mismatches found</p>}
                </div>

                {/* Mismatch Types */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-2 flex items-center gap-2">
                        <Activity size={14} className="text-purple-500" /> Fraud Types Distribution
                    </h3>
                    {typeData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={typeData} layout="vertical" margin={{ left: 100, right: 10 }}>
                                <XAxis type="number" tick={{ fontSize: 10 }} />
                                <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} width={95} />
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                <Tooltip />
                                <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={16}>
                                    {typeData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-16">No data</p>}
                </div>

                {/* Risk Profile Radar */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-2 flex items-center gap-2">
                        <Target size={14} className="text-indigo-500" /> Risk Profile
                    </h3>
                    <ResponsiveContainer width="100%" height={200}>
                        <RadarChart outerRadius={70} data={radarData}>
                            <PolarGrid stroke="#e2e8f0" />
                            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 9, fill: '#64748b' }} />
                            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
                            <Radar dataKey="value" stroke="#ef4444" fill="#ef4444" fillOpacity={0.2} strokeWidth={2} />
                        </RadarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Trends + Top Fraud Alerts */}
            <div className="grid grid-cols-2 gap-6">
                {/* Trends */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-3 flex items-center gap-2">
                        <TrendingUp size={14} className="text-blue-500" /> Monthly Mismatch Trend
                    </h3>
                    {trends.length > 0 ? (
                        <ResponsiveContainer width="100%" height={220}>
                            <AreaChart data={trends}>
                                <defs>
                                    <linearGradient id="gradArea" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                <XAxis dataKey="period" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
                                <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0' }} />
                                <Area type="monotone" dataKey="mismatch_count" stroke="#3b82f6" fill="url(#gradArea)" strokeWidth={2} name="Mismatches" />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-16">No trend data</p>}
                </div>

                {/* Top Fraud Alerts */}
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-3 flex items-center gap-2">
                        <AlertTriangle size={14} className="text-red-500" /> Top Fraud Alerts
                    </h3>
                    <div className="space-y-2 max-h-[250px] overflow-y-auto">
                        {(summary?.top_mismatches || []).map((m, i) => (
                            <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-slate-100 hover:bg-slate-50 transition-colors">
                                <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${m.severity === 'CRITICAL' ? 'bg-red-900' : m.severity === 'HIGH' ? 'bg-red-500' : m.severity === 'MEDIUM' ? 'bg-amber-500' : 'bg-green-500'}`} />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs font-semibold text-slate-700">{m.type?.replace(/_/g, ' ')}</span>
                                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${m.severity === 'CRITICAL' ? 'bg-red-100 text-red-700' : m.severity === 'HIGH' ? 'bg-red-50 text-red-600' : m.severity === 'MEDIUM' ? 'bg-amber-50 text-amber-600' : 'bg-green-50 text-green-600'}`}>{m.severity}</span>
                                    </div>
                                    <p className="text-[11px] text-slate-500 truncate mt-0.5">{m.description || m.narrative?.slice(0, 100) || m.id}</p>
                                </div>
                                <span className="text-xs font-mono font-bold text-red-600 flex-shrink-0">{fmt(m.itc_risk)}</span>
                            </div>
                        ))}
                        {(!summary?.top_mismatches || summary.top_mismatches.length === 0) && (
                            <p className="text-center text-slate-400 py-8">No alerts — run reconciliation to detect fraud</p>
                        )}
                    </div>
                </div>
            </div>

            {/* Risk Network Metrics */}
            {summary?.risk && (
                <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-4 flex items-center gap-2">
                        <Target size={14} className="text-indigo-500" /> Network Risk Analysis
                    </h3>
                    <div className="grid grid-cols-5 gap-4">
                        {[
                            { label: 'Risk Score', value: `${riskScore.toFixed(1)}%`, sub: riskLabel.toUpperCase(), color: riskScore > 50 ? 'text-red-600' : riskScore > 30 ? 'text-amber-600' : 'text-green-600' },
                            { label: 'PageRank', value: summary.risk.pagerank?.toFixed(4) || 'N/A', sub: 'Centrality', color: 'text-blue-600' },
                            { label: 'Degree', value: summary.risk.degree?.toFixed(4) || 'N/A', sub: 'Connections', color: 'text-purple-600' },
                            { label: 'Betweenness', value: summary.risk.betweenness?.toFixed(4) || 'N/A', sub: 'Bridge Score', color: 'text-indigo-600' },
                            { label: 'Community', value: summary.risk.community ?? 'N/A', sub: 'Cluster ID', color: 'text-teal-600' },
                        ].map(({ label, value, sub, color }) => (
                            <div key={label} className="text-center p-3 rounded-lg bg-slate-50">
                                <p className={`text-lg font-bold ${color}`}>{value}</p>
                                <p className="text-xs text-slate-500 font-medium">{label}</p>
                                <p className="text-[10px] text-slate-400">{sub}</p>
                            </div>
                        ))}
                    </div>
                    <div className="mt-4">
                        <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                            <span>Risk Level</span>
                            <span>{riskScore.toFixed(0)}%</span>
                        </div>
                        <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
                            <div className={`h-full rounded-full transition-all duration-1000 ${riskScore > 70 ? 'bg-red-500' : riskScore > 50 ? 'bg-amber-500' : riskScore > 30 ? 'bg-yellow-400' : 'bg-green-500'}`}
                                style={{ width: `${riskScore.toFixed(0)}%` }} />
                        </div>
                        <div className="flex justify-between text-[10px] text-slate-400 mt-1">
                            <span>Low</span><span>Medium</span><span>High</span><span>Critical</span>
                        </div>
                    </div>
                </div>
            )}
            {/* SCN Notice Modal */}
            {showNotice && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowNotice(false)}>
                    <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
                        <div className="bg-red-600 text-white p-6 rounded-t-2xl">
                            <div className="flex items-center gap-3">
                                <Mail size={24} />
                                <div>
                                    <h2 className="text-lg font-bold">Show Cause Notice (SCN)</h2>
                                    <p className="text-red-100 text-sm">Under Section 73/74 of CGST Act, 2017</p>
                                </div>
                            </div>
                        </div>
                        <div className="p-6 space-y-4 text-sm text-slate-700">
                            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                                <p className="font-semibold text-red-800 mb-2">NOTICE TO:</p>
                                <p className="font-bold text-slate-800">{entityName || 'Registered Taxpayer'}</p>
                                <p className="text-slate-600">GSTIN: {gstin}</p>
                                <p className="text-slate-600">Period: {period}</p>
                            </div>
                            <div>
                                <p className="font-semibold mb-1">Subject: Discrepancies detected in GST Returns</p>
                                <p className="text-slate-600 leading-relaxed">
                                    During the automated reconciliation and risk assessment of your GST returns, the system has identified <strong className="text-red-600">{criticalCount + highCount} critical/high-risk discrepancies</strong> with
                                    a composite risk score of <strong className="text-red-600">{riskScore.toFixed(1)}%</strong>.
                                </p>
                            </div>
                            <div>
                                <p className="font-semibold mb-2">Key Findings:</p>
                                <ul className="list-disc list-inside space-y-1 text-slate-600">
                                    <li>Total mismatches detected: <strong>{summary?.total_mismatches || 0}</strong></li>
                                    <li>ITC at risk: <strong>{fmt(summary?.total_itc_at_risk)}</strong></li>
                                    <li>Critical findings: <strong>{criticalCount}</strong></li>
                                    <li>High-risk findings: <strong>{highCount}</strong></li>
                                    <li>Compliance rate: <strong>{complianceRate.toFixed(1)}%</strong></li>
                                </ul>
                            </div>
                            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800">
                                <p className="font-semibold flex items-center gap-2"><AlertTriangle size={14} /> Action Required</p>
                                <p className="mt-1 text-sm">You are hereby directed to furnish a reply within <strong>30 days</strong> from the date of this notice, explaining the discrepancies or pay the differential tax along with applicable interest and penalty.</p>
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button onClick={() => { window.print(); }} className="flex-1 bg-red-600 text-white py-2.5 rounded-lg font-semibold hover:bg-red-700 transition-colors flex items-center justify-center gap-2">
                                    <Download size={16} /> Download & Print
                                </button>
                                <button onClick={() => setShowNotice(false)} className="flex-1 bg-slate-100 text-slate-700 py-2.5 rounded-lg font-semibold hover:bg-slate-200 transition-colors">
                                    Close
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
