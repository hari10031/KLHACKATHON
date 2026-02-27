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
const RISK_BG = { LOW: 'bg-green-50 text-green-700 border-green-200', MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200', HIGH: 'bg-red-50 text-red-600 border-red-200', CRITICAL: 'bg-red-100 text-red-800 border-red-300' }

// Normalize risk score to 0-100% — clamp strictly
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

    // Risk distribution
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
                    <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2"><Building2 size={22} className="text-blue-600" /> Vendor Risk Scorecard</h2>
                    <p className="text-sm text-slate-500 mt-0.5">{total} vendors in supply chain  |  GSTIN: <span className="font-mono font-semibold text-slate-700">{gstin}</span></p>
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
                    <div key={label} className={`${gradient} rounded-xl p-4 text-white shadow-lg card-hover`}>
                        <div className="flex items-center gap-2 mb-1">
                            <div className="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center"><Icon size={14} /></div>
                        </div>
                        <p className="text-2xl font-extrabold">{value}</p>
                        <p className="text-[11px] text-white/70 uppercase tracking-wider font-medium">{label}</p>
                    </div>
                ))}
            </div>

            {/* Charts */}
            <div className="grid grid-cols-2 gap-6">
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-3 flex items-center gap-2">
                        <Activity size={14} className="text-blue-500" /> Risk Distribution
                    </h3>
                    {pieData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={180}>
                            <PieChart>
                                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} innerRadius={40} label={({ name, value }) => `${name}: ${value}`}>
                                    {pieData.map(e => <Cell key={e.name} fill={RISK_COLORS[e.name]} />)}
                                </Pie>
                                <Tooltip />
                            </PieChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-12">No data</p>}
                </div>

                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                    <h3 className="text-sm font-semibold text-slate-600 mb-3 flex items-center gap-2">
                        <TrendingUp size={14} className="text-purple-500" /> Top 10 by Risk Score
                    </h3>
                    {vendors.length > 0 ? (
                        <ResponsiveContainer width="100%" height={180}>
                            <BarChart data={[...vendors].sort((a, b) => normalizeRisk(b.risk_score) - normalizeRisk(a.risk_score)).slice(0, 10)} layout="vertical" margin={{ left: 50, right: 10 }}>
                                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} />
                                <YAxis type="category" dataKey={d => d.name || d.entity_name || d.gstin?.slice(-6)} tick={{ fontSize: 9 }} width={45} />
                                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                                <Tooltip formatter={v => `${normalizeRisk(v).toFixed(1)}%`} />
                                <Bar dataKey="risk_score" radius={[0, 4, 4, 0]} barSize={14}>
                                    {[...vendors].sort((a, b) => normalizeRisk(b.risk_score) - normalizeRisk(a.risk_score)).slice(0, 10).map((v, i) => (
                                        <Cell key={i} fill={RISK_COLORS[getRiskLabel(v.risk_score)]} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    ) : <p className="text-center text-slate-400 py-12">No data</p>}
                </div>
            </div>

            {/* Search */}
            <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search vendors by name or GSTIN..."
                    className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-200 outline-none" />
            </div>

            {/* Vendor Table */}
            {loading ? (
                <div className="space-y-2">{[...Array(6)].map((_, i) => <div key={i} className="h-14 shimmer rounded-lg" />)}</div>
            ) : (
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-slate-50 border-b border-slate-200">
                                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Vendor</th>
                                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">GSTIN</th>
                                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Risk Score</th>
                                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Level</th>
                                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">PageRank</th>
                                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Community</th>
                                <th className="text-center px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {filtered.map(v => {
                                const rl = getRiskLabel(v.risk_score)
                                return (
                                    <tr key={v.gstin} className="hover:bg-slate-50 transition-colors">
                                        <td className="px-4 py-3">
                                            <span className="font-semibold text-slate-800">{v.name || v.entity_name || 'Unknown'}</span>
                                        </td>
                                        <td className="px-4 py-3">
                                            <span className="font-mono text-xs text-slate-500">{v.gstin}</span>
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            <div className="flex items-center justify-center gap-2">
                                                <div className="w-16 bg-slate-200 rounded-full h-1.5">
                                                    <div className="h-full rounded-full transition-all" style={{ width: `${normalizeRisk(v.risk_score)}%`, backgroundColor: RISK_COLORS[rl] }} />
                                                </div>
                                                <span className="text-xs font-bold" style={{ color: RISK_COLORS[rl] }}>{normalizeRisk(v.risk_score).toFixed(0)}%</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${RISK_BG[rl]}`}>{rl}</span>
                                        </td>
                                        <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">{v.pagerank?.toFixed(4) || '—'}</td>
                                        <td className="px-4 py-3 text-right text-xs text-slate-500 font-mono">{v.community ?? '—'}</td>
                                        <td className="px-4 py-3 text-center">
                                            <button onClick={() => openDetail(v.gstin)}
                                                className="text-blue-500 hover:text-blue-700 p-1 rounded-md hover:bg-blue-50 transition-all">
                                                <ExternalLink size={14} />
                                            </button>
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>

                    {filtered.length === 0 && (
                        <div className="text-center py-12">
                            <Users size={32} className="text-slate-300 mx-auto mb-3" />
                            <p className="text-sm text-slate-400">No vendors found</p>
                        </div>
                    )}
                </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between pt-1">
                    <p className="text-xs text-slate-500">Page {page} of {totalPages} ({total} vendors)</p>
                    <div className="flex items-center gap-1">
                        <button onClick={() => setPage(1)} disabled={page === 1} className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-30"><ChevronsLeft size={14} /></button>
                        {[...Array(Math.min(5, totalPages))].map((_, i) => {
                            const pg = page <= 3 ? i + 1 : page + i - 2
                            if (pg < 1 || pg > totalPages) return null
                            return <button key={pg} onClick={() => setPage(pg)} className={`w-8 h-8 rounded-lg text-xs font-medium ${pg === page ? 'bg-blue-600 text-white' : 'hover:bg-slate-100'}`}>{pg}</button>
                        })}
                        <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-30"><ChevronsRight size={14} /></button>
                    </div>
                </div>
            )}

            {/* Detail Modal */}
            {selectedVendor && (
                <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 animate-fade-in" onClick={() => { setSelectedVendor(null); setVendorDetail(null) }}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-y-auto animate-slide-in" onClick={e => e.stopPropagation()}>
                        <div className="p-6 border-b border-slate-200 flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-bold text-slate-800">Vendor Risk Profile</h3>
                                <p className="text-xs font-mono text-slate-500 mt-0.5">{selectedVendor}</p>
                            </div>
                            <button onClick={() => { setSelectedVendor(null); setVendorDetail(null) }} className="text-slate-400 hover:text-slate-600 p-1">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="p-6">
                            {detailLoading ? (
                                <div className="space-y-3">{[...Array(4)].map((_, i) => <div key={i} className="h-10 shimmer rounded-lg" />)}</div>
                            ) : vendorDetail ? (
                                <div className="space-y-4">
                                    <div className="flex items-center gap-4">
                                        <div className={`w-16 h-16 rounded-xl flex items-center justify-center text-white font-bold text-xl ${normalizeRisk(vendorDetail.risk_score) > 50 ? 'gradient-red' : normalizeRisk(vendorDetail.risk_score) > 30 ? 'gradient-amber' : 'gradient-green'}`}>
                                            {normalizeRisk(vendorDetail.risk_score).toFixed(0)}%
                                        </div>
                                        <div>
                                            <p className="font-semibold text-slate-800">{vendorDetail.entity_name || 'Unknown Entity'}</p>
                                            <p className="text-xs text-slate-500">Risk Level: <span className="font-bold">{getRiskLabel(vendorDetail.risk_score)}</span></p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3 text-sm">
                                        {[
                                            { label: 'PageRank', value: vendorDetail.pagerank?.toFixed(6) },
                                            { label: 'Degree Centrality', value: vendorDetail.degree?.toFixed(6) },
                                            { label: 'Betweenness', value: vendorDetail.betweenness?.toFixed(6) },
                                            { label: 'Community', value: vendorDetail.community },
                                            { label: 'Invoice Count', value: vendorDetail.invoice_count },
                                            { label: 'Total Value', value: fmt(vendorDetail.total_value) },
                                        ].map(({ label, value }) => (
                                            <div key={label} className="bg-slate-50 rounded-lg p-3">
                                                <p className="text-slate-400 text-[10px] uppercase tracking-wider">{label}</p>
                                                <p className="font-bold text-slate-700 mt-0.5">{value ?? '—'}</p>
                                            </div>
                                        ))}
                                    </div>

                                    {vendorDetail.risk_factors && vendorDetail.risk_factors.length > 0 && (
                                        <div>
                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><Zap size={12} /> Risk Factors</h4>
                                            <div className="space-y-1.5">
                                                {vendorDetail.risk_factors.map((f, i) => (
                                                    <div key={i} className="flex items-center gap-2 text-xs bg-red-50 rounded-lg p-2">
                                                        <AlertTriangle size={12} className="text-red-500 flex-shrink-0" />
                                                        <span className="text-red-700">{f}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {vendorDetail.connections && vendorDetail.connections.length > 0 && (
                                        <div>
                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2">Connected Entities</h4>
                                            <div className="space-y-1">
                                                {vendorDetail.connections.slice(0, 8).map((c, i) => (
                                                    <div key={i} className="flex items-center justify-between text-xs bg-slate-50 rounded-lg p-2">
                                                        <span className="font-mono text-slate-600">{c.gstin || c.entity}</span>
                                                        <span className="text-slate-400">{c.relationship || c.type}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <p className="text-sm text-slate-400 text-center py-8">No detailed risk data available</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
