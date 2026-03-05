import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom'
import {
    BarChart3, Search, Network, Users, FileText,
    ChevronDown, Activity, Target, Zap, Shield,
    Database, Cpu, Bell
} from 'lucide-react'
import ReconciliationSummary from './views/ReconciliationSummary'
import MismatchExplorer from './views/MismatchExplorer'
import GraphVisualization from './views/GraphVisualization'
import VendorScorecard from './views/VendorScorecard'
import AuditTrail from './views/AuditTrail'
import PerformanceResults from './views/PerformanceResults'
import LiveSimulation from './views/LiveSimulation'
import { getGSTINs, getPeriods } from './api'

// ── ReconAI Logo SVG ──────────────────────────────────────────────────────────
// Concept: A shield with a scanner crosshair (fraud targeting) + graph nodes
// (knowledge graph) at the crosshair intersections = AI-powered fraud detection
function ReconLogo({ size = 38, animated = false }) {
    return (
        <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg"
            className={animated ? 'recon-logo-spin' : ''}>
            <defs>
                <linearGradient id="shield-bg" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor="#0f172a" />
                    <stop offset="100%" stopColor="#0d2c2a" />
                </linearGradient>
                <linearGradient id="shield-stroke" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stopColor="#14b8a6" />
                    <stop offset="100%" stopColor="#06b6d4" />
                </linearGradient>
                <linearGradient id="center-node" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#14b8a6" />
                    <stop offset="100%" stopColor="#06b6d4" />
                </linearGradient>
                <filter id="glow-node" x="-40%" y="-40%" width="180%" height="180%">
                    <feGaussianBlur stdDeviation="1.2" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <filter id="glow-soft" x="-60%" y="-60%" width="220%" height="220%">
                    <feGaussianBlur stdDeviation="2" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
            </defs>

            {/* Shield body */}
            <path d="M20 2.5L35 8.5V21C35 29.5 28 35.5 20 38C12 35.5 5 29.5 5 21V8.5L20 2.5Z"
                fill="url(#shield-bg)" stroke="url(#shield-stroke)" strokeWidth="1.3" strokeLinejoin="round" />

            {/* Scan ring outer */}
            <circle cx="20" cy="21" r="10.5" fill="none" stroke="rgba(20,184,166,0.18)" strokeWidth="0.8" />
            {/* Scan ring inner */}
            <circle cx="20" cy="21" r="6" fill="none" stroke="rgba(20,184,166,0.28)" strokeWidth="0.8" />

            {/* Crosshair lines */}
            <line x1="20" y1="11" x2="20" y2="31" stroke="rgba(20,184,166,0.22)" strokeWidth="0.75" />
            <line x1="10" y1="21" x2="30" y2="21" stroke="rgba(20,184,166,0.22)" strokeWidth="0.75" />

            {/* Graph edges — connecting crosshair nodes */}
            <line x1="20" y1="12.5" x2="13" y2="21" stroke="rgba(20,184,166,0.45)" strokeWidth="1.1" strokeLinecap="round" />
            <line x1="20" y1="12.5" x2="27" y2="21" stroke="rgba(20,184,166,0.45)" strokeWidth="1.1" strokeLinecap="round" />
            <line x1="13" y1="21" x2="20" y2="29.5" stroke="rgba(6,182,212,0.38)" strokeWidth="1" strokeLinecap="round" />
            <line x1="27" y1="21" x2="20" y2="29.5" stroke="rgba(6,182,212,0.38)" strokeWidth="1" strokeLinecap="round" />

            {/* Graph nodes at crosshair intersections */}
            {/* Top node — largest, primary */}
            <circle cx="20" cy="12.5" r="2.8" fill="url(#center-node)" filter="url(#glow-node)" />
            <circle cx="20" cy="12.5" r="1.2" fill="white" opacity="0.85" />

            {/* Left and right nodes */}
            <circle cx="13" cy="21" r="2" fill="#06b6d4" opacity="0.9" />
            <circle cx="27" cy="21" r="2" fill="#06b6d4" opacity="0.9" />

            {/* Bottom node */}
            <circle cx="20" cy="29.5" r="1.6" fill="#7dd3fc" opacity="0.8" />

            {/* Center target dot */}
            <circle cx="20" cy="21" r="1.5" fill="rgba(20,184,166,0.55)" />
            <circle cx="20" cy="21" r="0.7" fill="#14b8a6" />
        </svg>
    )
}

