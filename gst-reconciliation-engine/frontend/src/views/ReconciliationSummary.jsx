import React, { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { runReconciliation, getDashboardSummary, getMismatchTrends } from '../api'

const SEVERITY_COLORS = { CRITICAL: '#991b1b', HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#22c55e' }

export default function ReconciliationSummary({ gstin, period }) {
    const [summary, setSummary] = useState(null)
    const [running, setRunning] = useState(false)
    const [trends, setTrends] = useState([])
    const [error, setError] = useState(null)

    useEffect(() => {
        if (!gstin || !period) return
        getDashboardSummary(gstin, period)
            .then(r => setSummary(r.data))
            .catch(() => { })
        getMismatchTrends(gstin)
            .then(r => setTrends(r.data.trends || []))
            .catch(() => { })
    }, [gstin, period])

    const handleRun = async () => {
        setRunning(true)
        setError(null)
        try {
            const res = await runReconciliation(gstin, period)
            setSummary(prev => ({ ...prev, reconciliation: res.data }))
        } catch (e) {
            setError(e.response?.data?.detail || 'Reconciliation failed')
        }
        setRunning(false)
    }

    const recon = summary?.reconciliation
    const severityData = summary?.mismatches?.map(m => ({
        name: m.severity,
        count: m.cnt,
        itcRisk: m.itc_risk,
    })) || []

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-800">Reconciliation Summary</h2>
                <button
                    onClick={handleRun}
                    disabled={running || !gstin}
                    className="bg-gst-600 hover:bg-gst-700 text-white px-5 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                    {running ? 'Running...' : 'Run Reconciliation'}
                </button>
            </div>

            {error && <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg">{error}</div>}

            {/* KPI Cards */}
            <div className="grid grid-cols-4 gap-4">
                {[
                    { label: 'Total Invoices', value: recon?.total_invoices ?? summary?.invoices?.total_invoices ?? '—', color: 'blue' },
                    { label: 'Matched', value: recon?.matched ?? '—', color: 'green' },
                    { label: 'Mismatches', value: recon ? (recon.partial_matched + recon.unmatched) : '—', color: 'red' },
                    { label: 'ITC at Risk', value: recon?.itc_at_risk != null ? `₹${Number(recon.itc_at_risk).toLocaleString('en-IN')}` : '—', color: 'amber' },
                ].map(({ label, value, color }) => (
                    <div key={label} className="bg-white rounded-xl shadow-sm border p-5">
                        <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
                        <p className={`text-2xl font-bold mt-1 text-${color}-600`}>{value}</p>
                    </div>
                ))}
            </div>

            {/* Risk gauge */}
            {summary?.risk?.risk_score != null && (
                <div className="bg-white rounded-xl shadow-sm border p-5">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Vendor Risk Score</h3>
                    <div className="flex items-center gap-4">
                        <div className="w-full bg-gray-200 rounded-full h-4">
                            <div
                                className={`h-4 rounded-full ${summary.risk.risk_score > 0.7 ? 'bg-risk-critical' :
                                        summary.risk.risk_score > 0.5 ? 'bg-risk-high' :
                                            summary.risk.risk_score > 0.3 ? 'bg-risk-medium' : 'bg-risk-low'
                                    }`}
                                style={{ width: `${(summary.risk.risk_score * 100).toFixed(0)}%` }}
                            />
                        </div>
                        <span className="text-sm font-bold w-16 text-right">
                            {(summary.risk.risk_score * 100).toFixed(0)}%
                        </span>
                    </div>
                </div>
            )}

            {/* Charts */}
            <div className="grid grid-cols-2 gap-6">
                {/* Severity Pie */}
                <div className="bg-white rounded-xl shadow-sm border p-5">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Mismatches by Severity</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <PieChart>
                            <Pie data={severityData} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={90} label>
                                {severityData.map((entry) => (
                                    <Cell key={entry.name} fill={SEVERITY_COLORS[entry.name] || '#94a3b8'} />
                                ))}
                            </Pie>
                            <Tooltip formatter={(v) => v.toLocaleString('en-IN')} />
                        </PieChart>
                    </ResponsiveContainer>
                </div>

                {/* Trend Bar */}
                <div className="bg-white rounded-xl shadow-sm border p-5">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Monthly Mismatch Trend</h3>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={trends}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="period" tick={{ fontSize: 11 }} />
                            <YAxis />
                            <Tooltip />
                            <Bar dataKey="mismatch_count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    )
}
