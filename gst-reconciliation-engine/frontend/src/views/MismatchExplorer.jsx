import React, { useState, useEffect, useCallback } from 'react'
import { getMismatches, getTraversalPath } from '../api'
import {
    Search, Filter, X, ChevronDown, ChevronRight, ChevronsLeft, ChevronsRight,
    AlertTriangle, AlertCircle, Info, CheckCircle, ExternalLink, ArrowRight,
    FileText, DollarSign, Eye, Shield, Building2, Users, TrendingUp, Zap
} from 'lucide-react'

const sevConfig = {
    CRITICAL: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200', dot: 'bg-red-600', icon: AlertTriangle },
    HIGH: { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-100', dot: 'bg-red-500', icon: AlertCircle },
    MEDIUM: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-100', dot: 'bg-amber-500', icon: Info },
    LOW: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-100', dot: 'bg-green-500', icon: CheckCircle },
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

// Normalize risk score to 0-100% — clamp strictly
const normalizeRisk = (score) => {
    if (score == null) return null
    const s = Number(score)
    if (isNaN(s)) return null
    return Math.min(100, Math.max(0, s))
}

export default function MismatchExplorer({ gstin, period }) {
    const [mismatches, setMismatches] = useState([])
    const [total, setTotal] = useState(0)
    const [sevCounts, setSevCounts] = useState({})
    const [allTypes, setAllTypes] = useState([])
    const [loading, setLoading] = useState(true)
    const [page, setPage] = useState(1)
    const [pageSize] = useState(15)
    const [search, setSearch] = useState('')
    const [sevFilter, setSevFilter] = useState('')
    const [typeFilter, setTypeFilter] = useState('')
    const [expanded, setExpanded] = useState(null)
    const [traversal, setTraversal] = useState(null)
    const [tLoading, setTLoading] = useState(false)
    const [error, setError] = useState(null)

    const load = useCallback(() => {
        if (!gstin) return
        setLoading(true); setError(null)
        getMismatches(gstin, '', {
            severity: sevFilter, mismatch_type: typeFilter, page, page_size: pageSize
        })
            .then(r => {
                setMismatches(r.data.mismatches || [])
                setTotal(r.data.total || 0)
                if (r.data.severity_counts) setSevCounts(r.data.severity_counts)
                if (r.data.all_types) setAllTypes(r.data.all_types)
            })
            .catch(e => setError(e.response?.data?.detail || 'Failed to load mismatches'))
            .finally(() => setLoading(false))
    }, [gstin, sevFilter, typeFilter, page, pageSize])

    useEffect(() => { load() }, [load])
    useEffect(() => { setPage(1) }, [sevFilter, typeFilter, search])

    const loadTraversal = async (id) => {
        setTLoading(true)
        try {
            const r = await getTraversalPath(id)
            const d = r.data
            const path = []
            if (d.mismatch) path.push({ type: 'Mismatch', label: d.mismatch.mismatch_id || 'Mismatch' })
            if (d.invoice) path.push({ type: 'Invoice', label: d.invoice.invoice_number || 'Invoice' })
            if (d.seller?.gstin_number) path.push({ type: 'GSTIN', label: d.seller.gstin_number })
            if (d.buyer?.gstin_number) path.push({ type: 'GSTIN', label: d.buyer.gstin_number })
            if (d.irn) path.push({ type: 'IRN', label: d.irn.irn_number || 'IRN' })
            if (d.return_filed) path.push({ type: 'Return', label: d.return_filed.return_type || 'Return' })
            setTraversal({ path, seller_name: d.seller?.name, buyer_name: d.buyer?.name })
        } catch { setTraversal(null) }
        setTLoading(false)
    }

    const toggleExpand = (m) => {
        if (expanded === m.id) { setExpanded(null); setTraversal(null) }
        else { setExpanded(m.id); loadTraversal(m.id) }
    }

    const totalPages = Math.ceil(total / pageSize)

    const filteredMismatches = search
        ? mismatches.filter(m =>
            (m.description || '').toLowerCase().includes(search.toLowerCase()) ||
            (m.id || '').toLowerCase().includes(search.toLowerCase()) ||
            (m.type || '').toLowerCase().includes(search.toLowerCase()) ||
            (m.narrative || '').toLowerCase().includes(search.toLowerCase())
        )
        : mismatches

    return (
        <div className="space-y-5 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2"><Zap size={22} className="text-blue-600" /> Fraud Case Explorer</h2>
                    <p className="text-sm text-slate-500 mt-0.5">
                        {total} findings detected  |  GSTIN: <span className="font-mono font-semibold text-slate-700">{gstin}</span>
                    </p>
                </div>
                <button onClick={load} className="flex items-center gap-2 border border-slate-300 text-slate-600 hover:bg-slate-50 px-4 py-2 rounded-lg text-sm font-medium transition-all">
                    <Filter size={14} /> Refresh
                </button>
            </div>

            {/* Quick Stats */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: 'Total Cases', value: total, icon: FileText, color: 'text-blue-600', bg: 'bg-blue-50' },
                    { label: 'Critical', value: sevCounts.CRITICAL || 0, icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' },
                    { label: 'High Risk', value: sevCounts.HIGH || 0, icon: AlertCircle, color: 'text-orange-600', bg: 'bg-orange-50' },
                    { label: 'Types Found', value: allTypes.length, icon: TrendingUp, color: 'text-purple-600', bg: 'bg-purple-50' },
                ].map(({ label, value, icon: Icon, color, bg }) => (
                    <div key={label} className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-lg ${bg} flex items-center justify-center`}>
                            <Icon size={18} className={color} />
                        </div>
                        <div>
                            <p className={`text-xl font-bold ${color}`}>{value}</p>
                            <p className="text-[11px] text-slate-500">{label}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Summary Pills */}
            <div className="flex gap-3">
                {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => {
                    const sc = sevConfig[sev]
                    const cnt = sevCounts[sev] || 0
                    return (
                        <button key={sev} onClick={() => setSevFilter(sevFilter === sev ? '' : sev)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-full text-xs font-bold border transition-all ${sevFilter === sev ? `${sc.bg} ${sc.text} ${sc.border} ring-2 ring-offset-1 ring-${sev === 'CRITICAL' ? 'red' : sev === 'HIGH' ? 'red' : sev === 'MEDIUM' ? 'amber' : 'green'}-300` : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}>
                            <span className={`w-2 h-2 rounded-full ${sc.dot}`} />
                            {sev} ({cnt})
                        </button>
                    )
                })}
                {(sevFilter || typeFilter) && (
                    <button onClick={() => { setSevFilter(''); setTypeFilter('') }}
                        className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1">
                        <X size={12} /> Clear filters
                    </button>
                )}
            </div>

            {/* Search + Type Filter */}
            <div className="flex gap-3">
                <div className="relative flex-1">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search mismatches..."
                        className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-400 outline-none" />
                </div>
                <div className="relative">
                    <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
                        className="appearance-none bg-white border border-slate-200 rounded-lg px-4 py-2.5 pr-8 text-sm text-slate-600 cursor-pointer focus:ring-2 focus:ring-blue-200">
                        <option value="">All Types</option>
                        {allTypes.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                    </select>
                    <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
            </div>

            {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-center gap-2"><AlertTriangle size={16} />{error}</div>}

            {/* Loading */}
            {loading ? (
                <div className="space-y-3">
                    {[...Array(5)].map((_, i) => <div key={i} className="h-20 shimmer rounded-xl" />)}
                </div>
            ) : (
                <>
                    {/* Mismatch Cards */}
                    <div className="space-y-2">
                        {filteredMismatches.map(m => {
                            const sc = sevConfig[m.severity] || sevConfig.MEDIUM
                            const SIcon = sc.icon
                            const isOpen = expanded === m.id
                            return (
                                <div key={m.id} className={`bg-white rounded-xl border transition-all ${isOpen ? `${sc.border} shadow-md` : 'border-slate-200 hover:border-slate-300 shadow-sm'}`}>
                                    {/* Card Header */}
                                    <div className="flex items-center gap-4 p-4 cursor-pointer" onClick={() => toggleExpand(m)}>
                                        <div className={`w-10 h-10 rounded-lg ${sc.bg} flex items-center justify-center flex-shrink-0`}>
                                            <SIcon size={18} className={sc.text} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <span className="text-sm font-semibold text-slate-800">{(m.type || 'Unknown').replace(/_/g, ' ')}</span>
                                                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${sc.bg} ${sc.text}`}>{m.severity}</span>
                                            </div>
                                            <p className="text-xs text-slate-500 truncate">{m.description || m.narrative?.slice(0, 120) || m.id}</p>
                                            {(m.seller_name || m.buyer_name) && (
                                                <div className="flex items-center gap-3 mt-1 text-[10px] text-slate-400">
                                                    {m.seller_name && <span className="flex items-center gap-1"><Building2 size={10} className="text-blue-400" />{m.seller_name}</span>}
                                                    {m.seller_name && m.buyer_name && <ArrowRight size={8} />}
                                                    {m.buyer_name && <span className="flex items-center gap-1"><Building2 size={10} className="text-green-400" />{m.buyer_name}</span>}
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-4 flex-shrink-0">
                                            <div className="text-right">
                                                <p className="text-sm font-bold text-red-600">{fmt(m.itc_risk || m.tax_difference)}</p>
                                                <p className="text-[10px] text-slate-400">ITC at Risk</p>
                                            </div>
                                            {m.risk_score != null && (
                                                <div className="text-right">
                                                    <p className="text-sm font-bold text-slate-700">{normalizeRisk(m.risk_score)?.toFixed(0) ?? '—'}%</p>
                                                    <p className="text-[10px] text-slate-400">Risk</p>
                                                </div>
                                            )}
                                            <ChevronRight size={16} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                                        </div>
                                    </div>

                                    {/* Expanded Details */}
                                    {isOpen && (
                                        <div className="border-t border-slate-100 p-4 animate-fade-in">
                                            <div className="grid grid-cols-2 gap-6">
                                                {/* Left: Details */}
                                                <div className="space-y-4">
                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><FileText size={12} /> Fraud Narrative</h4>
                                                        <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-lg p-3">
                                                            {m.narrative || m.description || 'No narrative available'}
                                                        </p>
                                                    </div>
                                                    {m.evidence_path && (
                                                        <div>
                                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><Eye size={12} /> Evidence Chain</h4>
                                                            <pre className="text-xs text-slate-600 bg-slate-50 rounded-lg p-3 whitespace-pre-wrap font-mono">{m.evidence_path}</pre>
                                                        </div>
                                                    )}
                                                    {m.resolution_actions && (
                                                        <div>
                                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><Shield size={12} /> Resolution Actions</h4>
                                                            <p className="text-sm text-slate-600 bg-blue-50 rounded-lg p-3">{m.resolution_actions}</p>
                                                        </div>
                                                    )}
                                                    {m.regulatory_ref && (
                                                        <div>
                                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><ExternalLink size={12} /> Regulatory Reference</h4>
                                                            <p className="text-xs text-blue-600 bg-blue-50 rounded-lg p-2 font-medium">{m.regulatory_ref}</p>
                                                        </div>
                                                    )}
                                                </div>

                                                {/* Right: Properties + Traversal */}
                                                <div className="space-y-4">
                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><DollarSign size={12} /> Financial Details</h4>
                                                        <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-xs">
                                                            {m.invoice_value != null && <div className="flex justify-between"><span className="text-slate-500">Invoice Value</span><span className="font-bold">{fmt(m.invoice_value)}</span></div>}
                                                            {m.tax_difference != null && <div className="flex justify-between"><span className="text-slate-500">Tax Difference</span><span className="font-bold text-red-600">{fmt(m.tax_difference)}</span></div>}
                                                            {m.itc_risk != null && <div className="flex justify-between"><span className="text-slate-500">ITC at Risk</span><span className="font-bold text-red-600">{fmt(m.itc_risk)}</span></div>}
                                                            {m.buyer_gstin && <div className="flex justify-between"><span className="text-slate-500">Buyer</span><span className="font-mono text-slate-700">{m.buyer_gstin}{m.buyer_name ? ` (${m.buyer_name})` : ''}</span></div>}
                                                            {m.seller_gstin && <div className="flex justify-between"><span className="text-slate-500">Seller</span><span className="font-mono text-slate-700">{m.seller_gstin}{m.seller_name ? ` (${m.seller_name})` : ''}</span></div>}
                                                            {m.return_period && <div className="flex justify-between"><span className="text-slate-500">Period</span><span className="font-mono text-slate-700">{m.return_period}</span></div>}
                                                        </div>
                                                    </div>

                                                    {/* Traversal Path */}
                                                    <div>
                                                        <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1"><ArrowRight size={12} /> Graph Traversal</h4>
                                                        {tLoading ? (
                                                            <div className="shimmer h-24 rounded-lg" />
                                                        ) : traversal?.path ? (
                                                            <div className="bg-slate-50 rounded-lg p-3">
                                                                <div className="flex flex-wrap items-center gap-1">
                                                                    {traversal.path.map((node, i) => (
                                                                        <React.Fragment key={i}>
                                                                            <span className={`text-[10px] px-2 py-1 rounded font-medium ${node.type === 'Mismatch' ? 'bg-red-100 text-red-700' : node.type === 'GSTIN' ? 'bg-blue-100 text-blue-700' : node.type === 'Invoice' ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'}`}>
                                                                                {node.label || node.id}
                                                                            </span>
                                                                            {i < traversal.path.length - 1 && (
                                                                                <ArrowRight size={10} className="text-slate-300" />
                                                                            )}
                                                                        </React.Fragment>
                                                                    ))}
                                                                </div>
                                                                {traversal.seller_name && (
                                                                    <p className="text-[10px] text-slate-500 mt-2">Seller: <span className="font-semibold text-slate-700">{traversal.seller_name}</span></p>
                                                                )}
                                                                {traversal.buyer_name && (
                                                                    <p className="text-[10px] text-slate-500">Buyer: <span className="font-semibold text-slate-700">{traversal.buyer_name}</span></p>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <p className="text-xs text-slate-400 italic bg-slate-50 rounded-lg p-3">No traversal data</p>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>

                    {filteredMismatches.length === 0 && !loading && (
                        <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
                            <AlertCircle size={40} className="text-slate-300 mx-auto mb-4" />
                            <h3 className="text-lg font-semibold text-slate-600">No Mismatches Found</h3>
                            <p className="text-sm text-slate-400 mt-1">Run reconciliation from the Dashboard to detect GST fraud</p>
                        </div>
                    )}

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-between pt-2">
                            <p className="text-xs text-slate-500">
                                Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}
                            </p>
                            <div className="flex items-center gap-1">
                                <button onClick={() => setPage(1)} disabled={page === 1}
                                    className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition-colors">
                                    <ChevronsLeft size={14} />
                                </button>
                                {[...Array(Math.min(5, totalPages))].map((_, i) => {
                                    const pg = page <= 3 ? i + 1 : page + i - 2
                                    if (pg < 1 || pg > totalPages) return null
                                    return (
                                        <button key={pg} onClick={() => setPage(pg)}
                                            className={`w-8 h-8 rounded-lg text-xs font-medium transition-all ${pg === page ? 'bg-blue-600 text-white shadow-sm' : 'hover:bg-slate-100 text-slate-600'}`}>
                                            {pg}
                                        </button>
                                    )
                                })}
                                <button onClick={() => setPage(totalPages)} disabled={page === totalPages}
                                    className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-30 transition-colors">
                                    <ChevronsRight size={14} />
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
