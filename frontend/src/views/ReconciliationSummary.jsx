import React, { useState, useEffect } from 'react'
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, AreaChart, Area, RadarChart,
    PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts'
import { runReconciliation, getDashboardSummary, getMismatchTrends } from '../api'
import {
    TrendingUp, AlertTriangle, ShieldCheck, FileWarning,
    DollarSign, Activity, Play, Download, RefreshCw, Users,
    Zap, Target, Building2, Mail, CheckCircle
} from 'lucide-react'

const SEV_COLORS = { CRITICAL: '#991b1b', HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e' }
const TYPE_COLORS = ['#14b8a6','#3b82f6','#8b5cf6','#ef4444','#f59e0b','#10b981','#ec4899','#6366f1','#f97316','#64748b']

const normalizeRisk = s => { if (s == null) return 0; const n = Number(s); return isNaN(n) ? 0 : Math.min(100, Math.max(0, n)) }
const fmt = v => {
    if (v == null) return '—'
    if (typeof v === 'number') {
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
        if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`
        return `₹${v.toLocaleString('en-IN')}`
    }
    return v
}
const riskGradient = s => s > 70 ? 'gradient-red' : s > 50 ? 'gradient-amber' : s > 30 ? 'gradient-indigo' : 'gradient-teal'

const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
        <div className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 shadow-xl text-xs">
            {label && <p className="text-slate-400 mb-1">{label}</p>}
            {payload.map((p, i) => (
                <p key={i} className="font-semibold" style={{ color: p.color || p.fill || '#14b8a6' }}>
                    {p.name}: {typeof p.value === 'number' ? p.value.toLocaleString('en-IN') : p.value}
                </p>
            ))}
        </div>
    )
}

function SectionHeading({ icon: Icon, label }) {
    return (
        <h3 className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 mb-3 text-slate-400"
            style={{ letterSpacing: '0.1em' }}>
            <Icon size={12} /> {label}
        </h3>
    )
}

function KpiCard({ label, value, icon: Icon, gradient, sub, trend }) {
    return (
        <div className={`kpi-card ${gradient}`}>
            <div className="flex items-start justify-between mb-3 relative z-10">
                <div className="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center">
                    <Icon size={17} className="text-white" />
                </div>
                {trend && (
                    <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-white/15 uppercase tracking-wider">
                        {trend}
                    </span>
                )}
            </div>
            <p className="text-[22px] font-extrabold leading-tight relative z-10">{value}</p>
            <p className="text-[10px] text-white/65 mt-0.5 uppercase tracking-wider font-semibold relative z-10">{label}</p>
            {sub && <p className="text-[9px] text-white/40 mt-0.5 relative z-10">{sub}</p>}
        </div>
    )
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
            getDashboardSummary(gstin, period).then(r => setSummary(r.data)).catch(() => {}),
            getMismatchTrends(gstin).then(r => setTrends(r.data.trends || [])).catch(() => {}),
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

    const recon         = summary?.reconciliation
    const severityData  = summary?.mismatches?.map(m => ({ name: m.severity, count: m.cnt, itcRisk: m.itc_risk })) || []
    const typeData      = summary?.mismatch_types?.map((m, i) => ({ name: m.type?.replace(/_/g, ' '), count: m.cnt, fill: TYPE_COLORS[i % TYPE_COLORS.length] })) || []
    const totalMismatches = severityData.reduce((s, d) => s + (d.count || 0), 0)
    const totalItcRisk    = severityData.reduce((s, d) => s + (d.itcRisk || 0), 0)
    const riskScore     = normalizeRisk(summary?.risk?.risk_score)
    const riskLabel     = summary?.risk?.risk_label || 'unknown'
    const invoices      = summary?.invoices || {}
    const vendorCount   = summary?.vendor_count || 0
    const complianceRate = invoices.total_invoices ? Math.max(0, 100 - (totalMismatches / invoices.total_invoices * 100)) : 100
    const entityName    = invoices.entity_name && invoices.entity_name !== 'Unknown' ? invoices.entity_name : null
    const criticalCount = severityData.find(d => d.name === 'CRITICAL')?.count || 0
    const highCount     = severityData.find(d => d.name === 'HIGH')?.count || 0
    const isCritical    = riskScore >= 70
    const compColor     = complianceRate > 80 ? '#22c55e' : complianceRate > 50 ? '#f59e0b' : '#ef4444'

    const radarData = [
        { metric: 'Risk Score',   value: riskScore },
        { metric: 'Mismatch %',   value: invoices.total_invoices ? Math.min(100, (totalMismatches / invoices.total_invoices) * 100) : 0 },
        { metric: 'Critical %',   value: totalMismatches ? (criticalCount / totalMismatches) * 100 : 0 },
        { metric: 'ITC Exposure', value: Math.min(100, (totalItcRisk / Math.max(invoices.total_taxable || 1, 1)) * 100) },
        { metric: 'Vendor Risk',  value: riskScore },
    ]

    if (loading) return (
        <div className="space-y-5 animate-fade-in">
            <div className="h-8 w-64 shimmer rounded-lg" />
            <div className="grid grid-cols-6 gap-3">{[...Array(6)].map((_, i) => <div key={i} className="h-28 shimmer rounded-xl" />)}</div>
            <div className="grid grid-cols-2 gap-4">{[...Array(4)].map((_, i) => <div key={i} className="h-52 shimmer rounded-xl" />)}</div>
        </div>
    )

    return (
        <div className="space-y-5 animate-fade-in">

            {/* ── Header ──────────────────────────────────────────────────── */}
            <div className="flex items-start justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <h2 className="text-xl font-extrabold text-slate-800 tracking-tight">Reconciliation Dashboard</h2>
                        {isCritical && <span className="badge badge-critical">Critical Alert</span>}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                        {entityName && <span className="flex items-center gap-1 font-semibold text-slate-700"><Building2 size={12} className="text-teal-500" />{entityName}</span>}
                        {entityName && <span className="text-slate-300">·</span>}
                        <span className="font-mono text-slate-500">{gstin}</span>
                        {period && <><span className="text-slate-300">·</span><span>Period {period}</span></>}
                    </div>
                </div>
                <div className="flex gap-2">
                    {isCritical && (
                        <button onClick={() => setShowNotice(true)}
                            className="flex items-center gap-1.5 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-xs font-bold shadow-md shadow-red-200 transition-all">
                            <Mail size={13} /> Issue SCN
                        </button>
                    )}
                    <button onClick={handleRun} disabled={running || !gstin}
                        className="flex items-center gap-1.5 text-white px-4 py-2 rounded-lg text-xs font-bold disabled:opacity-50 transition-all"
                        style={{ background: 'linear-gradient(135deg,#0f766e,#14b8a6)', boxShadow: '0 4px 12px rgba(20,184,166,0.3)' }}>
                        {running ? <RefreshCw size={13} className="animate-spin" /> : <Play size={13} />}
                        {running ? 'Running...' : 'Run Reconciliation'}
                    </button>
                    <button onClick={() => window.open(`/api/v1/audit/report?gstin=${gstin}`, '_blank')}
                        className="flex items-center gap-1.5 border border-slate-200 text-slate-600 hover:bg-slate-50 bg-white px-4 py-2 rounded-lg text-xs font-medium transition-all">
                        <Download size={13} /> Export
                    </button>
                </div>
            </div>

            {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-xs flex items-center gap-2"><AlertTriangle size={14} />{error}</div>}

            {/* ── Critical banner ──────────────────────────────────────────── */}
            {isCritical && (
                <div className="rounded-xl p-4 flex items-start gap-4 animate-fade-in"
                    style={{ background: 'linear-gradient(135deg,rgba(153,27,27,0.07),rgba(239,68,68,0.05))', border: '1.5px solid rgba(239,68,68,0.28)' }}>
                    <div className="w-10 h-10 rounded-xl gradient-red flex items-center justify-center flex-shrink-0">
                        <AlertTriangle size={20} className="text-white" />
                    </div>
                    <div className="flex-1">
                        <h3 className="text-xs font-extrabold text-red-800 uppercase tracking-widest">Critical Risk Detected</h3>
                        <p className="text-xs text-red-600 mt-0.5 leading-relaxed">
                            <strong>{entityName || gstin}</strong> — Score <strong className="text-red-700">{riskScore.toFixed(0)}%</strong> · {criticalCount} critical + {highCount} high findings · ITC at risk: <strong>{fmt(totalItcRisk)}</strong>
                        </p>
                    </div>
                    <button onClick={() => setShowNotice(true)}
                        className="flex-shrink-0 flex items-center gap-1.5 bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold hover:bg-red-700 transition-all">
                        <Mail size={12} /> Send Notice
                    </button>
                </div>
            )}

            {/* ── KPI Cards ───────────────────────────────────────────────── */}
            <div className="grid grid-cols-6 gap-3">
                {[
                    { label: 'Total Invoices', value: recon?.total_invoices ?? invoices.total_invoices ?? 0,                      icon: FileWarning,  gradient: 'gradient-blue',   sub: `${fmt(invoices.total_taxable)} taxable` },
                    { label: 'Matched',        value: recon?.matched ?? '—',                                                       icon: ShieldCheck,  gradient: 'gradient-teal',   sub: 'Clean transactions' },
                    { label: 'Fraud Cases',    value: recon ? (recon.partial_matched + recon.unmatched) : totalMismatches,          icon: AlertTriangle, gradient: 'gradient-red',   sub: `${criticalCount} critical`, trend: totalMismatches > 0 ? 'Alert' : null },
                    { label: 'ITC at Risk',    value: fmt(recon?.itc_at_risk ?? (totalItcRisk || 0)),                               icon: DollarSign,   gradient: 'gradient-amber',  sub: 'Potential fraud amount' },
                    { label: 'Active Vendors', value: vendorCount,                                                                  icon: Users,        gradient: 'gradient-purple', sub: 'In supply chain' },
                    { label: 'Risk Score',     value: `${riskScore.toFixed(0)}%`,                                                  icon: Target,       gradient: riskGradient(riskScore), sub: riskLabel.toUpperCase(), trend: riskLabel },
                ].map(p => <KpiCard key={p.label} {...p} />)}
            </div>

            {/* ── Chart Grid row 1 ─────────────────────────────────────────── */}
            <div className="grid grid-cols-12 gap-4">

                {/* Compliance ring */}
                <div className="col-span-3 card p-5">
                    <SectionHeading icon={Zap} label="Compliance Health" />
                    <div className="flex flex-col items-center">
                        <div className="relative w-28 h-28">
                            <svg viewBox="0 0 36 36" className="w-28 h-28 -rotate-90">
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none" stroke="#e2e8f0" strokeWidth="3.5" />
                                <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none" stroke={compColor} strokeWidth="3.5"
                                    strokeDasharray={`${complianceRate}, 100`} strokeLinecap="round"
                                    style={{ filter: `drop-shadow(0 0 4px ${compColor}55)` }} />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-2xl font-extrabold text-slate-800">{complianceRate.toFixed(0)}%</span>
                                <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wider">Score</span>
                            </div>
                        </div>
                        <div className="w-full mt-3 space-y-1.5">
                            {[
                                { label: 'Taxable Value', value: fmt(invoices.total_taxable) },
                                { label: 'Total Tax',     value: fmt(invoices.total_tax) },
                                { label: 'Invoices',      value: invoices.total_invoices?.toLocaleString('en-IN') || '—' },
                            ].map(({ label, value }) => (
                                <div key={label} className="flex justify-between text-xs py-1 border-b border-slate-50">
                                    <span className="text-slate-500">{label}</span>
                                    <span className="font-bold text-slate-700">{value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Severity donut */}
                <div className="col-span-3 card p-5">
                    <SectionHeading icon={AlertTriangle} label="Findings by Severity" />
                    {severityData.length > 0 ? (
                        <>
                            <ResponsiveContainer width="100%" height={155}>
                                <PieChart>
                                    <Pie data={severityData} dataKey="count" nameKey="name"
                                        cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={3} strokeWidth={0}>
                                        {severityData.map(e => <Cell key={e.name} fill={SEV_COLORS[e.name] || '#94a3b8'} />)}
                                    </Pie>
                                    <Tooltip content={<CustomTooltip />} />
                                </PieChart>
                            </ResponsiveContainer>
                            <div className="grid grid-cols-2 gap-1 mt-2">
                                {severityData.map(e => (
                                    <div key={e.name} className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-50">
                                        <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SEV_COLORS[e.name] }} />
                                        <span className="text-[10px] text-slate-600 font-medium">{e.name}</span>
                                        <span className="text-[10px] font-bold text-slate-800 ml-auto">{e.count}</span>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : <p className="text-center text-slate-400 text-xs py-16">No mismatches found</p>}
                </div>

                {/* Risk radar */}
                <div className="col-span-3 card p-5">
                    <SectionHeading icon={Target} label="Risk Profile" />
                    <ResponsiveContainer width="100%" height={175}>
                        <RadarChart outerRadius={62} data={radarData}>
                            <PolarGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                            <PolarAngleAxis dataKey="metric" tick={{ fontSize: 8, fill: '#64748b' }} />
                            <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
                            <Radar dataKey="value" stroke="#ef4444" fill="#ef4444" fillOpacity={0.15} strokeWidth={2} />
                        </RadarChart>
                    </ResponsiveContainer>
                    <div className="flex items-center gap-2 mt-1 px-1">
                        <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-700"
                                style={{ width: `${riskScore}%`, background: riskScore > 70 ? '#ef4444' : riskScore > 50 ? '#f59e0b' : riskScore > 30 ? '#6366f1' : '#14b8a6' }} />
                        </div>
                        <span className="text-xs font-bold text-slate-700">{riskScore.toFixed(0)}%</span>
                    </div>
                </div>

                {/* Fraud types */}
                <div className="col-span-3 card p-5">
                    <SectionHeading icon={Activity} label="Fraud Type Distribution" />
                    {typeData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={210}>
                            <BarChart data={typeData} layout="vertical" margin={{ left: 88, right: 8, top: 0, bottom: 0 }}>
                                <XAxis type="number" tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                                <YAxis type="category" dataKey="name" tick={{ fontSize: 8, fill: '#64748b' }} width={86} axisLine={false} tickLine={false} />
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                                <Tooltip content={<CustomTooltip />} />
                                <Bar dataKey="count" radius={[0, 5, 5, 0]} barSize={12}>
                                    {typeData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 text-xs py-16">No data</p>}
                </div>
            </div>

            {/* ── Chart Grid row 2 ─────────────────────────────────────────── */}
            <div className="grid grid-cols-12 gap-4">

                {/* Monthly trend */}
                <div className="col-span-7 card p-5">
                    <SectionHeading icon={TrendingUp} label="Monthly Mismatch Trend" />
                    {trends.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <AreaChart data={trends} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                                <defs>
                                    <linearGradient id="gradArea" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%"  stopColor="#14b8a6" stopOpacity={0.35} />
                                        <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                <XAxis dataKey="period" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                                <Tooltip content={<CustomTooltip />} />
                                <Area type="monotone" dataKey="mismatch_count" stroke="#14b8a6" fill="url(#gradArea)"
                                    strokeWidth={2.5} name="Mismatches"
                                    dot={{ r: 3, fill: '#14b8a6', strokeWidth: 0 }}
                                    activeDot={{ r: 5, fill: '#14b8a6' }} />
                            </AreaChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 text-xs py-16">No trend data — run reconciliation to populate</p>}
                </div>

                {/* Top alerts */}
                <div className="col-span-5 card p-5">
                    <SectionHeading icon={AlertTriangle} label="Top Fraud Alerts" />
                    <div className="space-y-1.5 max-h-[215px] overflow-y-auto">
                        {(summary?.top_mismatches || []).map((m, i) => (
                            <div key={i} className="flex items-start gap-2.5 p-2.5 rounded-lg border border-slate-100 hover:bg-slate-50 transition-colors">
                                <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${m.severity === 'CRITICAL' ? 'bg-red-800' : m.severity === 'HIGH' ? 'bg-red-500' : m.severity === 'MEDIUM' ? 'bg-amber-500' : 'bg-green-500'}`} />
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5 mb-0.5">
                                        <span className="text-xs font-semibold text-slate-700">{(m.type || 'Unknown').replace(/_/g, ' ')}</span>
                                        <span className={`badge ${m.severity === 'CRITICAL' ? 'badge-critical' : m.severity === 'HIGH' ? 'badge-high' : m.severity === 'MEDIUM' ? 'badge-medium' : 'badge-low'}`}>{m.severity}</span>
                                    </div>
                                    <p className="text-[10px] text-slate-500 truncate">{m.description || m.narrative?.slice(0, 80) || m.id}</p>
                                </div>
                                <span className="text-xs font-bold font-mono text-red-600 flex-shrink-0">{fmt(m.itc_risk)}</span>
                            </div>
                        ))}
                        {(!summary?.top_mismatches || summary.top_mismatches.length === 0) && (
                            <div className="text-center py-10">
                                <CheckCircle size={26} className="text-emerald-300 mx-auto mb-2" />
                                <p className="text-xs text-slate-400">Run reconciliation to detect fraud</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── Network Risk ──────────────────────────────────────────────── */}
            {summary?.risk && (
                <div className="card p-5">
                    <SectionHeading icon={Target} label="Network Risk Analysis" />
                    <div className="grid grid-cols-5 gap-3 mb-4">
                        {[
                            { label: 'Risk Score',  value: `${riskScore.toFixed(1)}%`,                    sub: riskLabel.toUpperCase(), bg: riskScore > 50 ? 'bg-red-50' : 'bg-slate-50',   color: riskScore > 50 ? 'text-red-600' : riskScore > 30 ? 'text-amber-600' : 'text-emerald-600' },
                            { label: 'PageRank',    value: summary.risk.pagerank?.toFixed(4) || 'N/A',    sub: 'Centrality',            bg: 'bg-blue-50',    color: 'text-blue-600' },
                            { label: 'Degree',      value: summary.risk.degree?.toFixed(4) || 'N/A',      sub: 'Connections',           bg: 'bg-purple-50',  color: 'text-purple-600' },
                            { label: 'Betweenness', value: summary.risk.betweenness?.toFixed(4) || 'N/A', sub: 'Bridge Score',          bg: 'bg-indigo-50',  color: 'text-indigo-600' },
                            { label: 'Community',   value: summary.risk.community ?? 'N/A',               sub: 'Cluster ID',            bg: 'bg-teal-50',    color: 'text-teal-600' },
                        ].map(({ label, value, sub, bg, color }) => (
                            <div key={label} className={`text-center p-3.5 rounded-xl ${bg}`}>
                                <p className={`text-lg font-extrabold ${color}`}>{value}</p>
                                <p className="text-xs font-semibold text-slate-600 mt-0.5">{label}</p>
                                <p className="text-[9px] text-slate-400">{sub}</p>
                            </div>
                        ))}
                    </div>
                    <div>
                        <div className="flex justify-between text-[9px] text-slate-400 mb-1 uppercase tracking-widest">
                            <span>Low</span><span>Medium</span><span>High</span><span>Critical</span>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                            <div className="h-full rounded-full transition-all duration-1000"
                                style={{
                                    width: `${riskScore}%`,
                                    background: riskScore > 70 ? 'linear-gradient(90deg,#991b1b,#ef4444)' :
                                                riskScore > 50 ? 'linear-gradient(90deg,#b45309,#f59e0b)' :
                                                riskScore > 30 ? 'linear-gradient(90deg,#4f46e5,#6366f1)' :
                                                                 'linear-gradient(90deg,#0f766e,#14b8a6)',
                                    boxShadow: `0 0 8px ${riskScore > 70 ? '#ef444466' : riskScore > 50 ? '#f59e0b66' : '#14b8a666'}`
                                }} />
                        </div>
                    </div>
                </div>
            )}

            {/* ── SCN Modal ─────────────────────────────────────────────────── */}
            {showNotice && (
                <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                    onClick={() => setShowNotice(false)}>
                    <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slide-up"
                        onClick={e => e.stopPropagation()}>
                        <div className="gradient-red text-white p-6 rounded-t-2xl">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center"><Mail size={20} /></div>
                                <div>
                                    <h2 className="text-base font-extrabold">Show Cause Notice (SCN)</h2>
                                    <p className="text-red-100 text-xs mt-0.5">Under Section 73/74 of CGST Act, 2017</p>
                                </div>
                            </div>
                        </div>
                        <div className="p-6 space-y-4 text-sm text-slate-700">
                            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                                <p className="text-[9px] font-bold text-red-500 uppercase tracking-widest mb-1">Notice To</p>
                                <p className="font-bold text-slate-800">{entityName || 'Registered Taxpayer'}</p>
                                <p className="text-slate-500 text-xs font-mono mt-0.5">GSTIN: {gstin} · Period: {period}</p>
                            </div>
                            <div>
                                <p className="font-semibold mb-1 text-sm">Subject: Discrepancies Detected in GST Returns</p>
                                <p className="text-slate-600 text-sm leading-relaxed">
                                    Automated reconciliation identified <strong className="text-red-600">{criticalCount + highCount} critical/high-risk discrepancies</strong> with risk score <strong className="text-red-600">{riskScore.toFixed(1)}%</strong>.
                                </p>
                            </div>
                            <div>
                                <p className="font-semibold mb-2 text-sm">Key Findings</p>
                                <ul className="space-y-1 text-xs text-slate-600">
                                    {[
                                        ['Total mismatches', summary?.total_mismatches || 0],
                                        ['ITC at risk', fmt(summary?.total_itc_at_risk)],
                                        ['Critical findings', criticalCount],
                                        ['High-risk findings', highCount],
                                        ['Compliance rate', `${complianceRate.toFixed(1)}%`],
                                    ].map(([k, v]) => (
                                        <li key={k} className="flex justify-between border-b border-slate-50 pb-1">
                                            <span>{k}</span><strong className={k === 'ITC at risk' ? 'text-red-600' : ''}>{v}</strong>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-800 text-xs">
                                <p className="font-bold flex items-center gap-2 mb-1"><AlertTriangle size={13} /> Action Required</p>
                                <p>You are hereby directed to furnish a reply within <strong>30 days</strong> from the date of this notice, explaining the discrepancies or pay the differential tax along with applicable interest and penalty.</p>
                            </div>
                            <div className="flex gap-3 pt-1">
                                <button onClick={() => window.print()}
                                    className="flex-1 gradient-red text-white py-2.5 rounded-xl font-bold hover:opacity-90 transition-opacity flex items-center justify-center gap-2 text-sm">
                                    <Download size={14} /> Download & Print
                                </button>
                                <button onClick={() => setShowNotice(false)}
                                    className="flex-1 bg-slate-100 text-slate-700 py-2.5 rounded-xl font-bold hover:bg-slate-200 transition-colors text-sm">
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
