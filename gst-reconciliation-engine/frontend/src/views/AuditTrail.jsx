import React, { useState, useEffect } from 'react'
import { getFindings, getTraversalPath } from '../api'
import { ChevronRight, FileText, AlertTriangle, Shield, DollarSign } from 'lucide-react'

const SEVERITY_ICON = {
    CRITICAL: <AlertTriangle size={16} className="text-red-900" />,
    HIGH: <AlertTriangle size={16} className="text-red-500" />,
    MEDIUM: <Shield size={16} className="text-amber-500" />,
    LOW: <Shield size={16} className="text-green-500" />,
}

export default function AuditTrail({ gstin, period }) {
    const [findings, setFindings] = useState([])
    const [expanded, setExpanded] = useState(null)
    const [traversal, setTraversal] = useState(null)

    useEffect(() => {
        if (!gstin || !period) return
        getFindings(gstin, period)
            .then(r => setFindings(r.data.findings || []))
            .catch(() => { })
    }, [gstin, period])

    const toggle = async (f) => {
        if (expanded === f.mismatch_id) {
            setExpanded(null)
            return
        }
        setExpanded(f.mismatch_id)
        try {
            const r = await getTraversalPath(f.mismatch_id)
            setTraversal(r.data)
        } catch { setTraversal(null) }
    }

    const exportReport = () => {
        window.open(`/api/v1/audit/report?gstin=${gstin}&return_period=${period}`, '_blank')
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-800">Audit Trail</h2>
                <button
                    onClick={exportReport}
                    disabled={!gstin || !period}
                    className="bg-gst-600 hover:bg-gst-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50"
                >
                    <FileText size={16} />
                    Export Report
                </button>
            </div>

            {/* Summary stats */}
            <div className="grid grid-cols-4 gap-4">
                {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(sev => {
                    const count = findings.filter(f => f.severity === sev).length
                    return (
                        <div key={sev} className="bg-white rounded-xl shadow-sm border p-4">
                            <div className="flex items-center gap-2">
                                {SEVERITY_ICON[sev]}
                                <span className="text-xs uppercase text-gray-500">{sev}</span>
                            </div>
                            <p className="text-2xl font-bold mt-1">{count}</p>
                        </div>
                    )
                })}
            </div>

            {/* Findings list */}
            <div className="space-y-3">
                {findings.map(f => (
                    <div key={f.mismatch_id} className="bg-white rounded-xl shadow-sm border">
                        {/* Header */}
                        <div
                            className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-gray-50"
                            onClick={() => toggle(f)}
                        >
                            <ChevronRight
                                size={16}
                                className={`transition-transform ${expanded === f.mismatch_id ? 'rotate-90' : ''}`}
                            />
                            {SEVERITY_ICON[f.severity]}
                            <div className="flex-1">
                                <p className="font-medium text-sm">{f.mismatch_type?.replace(/_/g, ' ')}</p>
                                <p className="text-xs text-gray-500">{f.description || f.mismatch_id}</p>
                            </div>
                            <div className="flex items-center gap-1 text-sm font-mono text-gray-700">
                                <DollarSign size={14} />
                                ₹{Number(f.itc_at_risk || 0).toLocaleString('en-IN')}
                            </div>
                        </div>

                        {/* Expanded detail */}
                        {expanded === f.mismatch_id && (
                            <div className="px-5 pb-4 border-t pt-4 space-y-3 text-sm">
                                <div className="grid grid-cols-2 gap-4">
                                    <div><strong>Mismatch ID:</strong> <span className="font-mono text-xs">{f.mismatch_id}</span></div>
                                    <div><strong>Risk Score:</strong> {((f.composite_risk_score || 0) * 100).toFixed(1)}%</div>
                                    <div><strong>Buyer GSTIN:</strong> {f.buyer_gstin || '—'}</div>
                                    <div><strong>Seller GSTIN:</strong> {f.seller_gstin || '—'}</div>
                                </div>

                                {/* Knowledge Graph Path */}
                                {traversal && (
                                    <div>
                                        <h4 className="font-semibold text-gray-700 mb-2">Knowledge Graph Traversal</h4>
                                        <div className="flex items-center gap-2 text-xs flex-wrap">
                                            {traversal.seller && (
                                                <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded">
                                                    Seller: {traversal.seller.gstin_number}
                                                </span>
                                            )}
                                            <ChevronRight size={12} className="text-gray-400" />
                                            {traversal.invoice && (
                                                <span className="bg-amber-100 text-amber-700 px-2 py-1 rounded">
                                                    INV: {traversal.invoice.invoice_number}
                                                </span>
                                            )}
                                            <ChevronRight size={12} className="text-gray-400" />
                                            {traversal.irn && (
                                                <span className="bg-purple-100 text-purple-700 px-2 py-1 rounded">
                                                    IRN: {traversal.irn.irn_number?.slice(0, 20)}...
                                                </span>
                                            )}
                                            <ChevronRight size={12} className="text-gray-400" />
                                            {traversal.return_filed && (
                                                <span className="bg-green-100 text-green-700 px-2 py-1 rounded">
                                                    {traversal.return_filed.return_type} ({traversal.return_filed.return_period})
                                                </span>
                                            )}
                                            <ChevronRight size={12} className="text-gray-400" />
                                            {traversal.buyer && (
                                                <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded">
                                                    Buyer: {traversal.buyer.gstin_number}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                )}

                                {/* Regulatory References */}
                                {f.regulatory_references && f.regulatory_references.length > 0 && (
                                    <div>
                                        <h4 className="font-semibold text-gray-700 mb-1">Regulatory References</h4>
                                        <ul className="list-disc ml-5 text-xs text-gray-600 space-y-0.5">
                                            {f.regulatory_references.map((ref, i) => <li key={i}>{ref}</li>)}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ))}

                {findings.length === 0 && (
                    <div className="text-center py-12 text-gray-400">
                        No audit findings for this period. Run reconciliation first.
                    </div>
                )}
            </div>
        </div>
    )
}
