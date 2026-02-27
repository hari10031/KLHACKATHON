import React, { useState, useEffect, useCallback } from 'react'
import { getFindings, getTraversalPath } from '../api'
import {
    FileText, Download, AlertTriangle, AlertCircle, Info, CheckCircle,
    ChevronRight, Clock, DollarSign, Shield, Eye, ArrowRight, Search,
    Zap, ExternalLink, BookOpen, Target, X, Filter, Building2
} from 'lucide-react'

const sevConfig = {
    CRITICAL: { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200', dot: 'bg-red-600', icon: AlertTriangle, gradient: 'gradient-red' },
    HIGH: { bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-100', dot: 'bg-red-500', icon: AlertCircle, gradient: 'gradient-red' },
    MEDIUM: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-100', dot: 'bg-amber-500', icon: Info, gradient: 'gradient-amber' },
    LOW: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-100', dot: 'bg-green-500', icon: CheckCircle, gradient: 'gradient-green' },
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

export default function AuditTrail({ gstin, period }) {
    const [findings, setFindings] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [expanded, setExpanded] = useState(null)
    const [traversal, setTraversal] = useState(null)
    const [tLoading, setTLoading] = useState(false)
    const [sevTab, setSevTab] = useState('')
    const [search, setSearch] = useState('')

    const load = useCallback(() => {
        if (!gstin) return
        setLoading(true); setError(null)
        getFindings(gstin, period || '')
            .then(r => {
                setFindings(r.data.findings || [])
                setTotal(r.data.total || 0)
            })
            .catch(e => setError(e.response?.data?.detail || 'Failed to load audit findings'))
            .finally(() => setLoading(false))
    }, [gstin, period])

    useEffect(() => { load() }, [load])

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

    const toggleExpand = (f) => {
        if (expanded === f.id) { setExpanded(null); setTraversal(null) }
        else { setExpanded(f.id); loadTraversal(f.id) }
    }

    const exportReport = () => {
        const url = `/api/v1/audit/report?gstin=${gstin}${period ? `&return_period=${period}` : ''}`
        window.open(url, '_blank')
    }

    const sevCounts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }
    findings.forEach(f => { if (sevCounts[f.severity] !== undefined) sevCounts[f.severity]++ })
    const totalItc = findings.reduce((s, f) => s + (f.itc_risk || 0), 0)

    const filtered = findings
        .filter(f => !sevTab || f.severity === sevTab)
        .filter(f => !search || (f.description || '').toLowerCase().includes(search.toLowerCase()) ||
            (f.type || '').toLowerCase().includes(search.toLowerCase()) ||
            (f.narrative || '').toLowerCase().includes(search.toLowerCase()) ||
            (f.id || '').toLowerCase().includes(search.toLowerCase()))

    return (
        <div className="space-y-5 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2"><Building2 size={22} className="text-indigo-600" /> Audit Trail & Compliance Report</h2>
                    <p className="text-sm text-slate-500 mt-0.5">
                        {total} findings  |  GSTIN: <span className="font-mono font-semibold text-slate-700">{gstin}</span>{period ? `  |  Period: ${period}` : ''}
                    </p>
                </div>
                <div className="flex gap-2">
                    <button onClick={load} className="flex items-center gap-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 px-3 py-2 rounded-lg text-xs font-medium transition-all">
                        <Filter size={13} /> Refresh
                    </button>
                    <button onClick={exportReport}
                        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-md shadow-blue-200 transition-all">
                        <Download size={14} /> Export Audit Report
                    </button>
                </div>
            </div>

            {/* Summary KPIs */}
            <div className="grid grid-cols-5 gap-4">
                {[
                    { label: 'Total Findings', value: total, icon: FileText, gradient: 'gradient-blue' },
                    { label: 'Critical Alerts', value: sevCounts.CRITICAL, icon: AlertTriangle, gradient: 'gradient-red' },
                    { label: 'High Risk', value: sevCounts.HIGH, icon: AlertCircle, gradient: 'gradient-amber' },
                    { label: 'ITC Exposure', value: fmt(totalItc), icon: DollarSign, gradient: 'gradient-purple' },
                    { label: 'Resolution Rate', value: '0%', icon: Shield, gradient: 'gradient-indigo' },
                ].map(({ label, value, icon: Icon, gradient }) => (
                    <div key={label} className={`${gradient} rounded-xl p-4 text-white shadow-lg card-hover`}>
                        <div className="w-7 h-7 rounded-lg bg-white/20 flex items-center justify-center mb-1">
                            <Icon size={14} />
                        </div>
                        <p className="text-xl font-extrabold">{value}</p>
                        <p className="text-[10px] text-white/70 uppercase tracking-wider font-medium">{label}</p>
                    </div>
                ))}
            </div>

            {/* Filter bar */}
            <div className="flex items-center gap-3">
                {/* Severity tabs */}
                <div className="flex gap-1">
                    <button onClick={() => setSevTab('')}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${!sevTab ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                        All ({total})
                    </button>
                    {Object.entries(sevCounts).map(([sev, cnt]) => {
                        const sc = sevConfig[sev]
                        return (
                            <button key={sev} onClick={() => setSevTab(sevTab === sev ? '' : sev)}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${sevTab === sev ? `${sc.bg} ${sc.text}` : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${sc.dot}`} />
                                {sev} ({cnt})
                            </button>
                        )
                    })}
                </div>

                <div className="flex-1" />

                {/* Search */}
                <div className="relative">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search findings..."
                        className="w-64 pl-8 pr-4 py-2 bg-white border border-slate-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-200 outline-none" />
                </div>
            </div>

            {error && <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-center gap-2"><AlertTriangle size={16} />{error}</div>}

            {/* Findings Timeline */}
            {loading ? (
                <div className="space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-20 shimmer rounded-xl" />)}</div>
            ) : (
                <div className="relative">
                    {/* Timeline line */}
                    <div className="absolute left-6 top-0 bottom-0 w-px bg-slate-200" />

                    <div className="space-y-3">
                        {filtered.map((f, idx) => {
                            const sc = sevConfig[f.severity] || sevConfig.MEDIUM
                            const SIcon = sc.icon
                            const isOpen = expanded === f.id
                            return (
                                <div key={f.id || idx} className="relative pl-14">
                                    {/* Timeline dot */}
                                    <div className={`absolute left-[18px] top-4 w-3 h-3 rounded-full border-2 border-white ${sc.dot} shadow-sm z-10`} />

                                    <div className={`bg-white rounded-xl border transition-all ${isOpen ? `${sc.border} shadow-md` : 'border-slate-200 hover:border-slate-300 shadow-sm'}`}>
                                        {/* Card Header */}
                                        <div className="flex items-center gap-3 p-4 cursor-pointer" onClick={() => toggleExpand(f)}>
                                            <div className={`w-9 h-9 rounded-lg ${sc.bg} flex items-center justify-center flex-shrink-0`}>
                                                <SIcon size={16} className={sc.text} />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center gap-2 mb-0.5">
                                                    <span className="text-sm font-semibold text-slate-800">{(f.type || 'Finding').replace(/_/g, ' ')}</span>
                                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${sc.bg} ${sc.text}`}>{f.severity}</span>
                                                    {f.invoice_number && (
                                                        <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono">INV: {f.invoice_number}</span>
                                                    )}
                                                </div>
                                                <p className="text-xs text-slate-500 truncate">{f.description || f.narrative?.slice(0, 120) || f.id}</p>
                                            </div>
                                            <div className="flex items-center gap-4 flex-shrink-0">
                                                <div className="text-right">
                                                    <p className="text-sm font-bold text-red-600">{fmt(f.itc_risk || f.tax_difference)}</p>
                                                    <p className="text-[10px] text-slate-400">ITC Risk</p>
                                                </div>
                                                {f.seller_name && (
                                                    <div className="text-right hidden lg:block">
                                                        <p className="text-xs font-medium text-slate-600">{f.seller_name}</p>
                                                        <p className="text-[10px] text-slate-400">Seller</p>
                                                    </div>
                                                )}
                                                <ChevronRight size={16} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                                            </div>
                                        </div>

                                        {/* Expanded content */}
                                        {isOpen && (
                                            <div className="border-t border-slate-100 p-5 animate-fade-in">
                                                <div className="grid grid-cols-2 gap-6">
                                                    {/* Left column */}
                                                    <div className="space-y-4">
                                                        {/* AI Analysis */}
                                                        <div>
                                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1">
                                                                <Zap size={12} className="text-blue-500" /> AI Fraud Analysis
                                                            </h4>
                                                            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-100">
                                                                <p className="text-sm text-slate-700 leading-relaxed">
                                                                    {f.narrative || f.description || 'Analysis pending — run reconciliation to generate ML-powered fraud narrative.'}
                                                                </p>
                                                            </div>
                                                        </div>

                                                        {/* Evidence Chain */}
                                                        {f.evidence_path && (
                                                            <div>
                                                                <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1">
                                                                    <Eye size={12} className="text-purple-500" /> Evidence Chain
                                                                </h4>
                                                                <pre className="text-xs text-slate-600 bg-slate-50 rounded-lg p-3 whitespace-pre-wrap font-mono border border-slate-100">{f.evidence_path}</pre>
                                                            </div>
                                                        )}

                                                        {/* Resolution Actions */}
                                                        {f.resolution_actions && (
                                                            <div>
                                                                <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1">
                                                                    <Target size={12} className="text-green-500" /> Resolution Actions
                                                                </h4>
                                                                <p className="text-sm text-slate-600 bg-green-50 rounded-lg p-3 border border-green-100">{f.resolution_actions}</p>
                                                            </div>
                                                        )}

                                                        {/* Regulatory Reference */}
                                                        {f.regulatory_ref && (
                                                            <div>
                                                                <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1">
                                                                    <BookOpen size={12} className="text-indigo-500" /> Regulatory Reference
                                                                </h4>
                                                                <p className="text-xs text-blue-600 bg-blue-50 rounded-lg p-3 font-medium border border-blue-100">{f.regulatory_ref}</p>
                                                            </div>
                                                        )}
                                                    </div>

                                                    {/* Right column */}
                                                    <div className="space-y-4">
                                                        {/* Financial Details */}
                                                        <div>
                                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1">
                                                                <DollarSign size={12} className="text-amber-500" /> Financial Details
                                                            </h4>
                                                            <div className="bg-slate-50 rounded-lg p-3 space-y-2 text-xs border border-slate-100">
                                                                {f.invoice_number && <div className="flex justify-between"><span className="text-slate-500">Invoice</span><span className="font-mono font-bold text-slate-700">{f.invoice_number}</span></div>}
                                                                {f.invoice_value != null && <div className="flex justify-between"><span className="text-slate-500">Invoice Value</span><span className="font-bold">{fmt(f.invoice_value)}</span></div>}
                                                                {f.tax_difference != null && <div className="flex justify-between"><span className="text-slate-500">Tax Difference</span><span className="font-bold text-red-600">{fmt(f.tax_difference)}</span></div>}
                                                                {f.itc_risk != null && <div className="flex justify-between"><span className="text-slate-500">ITC at Risk</span><span className="font-bold text-red-600">{fmt(f.itc_risk)}</span></div>}
                                                                {f.buyer_gstin && <div className="flex justify-between"><span className="text-slate-500">Buyer</span><span className="font-mono text-slate-700">{f.buyer_gstin}</span></div>}
                                                                {f.seller_gstin && <div className="flex justify-between"><span className="text-slate-500">Seller</span><span className="font-mono text-slate-700">{f.seller_gstin}</span></div>}
                                                                {f.seller_name && f.seller_name !== 'Unknown' && <div className="flex justify-between"><span className="text-slate-500">Seller Name</span><span className="font-semibold text-slate-700">{f.seller_name}</span></div>}
                                                                {f.return_period && <div className="flex justify-between"><span className="text-slate-500">Period</span><span className="font-mono text-slate-700">{f.return_period}</span></div>}
                                                            </div>
                                                        </div>

                                                        {/* Graph Traversal */}
                                                        <div>
                                                            <h4 className="text-xs font-bold uppercase text-slate-400 mb-2 flex items-center gap-1">
                                                                <ArrowRight size={12} className="text-cyan-500" /> Graph Traversal Path
                                                            </h4>
                                                            {tLoading ? (
                                                                <div className="shimmer h-20 rounded-lg" />
                                                            ) : traversal?.path ? (
                                                                <div className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                                                                    <div className="flex flex-wrap items-center gap-1">
                                                                        {traversal.path.map((node, i) => (
                                                                            <React.Fragment key={i}>
                                                                                <span className={`text-[10px] px-2 py-1 rounded font-medium ${node.type === 'Mismatch' ? 'bg-red-100 text-red-700' : node.type === 'GSTIN' ? 'bg-blue-100 text-blue-700' : node.type === 'Invoice' ? 'bg-amber-100 text-amber-700' : 'bg-slate-200 text-slate-600'}`}>
                                                                                    {node.label || node.id}
                                                                                </span>
                                                                                {i < traversal.path.length - 1 && <ArrowRight size={10} className="text-slate-300" />}
                                                                            </React.Fragment>
                                                                        ))}
                                                                    </div>
                                                                    {traversal.seller_name && <p className="text-[10px] text-slate-500 mt-2">Seller: <span className="font-semibold text-slate-700">{traversal.seller_name}</span></p>}
                                                                    {traversal.buyer_name && <p className="text-[10px] text-slate-500">Buyer: <span className="font-semibold text-slate-700">{traversal.buyer_name}</span></p>}
                                                                </div>
                                                            ) : (
                                                                <p className="text-xs text-slate-400 italic bg-slate-50 rounded-lg p-3 border border-slate-100">No traversal data available</p>
                                                            )}
                                                        </div>

                                                        {/* Mismatch ID */}
                                                        <div className="bg-slate-50 rounded-lg p-2.5 border border-slate-100">
                                                            <p className="text-[10px] text-slate-400 uppercase tracking-wider">Finding ID</p>
                                                            <p className="text-xs font-mono text-slate-600 break-all">{f.id}</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>

                    {filtered.length === 0 && !loading && (
                        <div className="text-center py-16 bg-white rounded-xl border border-slate-200 ml-14">
                            <Shield size={40} className="text-slate-300 mx-auto mb-4" />
                            <h3 className="text-lg font-semibold text-slate-600">No Audit Findings</h3>
                            <p className="text-sm text-slate-400 mt-1">Run reconciliation to generate AI-powered fraud analysis</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
