import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom'
import { BarChart3, Search, Network, Users, FileText } from 'lucide-react'
import ReconciliationSummary from './views/ReconciliationSummary'
import MismatchExplorer from './views/MismatchExplorer'
import GraphVisualization from './views/GraphVisualization'
import VendorScorecard from './views/VendorScorecard'
import AuditTrail from './views/AuditTrail'
import { getGSTINs, getPeriods } from './api'

const navItems = [
    { path: '/', label: 'Summary', icon: BarChart3 },
    { path: '/mismatches', label: 'Mismatches', icon: Search },
    { path: '/graph', label: 'Graph', icon: Network },
    { path: '/vendors', label: 'Vendors', icon: Users },
    { path: '/audit', label: 'Audit', icon: FileText },
]

export default function App() {
    const [gstins, setGstins] = useState([])
    const [periods, setPeriods] = useState([])
    const [selectedGstin, setSelectedGstin] = useState('')
    const [selectedPeriod, setSelectedPeriod] = useState('')

    useEffect(() => {
        getGSTINs().then(r => {
            const list = r.data.gstins || []
            setGstins(list)
            if (list.length) setSelectedGstin(list[0])
        }).catch(() => { })
        getPeriods().then(r => {
            const list = r.data.periods || []
            setPeriods(list)
            if (list.length) setSelectedPeriod(list[list.length - 1])
        }).catch(() => { })
    }, [])

    return (
        <Router>
            <div className="min-h-screen flex flex-col">
                {/* Header */}
                <header className="bg-gst-900 text-white px-6 py-3 flex items-center justify-between">
                    <h1 className="text-lg font-bold tracking-wide">GST Reconciliation Engine</h1>
                    <div className="flex gap-3 items-center text-sm">
                        <select
                            className="bg-gst-700 text-white border border-gst-600 rounded px-2 py-1"
                            value={selectedGstin}
                            onChange={e => setSelectedGstin(e.target.value)}
                        >
                            {gstins.map(g => <option key={g} value={g}>{g}</option>)}
                        </select>
                        <select
                            className="bg-gst-700 text-white border border-gst-600 rounded px-2 py-1"
                            value={selectedPeriod}
                            onChange={e => setSelectedPeriod(e.target.value)}
                        >
                            {periods.map(p => <option key={p} value={p}>{p}</option>)}
                        </select>
                    </div>
                </header>

                <div className="flex flex-1">
                    {/* Sidebar */}
                    <nav className="w-52 bg-white border-r border-gray-200 py-4">
                        {navItems.map(({ path, label, icon: Icon }) => (
                            <NavLink
                                key={path}
                                to={path}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-5 py-2.5 text-sm font-medium transition-colors ${isActive ? 'bg-gst-50 text-gst-700 border-r-2 border-gst-600' : 'text-gray-600 hover:bg-gray-50'
                                    }`
                                }
                            >
                                <Icon size={18} />
                                {label}
                            </NavLink>
                        ))}
                    </nav>

                    {/* Main Content */}
                    <main className="flex-1 p-6 overflow-auto">
                        <Routes>
                            <Route path="/" element={<ReconciliationSummary gstin={selectedGstin} period={selectedPeriod} />} />
                            <Route path="/mismatches" element={<MismatchExplorer gstin={selectedGstin} period={selectedPeriod} />} />
                            <Route path="/graph" element={<GraphVisualization gstin={selectedGstin} />} />
                            <Route path="/vendors" element={<VendorScorecard gstin={selectedGstin} />} />
                            <Route path="/audit" element={<AuditTrail gstin={selectedGstin} period={selectedPeriod} />} />
                        </Routes>
                    </main>
                </div>
            </div>
        </Router>
    )
}
