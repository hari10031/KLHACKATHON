import React, { useState, useEffect, useCallback } from 'react'
import { getMismatches, getTraversalPath } from '../api'
import {
    Search, Filter, X, ChevronDown, ChevronRight, ChevronsLeft, ChevronsRight,
    AlertTriangle, AlertCircle, Info, CheckCircle, ExternalLink, ArrowRight,
    FileText, DollarSign, Eye, Shield, Building2, TrendingUp, Zap
} from 'lucide-react'

const sevConfig = {
    CRITICAL: { bg: 'bg-red-50',     text: 'text-red-700',    border: 'border-red-200',    dot: 'bg-red-700',    icon: AlertTriangle, badge: 'badge-critical' },
    HIGH:     { bg: 'bg-red-50',     text: 'text-red-600',    border: 'border-red-100',    dot: 'bg-red-500',    icon: AlertCircle,   badge: 'badge-high' },
    MEDIUM:   { bg: 'bg-amber-50',   text: 'text-amber-700',  border: 'border-amber-200',  dot: 'bg-amber-500',  icon: Info,          badge: 'badge-medium' },
    LOW:      { bg: 'bg-emerald-50', text: 'text-emerald-700',border: 'border-emerald-200',dot: 'bg-emerald-500',icon: CheckCircle,   badge: 'badge-low' },
}

