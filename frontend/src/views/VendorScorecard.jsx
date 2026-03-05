import React, { useState, useEffect, useCallback } from 'react'
import { getVendorScorecard, getVendorRisk } from '../api'
import {
    PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import {
    Users, AlertTriangle, Shield, TrendingUp, ChevronRight, X, Search,
    ChevronsLeft, ChevronsRight, ExternalLink, Activity, Target, Zap, Building2
} from 'lucide-react'

const RISK_COLORS = { LOW: '#22c55e', MEDIUM: '#f59e0b', HIGH: '#ef4444', CRITICAL: '#991b1b' }

const normalizeRisk = (score) => {
    if (score == null) return 0
    const s = Number(score)
    if (isNaN(s)) return 0
    return Math.min(100, Math.max(0, s))
}

function getRiskLabel(score) {
    if (score == null) return 'UNKNOWN'
    const s = normalizeRisk(score)
    if (s > 70) return 'CRITICAL'
    if (s > 50) return 'HIGH'
    if (s > 30) return 'MEDIUM'
    return 'LOW'
}

const BADGE_CLASS = {
    LOW: 'badge badge-low',
    MEDIUM: 'badge badge-medium',
    HIGH: 'badge badge-high',
    CRITICAL: 'badge badge-critical',
    UNKNOWN: 'badge badge-low',
}

const fmt = v => {
    if (v == null) return '—'
    if (typeof v === 'number') {
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
        if (v >= 100000) return `₹${(v / 100000).toFixed(2)} L`
        if (v >= 1000) return `₹${v.toLocaleString('en-IN')}`
        return `₹${v}`
    }
    return v
}

const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    return (
        <div className="bg-slate-900 text-white text-xs px-3 py-2 rounded-lg shadow-xl border border-slate-700">
            <p className="font-semibold">{payload[0].name}</p>
            <p className="text-slate-300">{payload[0].value} vendors</p>
        </div>
    )
}

