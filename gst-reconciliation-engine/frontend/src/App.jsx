import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import {
    BarChart3, Search, Network, Users, FileText,
    Shield, ChevronDown, Activity, Target, Zap
} from 'lucide-react'
import ReconciliationSummary from './views/ReconciliationSummary'
import MismatchExplorer from './views/MismatchExplorer'
import GraphVisualization from './views/GraphVisualization'
import VendorScorecard from './views/VendorScorecard'
import AuditTrail from './views/AuditTrail'
import PerformanceResults from './views/PerformanceResults'
import LiveSimulation from './views/LiveSimulation'
import { getGSTINs, getPeriods } from './api'

const navItems = [
    { path: '/', label: 'Dashboard', icon: BarChart3, desc: 'Overview & KPIs' },
    { path: '/mismatches', label: 'Mismatches', icon: Search, desc: 'Fraud Detection' },
    { path: '/graph', label: 'Knowledge Graph', icon: Network, desc: 'Entity Network' },
    { path: '/vendors', label: 'Vendor Risk', icon: Users, desc: 'Scorecard' },
    { path: '/audit', label: 'Audit Trail', icon: FileText, desc: 'Compliance' },
    { path: '/performance', label: 'Performance', icon: Target, desc: 'Model Metrics' },
    { path: '/simulation', label: 'Simulation', icon: Zap, desc: 'Live Demo' },
]

function NavContent({ gstins, selectedGstin, setSelectedGstin, periods, selectedPeriod, setSelectedPeriod }) {
    const location = useLocation()
    return (
        <>
            {/* Header */}
            <header className="gradient-blue text-white px-6 py-3.5 flex items-center justify-between shadow-lg relative z-10">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
                        <Shield size={20} className="text-white" />
                    </div>
                    <div>
                        <h1 className="text-base font-bold tracking-wide leading-tight">GST Reconciliation Engine</h1>
                        <p className="text-[10px] text-blue-200 font-medium tracking-wider uppercase">Knowledge Graph Powered Fraud Detection</p>
                    </div>
                </div>
                <div className="flex gap-3 items-center">
                    <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5 border border-white/20">
                        <span className="text-[10px] text-blue-200 uppercase font-semibold">GSTIN</span>
                        <select className="bg-transparent text-white text-xs font-mono outline-none cursor-pointer min-w-[180px]"
                            value={selectedGstin} onChange={e => setSelectedGstin(e.target.value)}>
                            {gstins.map(g => <option key={g} value={g} className="text-gray-900">{g}</option>)}
                        </select>
                        <ChevronDown size={14} className="text-blue-300" />
                    </div>
                    <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-1.5 border border-white/20">
                        <span className="text-[10px] text-blue-200 uppercase font-semibold">Period</span>
                        <select className="bg-transparent text-white text-xs font-mono outline-none cursor-pointer min-w-[80px]"
                            value={selectedPeriod} onChange={e => setSelectedPeriod(e.target.value)}>
                            {periods.map(p => <option key={p} value={p} className="text-gray-900">{p}</option>)}
                        </select>
                        <ChevronDown size={14} className="text-blue-300" />
                    </div>
                    <div className="flex items-center gap-1.5 bg-emerald-500/20 border border-emerald-400/30 rounded-lg px-3 py-1.5">
                        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-dot" />
                        <span className="text-[10px] text-emerald-300 font-semibold uppercase">Live</span>
                    </div>
                </div>
            </header>

            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar */}
                <nav className="w-56 bg-white border-r border-slate-200 flex flex-col shadow-sm">
                    <div className="flex-1 py-3">
                        {navItems.map(({ path, label, icon: Icon, desc }) => {
                            const isActive = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
                            return (
                                <NavLink key={path} to={path}
                                    className={`flex items-center gap-3 px-4 py-2.5 mx-2 my-0.5 rounded-lg text-sm font-medium transition-all duration-150 ${isActive
                                        ? 'bg-blue-50 text-blue-700 shadow-sm border border-blue-100'
                                        : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}>
                                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${isActive ? 'bg-blue-100' : 'bg-slate-100'}`}>
                                        <Icon size={16} className={isActive ? 'text-blue-600' : 'text-slate-400'} />
                                    </div>
                                    <div>
                                        <p className="leading-tight">{label}</p>
                                        <p className={`text-[10px] ${isActive ? 'text-blue-400' : 'text-slate-400'}`}>{desc}</p>
                                    </div>
                                </NavLink>
                            )
                        })}
                    </div>
                    <div className="px-4 py-3 border-t border-slate-100">
                        <div className="flex items-center gap-2 text-xs text-slate-400">
                            <Activity size={12} />
                            <span>Neo4j Aura Connected</span>
                        </div>
                    </div>
                </nav>

                {/* Main Content */}
                <main className="flex-1 overflow-auto bg-slate-50 p-6">
                    <Routes>
                        <Route path="/" element={<ReconciliationSummary gstin={selectedGstin} period={selectedPeriod} />} />
                        <Route path="/mismatches" element={<MismatchExplorer gstin={selectedGstin} period={selectedPeriod} />} />
                        <Route path="/graph" element={<GraphVisualization gstin={selectedGstin} />} />
                        <Route path="/vendors" element={<VendorScorecard gstin={selectedGstin} />} />
                        <Route path="/audit" element={<AuditTrail gstin={selectedGstin} period={selectedPeriod} />} />
                        <Route path="/performance" element={<PerformanceResults />} />
                        <Route path="/simulation" element={<LiveSimulation />} />
                    </Routes>
                </main>
            </div>
        </>
    )
}

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
            <div className="h-screen flex flex-col bg-slate-50">
                <NavContent
                    gstins={gstins} selectedGstin={selectedGstin} setSelectedGstin={setSelectedGstin}
                    periods={periods} selectedPeriod={selectedPeriod} setSelectedPeriod={setSelectedPeriod}
                />
            </div>
        </Router>
    )
}