const fmt = v => {
    if (v == null) return '—'
    if (typeof v === 'number') {
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(2)} Cr`
        if (v >= 100000)   return `₹${(v / 100000).toFixed(2)} L`
        if (v >= 1000)     return `₹${v.toLocaleString('en-IN')}`
        return `₹${v}`
    }
    return v
}
const normalizeRisk = s => { if (s == null) return null; const n = Number(s); return isNaN(n) ? null : Math.min(100, Math.max(0, n)) }

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
        getMismatches(gstin, '', { severity: sevFilter, mismatch_type: typeFilter, page, page_size: pageSize })
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
            if (d.invoice)  path.push({ type: 'Invoice',  label: d.invoice.invoice_number || 'Invoice' })
            if (d.seller?.gstin_number) path.push({ type: 'GSTIN', label: d.seller.gstin_number })
            if (d.buyer?.gstin_number)  path.push({ type: 'GSTIN', label: d.buyer.gstin_number })
            if (d.irn)          path.push({ type: 'IRN',    label: d.irn.irn_number || 'IRN' })
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
    const filtered = search
        ? mismatches.filter(m =>
            (m.description || '').toLowerCase().includes(search.toLowerCase()) ||
            (m.id || '').toLowerCase().includes(search.toLowerCase()) ||
            (m.type || '').toLowerCase().includes(search.toLowerCase()) ||
            (m.narrative || '').toLowerCase().includes(search.toLowerCase()))
        : mismatches

    return (
        <div className="space-y-4 animate-fade-in">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div>
                    <h2 className="text-xl font-extrabold text-slate-800 tracking-tight flex items-center gap-2">
                        <Zap size={19} className="text-teal-500" /> Fraud Case Explorer
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                        <span className="font-semibold text-slate-700">{total}</span> findings · GSTIN <span className="font-mono text-slate-600">{gstin}</span>
                    </p>
                </div>
                <button onClick={load}
                    className="flex items-center gap-1.5 border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 px-3.5 py-2 rounded-lg text-xs font-medium transition-all shadow-sm">
                    <Filter size={13} /> Refresh
                </button>
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-4 gap-3">
                {[
                    { label: 'Total Cases', value: total,                   icon: FileText,     color: 'text-blue-600',   bg: 'bg-blue-50',   border: 'border-blue-100' },
                    { label: 'Critical',    value: sevCounts.CRITICAL || 0, icon: AlertTriangle, color: 'text-red-600',   bg: 'bg-red-50',    border: 'border-red-100' },
                    { label: 'High Risk',   value: sevCounts.HIGH || 0,     icon: AlertCircle,   color: 'text-orange-600',bg: 'bg-orange-50', border: 'border-orange-100' },
                    { label: 'Fraud Types', value: allTypes.length,         icon: TrendingUp,    color: 'text-purple-600',bg: 'bg-purple-50', border: 'border-purple-100' },
                ].map(({ label, value, icon: Icon, color, bg, border }) => (
                    <div key={label} className={`card p-4 flex items-center gap-3 border ${border}`}>
                        <div className={`w-10 h-10 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
                            <Icon size={18} className={color} />
                        </div>
                        <div>
                            <p className={`text-xl font-extrabold ${color}`}>{value}</p>
                            <p className="text-[10px] text-slate-500 font-medium">{label}</p>
                        </div>
                    </div>
                ))}
            </div>

            {/* Severity pills */}
            <div className="flex gap-2 flex-wrap items-center">
                {['CRITICAL','HIGH','MEDIUM','LOW'].map(sev => {
                    const sc = sevConfig[sev]
                    const cnt = sevCounts[sev] || 0
                    const isActive = sevFilter === sev
                    return (
                        <button key={sev} onClick={() => setSevFilter(isActive ? '' : sev)}
                            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-bold border transition-all ${
                                isActive ? `${sc.bg} ${sc.text} ${sc.border} ring-2 ring-offset-1 ring-current/20` : 'bg-white border-slate-200 text-slate-500 hover:bg-slate-50'}`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                            {sev} ({cnt})
                        </button>
                    )
                })}
                {(sevFilter || typeFilter) && (
                    <button onClick={() => { setSevFilter(''); setTypeFilter('') }}
                        className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 px-2 py-1">
                        <X size={11} /> Clear
                    </button>
                )}
            </div>

            {/* Search + type */}
            <div className="flex gap-2">
                <div className="relative flex-1">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input value={search} onChange={e => setSearch(e.target.value)}
                        placeholder="Search fraud cases, IDs, narratives..."
                        className="w-full pl-9 pr-4 py-2.5 bg-white border border-slate-200 rounded-lg text-xs shadow-sm focus:ring-2 focus:ring-teal-200 focus:border-teal-400 outline-none placeholder-slate-400" />
                </div>
                <div className="relative">
                    <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
                        className="appearance-none bg-white border border-slate-200 rounded-lg px-4 py-2.5 pr-8 text-xs text-slate-600 cursor-pointer focus:ring-2 focus:ring-teal-200 shadow-sm outline-none">
                        <option value="">All Types</option>
                        {allTypes.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                    </select>
                    <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
            </div>

            {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-xs flex items-center gap-2"><AlertTriangle size={13} />{error}</div>}

            {loading ? (
                <div className="space-y-2">{[...Array(6)].map((_, i) => <div key={i} className="h-14 shimmer rounded-xl" />)}</div>
            ) : (
                <>
                    <div className="space-y-1.5">
                        {filtered.map(m => {
                            const sc = sevConfig[m.severity] || sevConfig.MEDIUM
                            const SIcon = sc.icon
                            const isOpen = expanded === m.id
                            const risk = normalizeRisk(m.risk_score)
                            return (
                                <div key={m.id} className={`bg-white rounded-xl border transition-all ${isOpen ? `${sc.border} shadow-md` : 'border-slate-200 hover:border-slate-300 shadow-sm'}`}>
                                    <div className="flex items-center gap-3 px-4 py-3 cursor-pointer" onClick={() => toggleExpand(m)}>
                                        <div className={`w-9 h-9 rounded-xl ${sc.bg} flex items-center justify-center flex-shrink-0`}>
                                            <SIcon size={16} className={sc.text} />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-0.5">
                                                <span className="text-xs font-bold text-slate-800">{(m.type || 'Unknown').replace(/_/g, ' ')}</span>
                                                <span className={`badge ${sc.badge}`}>{m.severity}</span>
                                            </div>
                                            <p className="text-[10.5px] text-slate-500 truncate">{m.description || m.narrative?.slice(0, 100) || m.id}</p>
                                            {(m.seller_name || m.buyer_name) && (
                                                <div className="flex items-center gap-2 mt-0.5 text-[9.5px] text-slate-400">
                                                    {m.seller_name && <span className="flex items-center gap-1"><Building2 size={9} className="text-blue-400" />{m.seller_name}</span>}
                                                    {m.seller_name && m.buyer_name && <ArrowRight size={8} className="text-slate-300" />}
                                                    {m.buyer_name  && <span className="flex items-center gap-1"><Building2 size={9} className="text-teal-400" />{m.buyer_name}</span>}
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-4 flex-shrink-0">
                                            <div className="text-right">
                                                <p className="text-sm font-bold text-red-600 font-mono">{fmt(m.itc_risk || m.tax_difference)}</p>
                                                <p className="text-[9px] text-slate-400">ITC at Risk</p>
                                            </div>
                                            {risk != null && (
                                                <div className="text-right">
                                                    <p className={`text-sm font-bold ${risk > 70 ? 'text-red-600' : risk > 50 ? 'text-amber-600' : 'text-slate-600'}`}>{risk.toFixed(0)}%</p>
                                                    <p className="text-[9px] text-slate-400">Risk</p>
                                                </div>
                                            )}
                                            <ChevronRight size={15} className={`text-slate-300 transition-transform duration-200 ${isOpen ? 'rotate-90' : ''}`} />
                                        </div>
                                    </div>

                                    {isOpen && (
                                        <div className="border-t border-slate-100 p-4 animate-fade-in" style={{ background: 'linear-gradient(135deg,#fafafa,#f8fafc)' }}>
                                            <div className="grid grid-cols-2 gap-5">
                                                <div className="space-y-3">
                                                    <div>
                                                        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1"><FileText size={10} /> Fraud Narrative</p>
                                                        <p className="text-xs text-slate-700 leading-relaxed bg-white rounded-lg p-3 border border-slate-100">{m.narrative || m.description || 'No narrative available'}</p>
                                                    </div>
                                                    {m.evidence_path && (
                                                        <div>
                                                            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1"><Eye size={10} /> Evidence Chain</p>
                                                            <pre className="text-[10px] text-slate-600 bg-white rounded-lg p-3 whitespace-pre-wrap font-mono border border-slate-100">{m.evidence_path}</pre>
                                                        </div>
                                                    )}
                                                    {m.resolution_actions && (
                                                        <div>
                                                            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1"><Shield size={10} /> Resolution Actions</p>
                                                            <p className="text-xs text-slate-600 bg-blue-50 rounded-lg p-3 border border-blue-100">{m.resolution_actions}</p>
                                                        </div>
                                                    )}
                                                    {m.regulatory_ref && (
                                                        <div>
                                                            <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1"><ExternalLink size={10} /> Regulatory Reference</p>
                                                            <p className="text-[10px] text-blue-600 bg-blue-50 rounded-lg p-2 border border-blue-100 font-medium">{m.regulatory_ref}</p>
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="space-y-3">
                                                    <div>
                                                        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1"><DollarSign size={10} /> Financial Details</p>
                                                        <div className="bg-white rounded-lg p-3 border border-slate-100 space-y-1.5 text-xs">
                                                            {[
                                                                m.invoice_value != null && ['Invoice Value', fmt(m.invoice_value), ''],
                                                                m.tax_difference != null && ['Tax Difference', fmt(m.tax_difference), 'text-red-600'],
                                                                m.itc_risk != null       && ['ITC at Risk',    fmt(m.itc_risk),      'text-red-600'],
                                                                m.buyer_gstin            && ['Buyer',  `${m.buyer_gstin}${m.buyer_name ? ` (${m.buyer_name})` : ''}`, 'font-mono text-[10px]'],
                                                                m.seller_gstin           && ['Seller', `${m.seller_gstin}${m.seller_name ? ` (${m.seller_name})` : ''}`, 'font-mono text-[10px]'],
                                                                m.return_period          && ['Period', m.return_period, 'font-mono'],
                                                            ].filter(Boolean).map(([label, value, extra]) => (
                                                                <div key={label} className="flex justify-between border-b border-slate-50 pb-1 last:border-0">
                                                                    <span className="text-slate-500">{label}</span>
                                                                    <span className={`font-bold text-slate-700 text-right max-w-[55%] truncate ${extra}`}>{value}</span>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mb-1.5 flex items-center gap-1"><ArrowRight size={10} /> Graph Traversal</p>
                                                        {tLoading ? (
                                                            <div className="shimmer h-14 rounded-lg" />
                                                        ) : traversal?.path?.length ? (
                                                            <div className="bg-white rounded-lg p-3 border border-slate-100">
                                                                <div className="flex flex-wrap items-center gap-1.5">
                                                                    {traversal.path.map((node, i) => (
                                                                        <React.Fragment key={i}>
                                                                            <span className={`text-[9.5px] px-2 py-1 rounded-md font-semibold ${
                                                                                node.type === 'Mismatch' ? 'bg-red-100 text-red-700' :
                                                                                node.type === 'GSTIN'    ? 'bg-blue-100 text-blue-700' :
                                                                                node.type === 'Invoice'  ? 'bg-amber-100 text-amber-700' :
                                                                                'bg-slate-100 text-slate-600'}`}>
                                                                                {node.label}
                                                                            </span>
                                                                            {i < traversal.path.length - 1 && <ArrowRight size={9} className="text-slate-300" />}
                                                                        </React.Fragment>
                                                                    ))}
                                                                </div>
                                                                {(traversal.seller_name || traversal.buyer_name) && (
                                                                    <div className="flex gap-3 mt-1.5 text-[9.5px] text-slate-500">
                                                                        {traversal.seller_name && <span>Seller: <strong className="text-slate-700">{traversal.seller_name}</strong></span>}
                                                                        {traversal.buyer_name  && <span>Buyer: <strong className="text-slate-700">{traversal.buyer_name}</strong></span>}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ) : (
                                                            <p className="text-[10px] text-slate-400 italic bg-slate-50 rounded-lg p-3">No traversal data</p>
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

                    {filtered.length === 0 && !loading && (
                        <div className="text-center py-16 card">
                            <AlertCircle size={36} className="text-slate-300 mx-auto mb-3" />
                            <h3 className="text-sm font-bold text-slate-600">No Mismatches Found</h3>
                            <p className="text-xs text-slate-400 mt-1">Run reconciliation from the Dashboard to detect GST fraud</p>
                        </div>
                    )}

                    {totalPages > 1 && (
                        <div className="flex items-center justify-between pt-1">
                            <p className="text-xs text-slate-500">Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total}</p>
                            <div className="flex items-center gap-1">
                                <button onClick={() => setPage(1)} disabled={page === 1} className="p-1.5 rounded-lg hover:bg-white border border-transparent hover:border-slate-200 disabled:opacity-30 transition-all">
                                    <ChevronsLeft size={14} className="text-slate-500" />
                                </button>
                                {[...Array(Math.min(5, totalPages))].map((_, i) => {
                                    const pg = page <= 3 ? i + 1 : page + i - 2
                                    if (pg < 1 || pg > totalPages) return null
                                    return (
                                        <button key={pg} onClick={() => setPage(pg)}
                                            className={`w-8 h-8 rounded-lg text-xs font-bold transition-all ${pg === page ? 'text-white' : 'hover:bg-white text-slate-600 border border-transparent hover:border-slate-200'}`}
                                            style={pg === page ? { background: 'linear-gradient(135deg,#0f766e,#14b8a6)' } : {}}>
                                            {pg}
                                        </button>
                                    )
                                })}
                                <button onClick={() => setPage(totalPages)} disabled={page === totalPages} className="p-1.5 rounded-lg hover:bg-white border border-transparent hover:border-slate-200 disabled:opacity-30 transition-all">
                                    <ChevronsRight size={14} className="text-slate-500" />
                                </button>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}