// ── Splash / loading screen ───────────────────────────────────────────────────
function SplashScreen({ onDone }) {
    const [phase, setPhase] = useState('enter') // enter → loaded → exit
    const [progress, setProgress] = useState(0)

    useEffect(() => {
        // Animate progress bar
        const steps = [
            { target: 18, delay: 200 },
            { target: 42, delay: 500 },
            { target: 67, delay: 900 },
            { target: 85, delay: 1300 },
            { target: 100, delay: 1700 },
        ]
        const timers = steps.map(({ target, delay }) =>
            setTimeout(() => setProgress(target), delay)
        )
        // Move to loaded state
        const loadedTimer = setTimeout(() => setPhase('loaded'), 1800)
        // Exit
        const exitTimer = setTimeout(() => {
            setPhase('exit')
            setTimeout(onDone, 500)
        }, 2300)

        return () => {
            timers.forEach(clearTimeout)
            clearTimeout(loadedTimer)
            clearTimeout(exitTimer)
        }
    }, [onDone])

    return (
        <div className={`splash-overlay${phase === 'exit' ? ' splash-exit' : ''}`}>
            {/* Background grid pattern */}
            <div className="splash-grid" />

            {/* Radial glow blobs */}
            <div className="splash-glow-1" />
            <div className="splash-glow-2" />

            {/* Center content */}
            <div className={`splash-center${phase === 'enter' ? '' : ' splash-center-in'}`}>
                {/* Logo */}
                <div className="splash-logo-wrap">
                    <ReconLogo size={80} />
                    {/* Outer ring pulse */}
                    <div className="splash-ring splash-ring-1" />
                    <div className="splash-ring splash-ring-2" />
                </div>

                {/* Brand name */}
                <div className="splash-title-wrap">
                    <h1 className="splash-title">
                        Recon<span className="splash-title-ai">AI</span>
                    </h1>
                </div>

                {/* Tagline */}
                <p className="splash-tagline">
                    Tax Credit Reconciliation &amp; Fraud Intelligence Platform
                </p>

                {/* Progress bar */}
                <div className="splash-bar-track">
                    <div className="splash-bar-fill" style={{ width: `${progress}%` }} />
                </div>

                {/* Status dots */}
                <div className="splash-dots">
                    {['Graph DB', 'ML Engine', 'API Layer'].map((label, i) => (
                        <div key={label} className="splash-dot-item" style={{ animationDelay: `${0.4 + i * 0.2}s` }}>
                            <span className="splash-dot-pulse" style={{ animationDelay: `${0.5 + i * 0.25}s` }} />
                            <span className="splash-dot-label">{label}</span>
                        </div>
                    ))}
                </div>

                {/* Version */}
                <p className="splash-version">v1.0.0 · Powered by Neo4j &amp; XGBoost</p>
            </div>
        </div>
    )
}

// ── Nav items ─────────────────────────────────────────────────────────────────
const navItems = [
    { path: '/',            label: 'Dashboard',       icon: BarChart3, desc: 'KPIs & Overview' },
    { path: '/mismatches',  label: 'Fraud Cases',     icon: Search,    desc: 'Mismatch Detection' },
    { path: '/graph',       label: 'Knowledge Graph', icon: Network,   desc: 'Entity Network' },
    { path: '/vendors',     label: 'Vendor Risk',     icon: Users,     desc: 'Risk Scorecard' },
    { path: '/audit',       label: 'Audit Trail',     icon: FileText,  desc: 'Compliance Log' },
    { path: '/performance', label: 'ML Metrics',      icon: Target,    desc: 'Model Performance' },
    { path: '/simulation',  label: 'Live Demo',       icon: Zap,       desc: 'Simulation' },
]

// ── Selector pill ─────────────────────────────────────────────────────────────
function SelectorPill({ label, value, options, onChange, mono }) {
    return (
        <div className="flex items-center gap-2 rounded-lg px-3 py-1.5 border border-white/10 hover:bg-white/10 transition-colors"
            style={{ background: 'rgba(255,255,255,0.06)' }}>
            <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color: 'rgba(94,234,212,0.8)' }}>
                {label}
            </span>
            <select
                className="bg-transparent text-white text-xs outline-none cursor-pointer"
                style={{ fontFamily: mono ? '"DM Mono", monospace' : 'inherit', minWidth: mono ? 160 : 80 }}
                value={value}
                onChange={e => onChange(e.target.value)}
            >
                {options.map(o => (
                    <option key={o} value={o} style={{ background: '#1e293b', color: '#f1f5f9' }}>{o}</option>
                ))}
            </select>
            <ChevronDown size={12} style={{ color: 'rgba(94,234,212,0.6)', flexShrink: 0 }} />
        </div>
    )
}