export default function VendorScorecard({ gstin }) {
    const [vendors, setVendors] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [page, setPage] = useState(1)
    const [search, setSearch] = useState('')
    const [selectedVendor, setSelectedVendor] = useState(null)
    const [vendorDetail, setVendorDetail] = useState(null)
    const [detailLoading, setDetailLoading] = useState(false)

    const pageSize = 12

    const load = useCallback(() => {
        if (!gstin) return
        setLoading(true)
        getVendorScorecard(gstin, page)
            .then(r => {
                setVendors(r.data.vendors || [])
                setTotal(r.data.total || 0)
            })
            .catch(() => { })
            .finally(() => setLoading(false))
    }, [gstin, page])

    useEffect(() => { load() }, [load])

    const openDetail = async (vendorGstin) => {
        setSelectedVendor(vendorGstin)
        setDetailLoading(true)
        try {
            const r = await getVendorRisk(vendorGstin)
            setVendorDetail(r.data)
        } catch { setVendorDetail(null) }
        setDetailLoading(false)
    }

    const totalPages = Math.ceil(total / pageSize)

    const riskDist = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 }
    vendors.forEach(v => { const l = getRiskLabel(v.risk_score); riskDist[l]++ })
    const pieData = Object.entries(riskDist).filter(([, v]) => v > 0).map(([k, v]) => ({ name: k, value: v }))

    const filtered = search ? vendors.filter(v =>
        (v.gstin || '').toLowerCase().includes(search.toLowerCase()) ||
        (v.name || v.entity_name || '').toLowerCase().includes(search.toLowerCase())
    ) : vendors

    const highRisk = vendors.filter(v => normalizeRisk(v.risk_score) > 50).length
    const avgScore = vendors.length ? vendors.reduce((s, v) => s + normalizeRisk(v.risk_score), 0) / vendors.length : 0

    return (
        <div className="space-y-5 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                        <Building2 size={20} className="text-teal-600" />
                        Vendor Risk Scorecard
                    </h2>
                    <p className="text-sm text-slate-500 mt-0.5">
                        {total} vendors in supply chain &nbsp;·&nbsp;
                        GSTIN: <span className="font-mono font-semibold text-slate-700">{gstin}</span>
                    </p>
                </div>
            </div>

            {/* KPI row */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: 'Total Vendors', value: total, icon: Users, gradient: 'gradient-blue' },
                    { label: 'High Risk', value: highRisk, icon: AlertTriangle, gradient: 'gradient-red' },
                    { label: 'Average Risk', value: `${avgScore.toFixed(0)}%`, icon: Target, gradient: 'gradient-amber' },
                    { label: 'Compliant', value: total - highRisk, icon: Shield, gradient: 'gradient-green' },
                ].map(({ label, value, icon: Icon, gradient }) => (
                    <div key={label} className={`kpi-card ${gradient}`}>
                        <div className="w-8 h-8 rounded-lg bg-white/15 flex items-center justify-center mb-2">
                            <Icon size={16} />
                        </div>
                        <p className="text-2xl font-extrabold leading-none">{value}</p>
                        <p className="text-[11px] text-white/70 uppercase tracking-wider font-medium mt-1">{label}</p>
                    </div>
                ))}
            </div>

            {/* Charts */}
            <div className="grid grid-cols-2 gap-5">
                <div className="card p-5">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                        <Activity size={13} className="text-teal-500" /> Risk Distribution
                    </p>
                    {pieData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={180}>
                            <PieChart>
                                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={72} innerRadius={40}
                                    label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                                    {pieData.map(e => <Cell key={e.name} fill={RISK_COLORS[e.name]} />)}
                                </Pie>
                                <Tooltip content={<CustomTooltip />} />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-12 text-sm">No data available</p>}
                </div>

                <div className="card p-5">
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                        <TrendingUp size={13} className="text-purple-500" /> Top 10 by Risk Score
                    </p>
                    {vendors.length > 0 ? (
                        <ResponsiveContainer width="100%" height={180}>
                            <BarChart
                                data={[...vendors].sort((a, b) => normalizeRisk(b.risk_score) - normalizeRisk(a.risk_score)).slice(0, 10)}
                                layout="vertical" margin={{ left: 50, right: 10 }}>
                                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                                <YAxis type="category" dataKey={d => d.name || d.entity_name || d.gstin?.slice(-6)} tick={{ fontSize: 9, fill: '#64748b' }} width={45} axisLine={false} tickLine={false} />
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                                <Tooltip content={({ active, payload }) => active && payload?.length ? (
                                    <div className="bg-slate-900 text-white text-xs px-3 py-2 rounded-lg shadow-xl">
                                        <p className="font-mono">{normalizeRisk(payload[0].value).toFixed(1)}% risk</p>
                                    </div>
                                ) : null} />
                                <Bar dataKey="risk_score" radius={[0, 4, 4, 0]} barSize={13}>
                                    {[...vendors].sort((a, b) => normalizeRisk(b.risk_score) - normalizeRisk(a.risk_score)).slice(0, 10).map((v, i) => (
                                        <Cell key={i} fill={RISK_COLORS[getRiskLabel(v.risk_score)]} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-12 text-sm">No data available</p>}
                </div>
            </div>

            {/* Search */}
            <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={search} onChange={e => setSearch(e.target.value)}
                    placeholder="Search vendors by name or GSTIN..."
                    className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-teal-200 outline-none shadow-sm" />
            </div>

            {/* Vendor Table */}
            {loading ? (
                <div className="space-y-2">{[...Array(6)].map((_, i) => <div key={i} className="h-14 shimmer rounded-xl" />)}</div>
            ) : (
                <div className="card overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200">
                                {['Vendor', 'GSTIN', 'Risk Score', 'Level', 'PageRank', 'Community', ''].map(h => (
                                    <th key={h} className="px-4 py-3 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filtered.map(v => {
                                const rl = getRiskLabel(v.risk_score)
                                return (
                                    <tr key={v.gstin} className="hover:bg-slate-50/60 transition-colors">
                                        <td className="px-4 py-3">
                                            <span className="font-semibold text-slate-800 text-sm">{v.name || v.entity_name || 'Unknown'}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="font-mono text-xs text-slate-500">{v.gstin}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-2">
                                                <div className="w-16 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                                                    <div className="h-full rounded-full transition-all" style={{ width: `${normalizeRisk(v.risk_score)}%`, backgroundColor: RISK_COLORS[rl] }} />
                                                </div>
                                                <span className="text-xs font-bold font-mono" style={{ color: RISK_COLORS[rl] }}>{normalizeRisk(v.risk_score).toFixed(0)}%</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className={BADGE_CLASS[rl]}>{rl}</span>
                                        </td>
                                        <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">{v.pagerank?.toFixed(4) || '—'}</td>
                                        <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">{v.community ?? '—'}</td>
                                        <td className="px-4 py-3 text-center">
                                            <button onClick={() => openDetail(v.gstin)}
                                                className="text-teal-500 hover:text-teal-700 p-1.5 rounded-lg hover:bg-teal-50 transition-all">
                                                <ExternalLink size={14} />
                                            </button>
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>

                    {filtered.length === 0 && (
                        <div className="text-center py-14">
                            <Users size={32} className="text-slate-200 mx-auto mb-3" />
                            <p className="text-sm text-slate-400">No vendors found</p>
                        </div>
                    )}
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between">
                    <p className="text-xs text-slate-500">Page {page} of {totalPages} &nbsp;·&nbsp; {total} vendors total</p>
                    <div className="flex items-center gap-1">
                        <button onClick={() => setPage(1)} disabled={page === 1}
                            className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition-colors text-slate-500">
                            <ChevronsLeft size={14} />
                        </button>
                        {[...Array(Math.min(5, totalPages))].map((_, i) => {
                            const pg = page <= 3 ? i + 1 : page + i - 2
                            if (pg < 1 || pg > totalPages) return null
                            return (
                                <button key={pg} onClick={() => setPage(pg)}
                                    className={`w-8 h-8 rounded-lg text-xs font-semibold transition-all ${pg === page ? 'bg-teal-600 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100'}`}>
                                    {pg}
                                </button>
                            )
                        })}
                        <button onClick={() => setPage(totalPages)} disabled={page === totalPages}
                            className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition-colors text-slate-500">
                            <ChevronsRight size={14} />
                        </button>
                    </div>
                </div>
            )}

            {/* Detail Modal */}
            {selectedVendor && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in p-4"
                    onClick={() => { setSelectedVendor(null); setVendorDetail(null) }}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto animate-slide-up"
                        onClick={e => e.stopPropagation()}>
                        {/* Modal Header */}
                        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                            <div>
                                <h3 className="text-base font-bold text-slate-800">Vendor Risk Profile</h3>
                                <p className="text-xs font-mono text-teal-600 mt-0.5">{selectedVendor}</p>
                            </div>
                            <button onClick={() => { setSelectedVendor(null); setVendorDetail(null) }}
                                className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 transition-colors">
                                <X size={18} />
                            </button>
                        </div>
                        <div className="p-5">
                            {detailLoading ? (
                                <div className="space-y-3">{[...Array(4)].map((_, i) => <div key={i} className="h-10 shimmer rounded-lg" />)}</div>
                            ) : vendorDetail ? (
                                <div className="space-y-5">
                                    <div className="flex items-center gap-4">
                                        <div className={`w-16 h-16 rounded-xl flex items-center justify-center text-white font-bold text-lg ${normalizeRisk(vendorDetail.risk_score) > 70 ? 'gradient-red' : normalizeRisk(vendorDetail.risk_score) > 50 ? 'gradient-amber' : normalizeRisk(vendorDetail.risk_score) > 30 ? 'gradient-indigo' : 'gradient-green'}`}>
                                            {normalizeRisk(vendorDetail.risk_score).toFixed(0)}%
                                        </div>
                                        <div>
                                            <p className="font-bold text-slate-800">{vendorDetail.entity_name || 'Unknown Entity'}</p>
                                            <p className="text-xs text-slate-500 mt-0.5">Risk Level: &nbsp;
                                                <span className={BADGE_CLASS[getRiskLabel(vendorDetail.risk_score)]}>
                                                    {getRiskLabel(vendorDetail.risk_score)}
                                                </span>
                                            </p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-2.5 text-sm">
                                        {[
                                            { label: 'PageRank', value: vendorDetail.pagerank?.toFixed(6) },
                                            { label: 'Degree Centrality', value: vendorDetail.degree?.toFixed(6) },
                                            { label: 'Betweenness', value: vendorDetail.betweenness?.toFixed(6) },
                                            { label: 'Community', value: vendorDetail.community },
                                            { label: 'Invoice Count', value: vendorDetail.invoice_count },
                                            { label: 'Total Value', value: fmt(vendorDetail.total_value) },
                                        ].map(({ label, value }) => (
                                            <div key={label} className="bg-slate-50 rounded-xl p-3 border border-slate-100">
                                                <p className="text-slate-400 text-[10px] uppercase tracking-wider">{label}</p>
                                                <p className="font-bold text-slate-700 mt-0.5 font-mono text-sm">{value ?? '—'}</p>
                                            </div>
                                        ))}
                                    </div>

                                    {vendorDetail.risk_factors?.length > 0 && (
                                        <div>
                                            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1">
                                                <Zap size={11} className="text-amber-500" /> Risk Factors
                                            </p>
                                            <div className="space-y-1.5">
                                                {vendorDetail.risk_factors.map((f, i) => (
                                                    <div key={i} className="flex items-start gap-2 text-xs bg-red-50 rounded-lg p-2.5 border border-red-100">
                                                        <AlertTriangle size={12} className="text-red-500 flex-shrink-0 mt-0.5" />
                                                        <span className="text-red-700 leading-relaxed">{f}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {vendorDetail.connections?.length > 0 && (
                                        <div>
                                            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">Connected Entities</p>
                                            <div className="space-y-1">
                                                {vendorDetail.connections.slice(0, 8).map((c, i) => (
                                                    <div key={i} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg p-2.5 border border-slate-100">
                                                        <span className="font-mono text-teal-700">{c.gstin || c.entity}</span>
                                                        <span className="text-slate-400 text-[10px]">{c.relationship || c.type}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-400 text-center py-10">No detailed risk data available</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
