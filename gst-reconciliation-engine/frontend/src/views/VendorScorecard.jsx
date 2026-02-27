import React, { useState, useEffect } from 'react'
import { getVendorScorecard, getVendorRisk } from '../api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const RISK_COLOR = { low: '#22c55e', medium: '#f59e0b', high: '#ef4444', critical: '#991b1b', unknown: '#94a3b8' }

export default function VendorScorecard({ gstin }) {
    const [vendors, setVendors] = useState([])
    const [page, setPage] = useState(1)
    const [detail, setDetail] = useState(null)

    useEffect(() => {
        if (!gstin) return
        getVendorScorecard(gstin, page)
            .then(r => setVendors(r.data.vendors || []))
            .catch(() => { })
    }, [gstin, page])

    const openDetail = async (v) => {
        try {
            const r = await getVendorRisk(v.gstin)
            setDetail(r.data)
        } catch { setDetail(v) }
    }

    const chartData = vendors.map(v => ({
        name: v.gstin?.slice(-6),
        risk: (v.risk_score * 100).toFixed(0),
        label: v.risk_label,
    }))

    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-800">Vendor Risk Scorecard</h2>

            {/* Risk distribution chart */}
            <div className="bg-white rounded-xl shadow-sm border p-5">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Vendor Risk Distribution</h3>
                <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={chartData}>
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis domain={[0, 100]} />
                        <Tooltip formatter={v => `${v}%`} />
                        <Bar dataKey="risk" radius={[4, 4, 0, 0]}>
                            {chartData.map((entry, i) => (
                                <Cell key={i} fill={RISK_COLOR[entry.label] || RISK_COLOR.unknown} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>

            {/* Vendor table */}
            <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                        <tr>
                            <th className="px-4 py-3 text-left">GSTIN</th>
                            <th className="px-4 py-3 text-left">Name</th>
                            <th className="px-4 py-3 text-right">Invoices</th>
                            <th className="px-4 py-3 text-right">Total Value (₹)</th>
                            <th className="px-4 py-3 text-right">Risk Score</th>
                            <th className="px-4 py-3 text-left">Risk Level</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y">
                        {vendors.map(v => (
                            <tr key={v.gstin} className="hover:bg-gray-50 cursor-pointer" onClick={() => openDetail(v)}>
                                <td className="px-4 py-3 font-mono text-xs">{v.gstin}</td>
                                <td className="px-4 py-3">{v.name || '—'}</td>
                                <td className="px-4 py-3 text-right">{v.invoice_count}</td>
                                <td className="px-4 py-3 text-right font-mono">
                                    {Number(v.total_value || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                </td>
                                <td className="px-4 py-3 text-right font-mono">
                                    {((v.risk_score || 0) * 100).toFixed(0)}%
                                </td>
                                <td className="px-4 py-3">
                                    <span className="px-2 py-0.5 rounded text-xs font-semibold text-white"
                                        style={{ backgroundColor: RISK_COLOR[v.risk_label] || RISK_COLOR.unknown }}>
                                        {v.risk_label?.toUpperCase() || 'N/A'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <div className="flex justify-center gap-3 text-sm">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                    className="px-3 py-1.5 border rounded disabled:opacity-40">Previous</button>
                <span className="self-center text-gray-500">Page {page}</span>
                <button onClick={() => setPage(p => p + 1)}
                    className="px-3 py-1.5 border rounded">Next</button>
            </div>

            {/* Detail modal */}
            {detail && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setDetail(null)}>
                    <div className="bg-white rounded-xl shadow-2xl p-6 w-[450px] space-y-3" onClick={e => e.stopPropagation()}>
                        <h3 className="font-bold text-lg">{detail.gstin}</h3>
                        <p className="text-sm text-gray-600">{detail.name}</p>
                        <div className="grid grid-cols-2 gap-3 text-sm">
                            <div><strong>Risk Score:</strong> {((detail.risk_score || 0) * 100).toFixed(1)}%</div>
                            <div><strong>Risk Label:</strong> {detail.risk_label}</div>
                            <div><strong>PageRank:</strong> {detail.pagerank?.toFixed(4) || 'N/A'}</div>
                            <div><strong>Degree:</strong> {detail.degree?.toFixed(4) || 'N/A'}</div>
                            <div><strong>Betweenness:</strong> {detail.betweenness?.toFixed(4) || 'N/A'}</div>
                            <div><strong>Community:</strong> {detail.community ?? 'N/A'}</div>
                            <div><strong>Invoices:</strong> {detail.invoice_count}</div>
                            <div><strong>Total Value:</strong> ₹{Number(detail.total_value || 0).toLocaleString('en-IN')}</div>
                        </div>
                        <button onClick={() => setDetail(null)} className="mt-3 text-sm text-gst-600 hover:underline">Close</button>
                    </div>
                </div>
            )}
        </div>
    )
}