// ── Main app shell ─────────────────────────────────────────────────────────────
function AppShell({ gstins, selectedGstin, setSelectedGstin, periods, selectedPeriod, setSelectedPeriod }) {
    const location = useLocation()
    const currentPage = navItems.find(n =>
        n.path === '/' ? location.pathname === '/' : location.pathname.startsWith(n.path)
    )

    return (
        <div className="h-screen flex flex-col">
            {/* ── Header ──────────────────────────────────────────────────── */}
            <header className="nexus-header flex-shrink-0 z-20">
                <div className="relative z-10 flex items-center justify-between px-5 py-3">
                    {/* Brand */}
                    <div className="flex items-center gap-3">
                        <ReconLogo size={38} />
                        <div>
                            <div className="flex items-center gap-2">
                                <h1 className="text-[17px] font-extrabold tracking-tight text-white leading-none">
                                    Recon<span style={{ color: '#14b8a6' }}>AI</span>
                                </h1>
                                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded"
                                    style={{ background: 'rgba(20,184,166,0.18)', color: '#5eead4', border: '1px solid rgba(20,184,166,0.3)', letterSpacing: '0.07em' }}>
                                    v1.0
                                </span>
                            </div>
                            <p className="text-[9px] font-semibold tracking-widest mt-0.5 uppercase"
                                style={{ color: 'rgba(148,163,184,0.65)', letterSpacing: '0.07em' }}>
                                Tax Credit Reconciliation &amp; Fraud Intelligence
                            </p>
                        </div>
                    </div>

                    {/* Center: breadcrumb */}
                    {currentPage && (
                        <div className="hidden lg:flex items-center gap-2 px-4 py-1.5 rounded-full"
                            style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}>
                            <currentPage.icon size={13} style={{ color: '#14b8a6' }} />
                            <span className="text-xs font-semibold text-white/80">{currentPage.label}</span>
                            <span className="text-[10px]" style={{ color: 'rgba(148,163,184,0.5)' }}>— {currentPage.desc}</span>
                        </div>
                    )}

                    {/* Right controls */}
                    <div className="flex items-center gap-2">
                        {gstins.length > 0 && (
                            <SelectorPill label="GSTIN" value={selectedGstin} options={gstins} onChange={setSelectedGstin} mono />
                        )}
                        {periods.length > 0 && (
                            <SelectorPill label="Period" value={selectedPeriod} options={periods} onChange={setSelectedPeriod} />
                        )}
                        <div className="flex items-center gap-1.5 rounded-lg px-3 py-1.5"
                            style={{ background: 'rgba(20,184,166,0.12)', border: '1px solid rgba(20,184,166,0.25)' }}>
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />
                            <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color: '#5eead4' }}>Live</span>
                        </div>
                        <button className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
                            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)' }}
                            title="Notifications">
                            <Bell size={14} className="text-slate-400 hover:text-white" />
                        </button>
                    </div>
                </div>
            </header>

            {/* ── Body ────────────────────────────────────────────────────── */}
            <div className="flex flex-1 overflow-hidden">
                {/* ── Sidebar ─────────────────────────────────────────────── */}
                <nav className="nexus-sidebar sidebar-scroll w-56 flex-shrink-0 flex flex-col overflow-y-auto">
                    <div className="pt-4 pb-1 px-3">
                        <p className="text-[9px] font-bold tracking-widest uppercase px-2 mb-2"
                            style={{ color: 'rgba(94,234,212,0.4)', letterSpacing: '0.12em' }}>
                            Main Menu
                        </p>
                        {navItems.map(({ path, label, icon: Icon, desc }) => {
                            const isActive = path === '/'
                                ? location.pathname === '/'
                                : location.pathname.startsWith(path)
                            return (
                                <NavLink key={path} to={path} className={`nexus-nav-item${isActive ? ' active' : ''}`}>
                                    <span className="nav-icon-wrap">
                                        <Icon size={15} style={{ color: isActive ? '#5eead4' : 'rgba(148,163,184,0.7)' }} />
                                    </span>
                                    <div className="min-w-0">
                                        <p className="text-[13px] font-medium leading-tight truncate">{label}</p>
                                        <p className="text-[9.5px] leading-tight truncate"
                                            style={{ color: isActive ? 'rgba(94,234,212,0.55)' : 'rgba(100,116,139,0.7)' }}>
                                            {desc}
                                        </p>
                                    </div>
                                </NavLink>
                            )
                        })}
                    </div>

                    <div className="divider-dark mx-4 my-3" />

                    {/* System status */}
                    <div className="px-3 pb-2">
                        <p className="text-[9px] font-bold tracking-widest uppercase px-2 mb-2"
                            style={{ color: 'rgba(94,234,212,0.4)', letterSpacing: '0.12em' }}>
                            System
                        </p>
                        {[
                            { icon: Database, label: 'Neo4j Aura',  sub: 'Connected', color: '#22c55e' },
                            { icon: Cpu,      label: 'ML Engine',   sub: 'Active',    color: '#14b8a6' },
                            { icon: Activity, label: 'API Server',  sub: 'Healthy',   color: '#3b82f6' },
                        ].map(({ icon: Icon, label, sub, color }) => (
                            <div key={label} className="flex items-center gap-2.5 px-3 py-2 rounded-lg mx-1 mb-0.5"
                                style={{ background: 'rgba(255,255,255,0.03)' }}>
                                <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
                                    style={{ background: `${color}18` }}>
                                    <Icon size={12} style={{ color }} />
                                </div>
                                <div className="min-w-0">
                                    <p className="text-[11px] font-medium leading-tight" style={{ color: 'rgba(226,232,240,0.8)' }}>{label}</p>
                                    <p className="text-[9px] leading-tight" style={{ color }}>{sub}</p>
                                </div>
                                <div className="w-1.5 h-1.5 rounded-full ml-auto flex-shrink-0 animate-pulse-dot" style={{ background: color }} />
                            </div>
                        ))}
                    </div>

                    {/* Footer */}
                    <div className="mt-auto px-4 py-3">
                        <div className="divider-dark mb-3" />
                        <div className="flex items-center gap-2 px-1">
                            <ReconLogo size={28} />
                            <div className="min-w-0">
                                <p className="text-[11px] font-bold" style={{ color: 'rgba(226,232,240,0.85)' }}>
                                    Recon<span style={{ color: '#14b8a6' }}>AI</span>
                                </p>
                                <p className="text-[9px]" style={{ color: 'rgba(100,116,139,0.7)' }}>© 2025 · v1.0.0</p>
                            </div>
                        </div>
                    </div>
                </nav>

                {/* ── Main Content ─────────────────────────────────────────── */}
                <main className="flex-1 overflow-auto" style={{ background: '#f0f4f8' }}>
                    <div className="p-6">
                        <Routes>
                            <Route path="/"            element={<ReconciliationSummary gstin={selectedGstin} period={selectedPeriod} />} />
                            <Route path="/mismatches"  element={<MismatchExplorer     gstin={selectedGstin} period={selectedPeriod} />} />
                            <Route path="/graph"       element={<GraphVisualization   gstin={selectedGstin} />} />
                            <Route path="/vendors"     element={<VendorScorecard      gstin={selectedGstin} />} />
                            <Route path="/audit"       element={<AuditTrail           gstin={selectedGstin} period={selectedPeriod} />} />
                            <Route path="/performance" element={<PerformanceResults />} />
                            <Route path="/simulation"  element={<LiveSimulation />} />
                        </Routes>
                    </div>
                </main>
            </div>
        </div>
    )
}

// ── Root ──────────────────────────────────────────────────────────────────────
export default function App() {
    const [splashDone, setSplashDone] = useState(false)
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
        <>
            {!splashDone && <SplashScreen onDone={() => setSplashDone(true)} />}
            <div className={splashDone ? 'app-fade-in' : 'app-hidden'}>
                <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                    <AppShell
                        gstins={gstins}        selectedGstin={selectedGstin}   setSelectedGstin={setSelectedGstin}
                        periods={periods}      selectedPeriod={selectedPeriod} setSelectedPeriod={setSelectedPeriod}
                    />
                </Router>
            </div>
        </>
    )
}
