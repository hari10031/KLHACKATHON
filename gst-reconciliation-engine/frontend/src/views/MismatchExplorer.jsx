import React, { useState, useEffect, useCallback } from 'react'
import { getMismatches, getTraversalPath } from '../api'
import { ChevronDown, ChevronUp, X } from 'lucide-react'

const SEVERITY_BADGE = {
    CRITICAL: 'bg-red-900 text-white',
    HIGH: 'bg-red-500 text-white',
    MEDIUM: 'bg-amber-500 text-white',
    LOW: 'bg-green-500 text-white',
}

export default function MismatchExplorer({ gstin, period }) {
    const [mismatches, setMismatches] = useState([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [filters, setFilters] = useState({ severity: '', mismatch_type: '' })
    const [selected, setSelected] = useState(null)
    const [traversal, setTraversal] = useState(null)

    const load = useCallback(() => {
        if (!gstin || !period) return
        getMismatches(gstin, period, { ...filters, page, page_size: 20 })
            .then(r => {
                setMismatches(r.data.mismatches || [])
                setTotal(r.data.total || 0)
            })
            .catch(() => { })
    }, [gstin, period, filters, page])

    useEffect(() => { load() }, [load])

    const openDetail = async (m) => {
        setSelected(m)
        try {
            const r = await getTraversalPath(m.mismatch_id)
            setTraversal(r.data)
        } catch { setTraversal(null) }
    }

    return (
        <div className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-800">Mismatch Explorer</h2>

            {/* Filters */}
            <div className="flex gap-3">
                <select
                    className="border rounded px-3 py-1.5 text-sm"
                    value={filters.severity}
                    onChange={e => { setFilters(f => ({ ...f, severity: e.target.value })); setPage(1) }}
                >
                    <option value="">All Severities</option>
                    {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => <option key={s}>{s}</option>)}
                </select>
                <select
                    className="border rounded px-3 py-1.5 text-sm"
                    value={filters.mismatch_type}
                    onChange={e => { setFilters(f => ({ ...f, mismatch_type: e.target.value })); setPage(1) }}
                >
                    <option value="">All Types</option>
                    {[
                        'INVOICE_MISSING', 'VALUE_MISMATCH', 'TAX_RATE_MISMATCH', 'DATE_MISMATCH',
                        'DUPLICATE_INVOICE', 'PHANTOM_INVOICE', 'ITC_OVERCLAIM', 'CIRCULAR_TRADE',
                        'HSN_MISMATCH', 'LATE_FILING', 'CANCELLED_CLAIMED',
                    ].map(t => <option key={t}>{t}</option>)}
                </select>
                <span className="text-sm text-gray-500 self-center ml-auto">{total} results</span>
            </div>

            {/* Table */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                        <tr>
                            <th className="px-4 py-3 text-left">ID</th>
                            <th className="px-4 py-3 text-left">Type</th>
                            <th className="px-4 py-3 text-left">Severity</th>
                            <th className="px-4 py-3 text-right">ITC at Risk (₹)</th>
                            <th className="px-4 py-3 text-right">Risk Score</th>
                            <th className="px-4 py-3"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y">
                        {mismatches.map(m => (
                            <tr key={m.mismatch_id} className="hover:bg-gray-50 cursor-pointer" onClick={() => openDetail(m)}>
                                <td className="px-4 py-3 font-mono text-xs">{m.mismatch_id?.slice(0, 12)}</td>
                                <td className="px-4 py-3">{m.mismatch_type}</td>
                                <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${SEVERITY_BADGE[m.severity] || ''}`}>
                                        {m.severity}
                                    </span>
                                </td>
                                <td className="px-4 py-3 text-right font-mono">
                                    {Number(m.itc_at_risk || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                </td>
                                <td className="px-4 py-3 text-right font-mono">
                                    {((m.composite_risk_score || 0) * 100).toFixed(0)}%
                                </td>
                                <td className="px-4 py-3 text-right text-gray-400">
                                    <ChevronDown size={16} />
                                </td>
                            </tr>
                        ))}
                        {mismatches.length === 0 && (
                            <tr><td colSpan={6} className="text-center py-8 text-gray-400">No mismatches found</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <div className="flex justify-between items-center text-sm">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                    className="px-3 py-1.5 border rounded disabled:opacity-40">Previous</button>
                <span className="text-gray-500">Page {page} of {Math.ceil(total / 20) || 1}</span>
                <button onClick={() => setPage(p => p + 1)} disabled={page * 20 >= total}
                    className="px-3 py-1.5 border rounded disabled:opacity-40">Next</button>
            </div>

            {/* Detail Drawer */}
            {selected && (
                <div className="fixed inset-0 z-50 flex">
                    <div className="bg-black/30 flex-1" onClick={() => setSelected(null)} />
                    <div className="w-[500px] bg-white shadow-2xl overflow-y-auto p-6 space-y-4">
                        <div className="flex justify-between items-center">
                            <h3 className="font-bold text-lg">Mismatch Detail</h3>
                            <button onClick={() => setSelected(null)}><X size={20} /></button>
                        </div>
                        <div className="space-y-2 text-sm">
                            <p><strong>ID:</strong> {selected.mismatch_id}</p>
                            <p><strong>Type:</strong> {selected.mismatch_type}</p>
                            <p><strong>Severity:</strong> {selected.severity}</p>
                            <p><strong>Description:</strong> {selected.description}</p>
                            <p><strong>ITC at Risk:</strong> ₹{Number(selected.itc_at_risk || 0).toLocaleString('en-IN')}</p>
                            <p><strong>Risk Score:</strong> {((selected.composite_risk_score || 0) * 100).toFixed(1)}%</p>
                        </div>

                        {traversal && (
                            <div className="space-y-2">
                                <h4 className="font-semibold text-sm text-gray-600">Graph Traversal Path</h4>
                                <div className="bg-gray-50 rounded p-3 text-xs font-mono space-y-1">
                                    {traversal.seller && <p>Seller: {traversal.seller.gstin_number}</p>}
                                    {traversal.invoice && <p>→ Invoice: {traversal.invoice.invoice_number}</p>}
                                    {traversal.irn && <p>→ IRN: {traversal.irn.irn_number}</p>}
                                    {traversal.return_filed && <p>→ Return: {traversal.return_filed.return_type} ({traversal.return_filed.return_period})</p>}
                                    {traversal.buyer && <p>→ Buyer: {traversal.buyer.gstin_number}</p>}
                                </div>
                            </div>
                        )}

                        {selected.resolution_actions && (
                            <div className="space-y-1">
                                <h4 className="font-semibold text-sm text-gray-600">Resolution Actions</h4>
                                <ul className="list-disc ml-5 text-xs space-y-0.5">
                                    {(Array.isArray(selected.resolution_actions) ? selected.resolution_actions : []).map((a, i) => (
                                        <li key={i}>{a}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
