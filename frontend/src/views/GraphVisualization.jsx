import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { getGraphData } from '../api'
import { jsPDF } from 'jspdf'
import {
    ZoomIn, ZoomOut, Maximize, RotateCcw, Layers, Info,
    Download, Search, X, FileText, AlertTriangle,
    GitBranch, Activity
} from 'lucide-react'

const NODE_COLORS = {
    GSTIN: { bg: '#14b8a6', border: '#0d9488', font: '#ffffff', shape: 'diamond', size: 35 },
    Invoice: { bg: '#f59e0b', border: '#d97706', font: '#ffffff', shape: 'box', size: 22 },
    'GSTR-1': { bg: '#22c55e', border: '#16a34a', font: '#ffffff', shape: 'ellipse', size: 20 },
    'GSTR-2B': { bg: '#06b6d4', border: '#0891b2', font: '#ffffff', shape: 'ellipse', size: 20 },
    'GSTR-3B': { bg: '#a855f7', border: '#9333ea', font: '#ffffff', shape: 'ellipse', size: 20 },
    Return: { bg: '#8b5cf6', border: '#7c3aed', font: '#ffffff', shape: 'ellipse', size: 20 },
    IRN: { bg: '#6366f1', border: '#4f46e5', font: '#ffffff', shape: 'hexagon', size: 18 },
    EWayBill: { bg: '#ec4899', border: '#db2777', font: '#ffffff', shape: 'hexagon', size: 18 },
    Mismatch: { bg: '#ef4444', border: '#dc2626', font: '#ffffff', shape: 'triangle', size: 28 },
    Taxpayer: { bg: '#0f172a', border: '#1e293b', font: '#ffffff', shape: 'star', size: 30 },
    LineItem: { bg: '#94a3b8', border: '#64748b', font: '#ffffff', shape: 'dot', size: 12 },
    Default: { bg: '#64748b', border: '#475569', font: '#ffffff', shape: 'dot', size: 18 },
}

const physicsOptions = {
    forceAtlas2Based: { gravitationalConstant: -40, centralGravity: 0.005, springLength: 140, springConstant: 0.06, damping: 0.5 },
    maxVelocity: 40, solver: 'forceAtlas2Based', stabilization: { iterations: 200, updateInterval: 25 },
}

export default function GraphVisualization({ gstin, period }) {
    const containerRef = useRef(null)
    const networkRef = useRef(null)
    const nodesRef = useRef(new DataSet())
    const edgesRef = useRef(new DataSet())
    const [depth, setDepth] = useState(1)
    const [loading, setLoading] = useState(false)
    const [selected, setSelected] = useState(null)
    const [stats, setStats] = useState({ nodes: 0, edges: 0 })
    const [showTypes, setShowTypes] = useState({})
    const [searchNode, setSearchNode] = useState('')
    const [stabilized, setStabilized] = useState(false)
    const [circularCount, setCircularCount] = useState(0)
    const [showCircularOnly, setShowCircularOnly] = useState(false)

    const buildGraph = useCallback(async () => {
        if (!gstin) return
        setLoading(true); setSelected(null); setStabilized(false)
        try {
            const res = await getGraphData(gstin, depth)
            const data = res.data
            const rawNodes = data.nodes || []
            const rawEdges = data.edges || []

            const typeCounts = {}
            const visNodes = rawNodes.map(n => {
                const t = n.type || 'Default'
                typeCounts[t] = (typeCounts[t] || 0) + 1
                const c = NODE_COLORS[t] || NODE_COLORS.Default
                const isCircular = n.in_circular_trade
                return {
                    id: n.id,
                    label: n.label || n.id?.slice(-6),
                    color: {
                        background: isCircular && t === 'GSTIN' ? '#dc2626' : c.bg,
                        border: isCircular && t === 'GSTIN' ? '#991b1b' : c.border,
                        highlight: { background: isCircular ? '#dc2626' : c.bg, border: '#000' }
                    },
                    font: { color: c.font, size: t === 'Mismatch' ? 11 : 10, face: 'Inter, sans-serif', bold: t === 'GSTIN' || t === 'Mismatch' },
                    shape: c.shape,
                    size: isCircular && t === 'GSTIN' ? c.size + 8 : c.size,
                    borderWidth: isCircular ? 4 : t === 'Mismatch' ? 3 : 2,
                    shadow: t === 'Mismatch' ? { enabled: true, color: '#ef444466', size: 15 } :
                        isCircular ? { enabled: true, color: '#dc262666', size: 20 } : false,
                    _type: t, _props: n.properties || {}, _circular: isCircular || false,
                }
            })

            const visEdges = rawEdges.map((e, i) => {
                const isCircularEdge = e.circular === true
                const isFraudEdge = (e.label === 'INVOLVES' || e.label === 'DETECTED_FOR')
                return {
                    id: `e${i}`, from: e.from, to: e.to,
                    label: isCircularEdge ? `${e.label || ''} ⚠️` : (e.label || ''),
                    font: { size: 8, color: isCircularEdge ? '#dc2626' : '#94a3b8', strokeWidth: 0, face: 'Inter, sans-serif' },
                    color: { color: isCircularEdge ? '#dc2626' : isFraudEdge ? '#ef4444' : '#cbd5e1', highlight: '#14b8a6', opacity: isCircularEdge ? 1.0 : 0.7 },
                    width: isCircularEdge ? 4 : isFraudEdge ? 2.5 : 1,
                    dashes: isFraudEdge && !isCircularEdge ? [5, 5] : false,
                    arrows: { to: { enabled: true, scaleFactor: isCircularEdge ? 0.8 : 0.5 } },
                    smooth: { type: 'curvedCW', roundness: isCircularEdge ? 0.25 : 0.15 },
                    _circular: isCircularEdge,
                }
            })

            nodesRef.current.clear(); edgesRef.current.clear()
            nodesRef.current.add(visNodes); edgesRef.current.add(visEdges)
            setStats({ nodes: visNodes.length, edges: visEdges.length })
            setShowTypes(typeCounts)
            setCircularCount(data.circular_trade_count || 0)
        } catch (err) {
            console.error('Graph error:', err)
        }
        setLoading(false)
    }, [gstin, depth])

    useEffect(() => { buildGraph() }, [buildGraph])

    useEffect(() => {
        if (!containerRef.current) return
        const network = new Network(containerRef.current,
            { nodes: nodesRef.current, edges: edgesRef.current },
            {
                physics: physicsOptions,
                interaction: { hover: true, tooltipDelay: 100, navigationButtons: false, keyboard: true, zoomView: true, dragView: true },
                layout: { improvedLayout: true },
                edges: { smooth: { type: 'curvedCW', roundness: 0.15 } },
            }
        )
        networkRef.current = network
        network.on('click', params => {
            if (params.nodes.length > 0) {
                setSelected(nodesRef.current.get(params.nodes[0]))
            } else { setSelected(null) }
        })
        network.on('stabilized', () => setStabilized(true))
        return () => network.destroy()
    }, [])

    const zoomIn = () => networkRef.current?.moveTo({ scale: networkRef.current.getScale() * 1.3, animation: { duration: 300 } })
    const zoomOut = () => networkRef.current?.moveTo({ scale: networkRef.current.getScale() * 0.7, animation: { duration: 300 } })
    const resetView = () => networkRef.current?.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } })
    const rearrange = () => { setStabilized(false); networkRef.current?.stabilize(200) }

    const focusNode = () => {
        if (!searchNode) return
        const found = nodesRef.current.get({ filter: n => (n.label || '').toLowerCase().includes(searchNode.toLowerCase()) })
        if (found.length > 0) {
            networkRef.current?.focus(found[0].id, { scale: 1.5, animation: { duration: 500 } })
            networkRef.current?.selectNodes([found[0].id])
            setSelected(found[0])
        }
    }

    const exportPNG = () => {
        const canvas = containerRef.current?.querySelector('canvas')
        if (!canvas) return
        const link = document.createElement('a')
        link.download = `nexusgst-graph-${gstin}.png`
        link.href = canvas.toDataURL('image/png')
        link.click()
    }

    const exportPDF = () => {
        const canvas = containerRef.current?.querySelector('canvas')
        if (!canvas) return
        const imgData = canvas.toDataURL('image/png')
        const pdf = new jsPDF({ orientation: canvas.width > canvas.height ? 'landscape' : 'portrait', unit: 'px', format: [canvas.width, canvas.height] })
        pdf.addImage(imgData, 'PNG', 0, 0, canvas.width, canvas.height)
        pdf.setFontSize(14); pdf.setTextColor(30, 41, 59)
        pdf.text(`NexusGST Knowledge Graph — ${gstin}`, 20, 24)
        pdf.setFontSize(9); pdf.setTextColor(100, 116, 139)
        pdf.text(`${stats.nodes} nodes, ${stats.edges} edges | Depth: ${depth} | ${new Date().toLocaleString()}`, 20, 40)
        pdf.save(`nexusgst-graph-${gstin}.pdf`)
    }

    return (
        <div className="space-y-4 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                        <Activity size={20} className="text-teal-600" />
                        Knowledge Graph
                    </h2>
                    <p className="text-sm text-slate-500 mt-0.5">
                        {stats.nodes} nodes &nbsp;·&nbsp; {stats.edges} edges &nbsp;·&nbsp; Depth {depth}
                        {circularCount > 0 && <span className="text-red-600 font-semibold ml-2">| {circularCount} circular trade entities</span>}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {circularCount > 0 && (
                        <button onClick={() => setShowCircularOnly(!showCircularOnly)}
                            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-all ${showCircularOnly ? 'bg-red-600 text-white shadow-md' : 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'}`}>
                            <GitBranch size={13} /> Circular Trades
                        </button>
                    )}
                    <button onClick={exportPDF}
                        className="flex items-center gap-1.5 bg-teal-600 hover:bg-teal-700 text-white px-3 py-2 rounded-lg text-xs font-semibold transition-all shadow-sm">
                        <FileText size={13} /> Export PDF
                    </button>
                    <button onClick={exportPNG}
                        className="flex items-center gap-1.5 border border-slate-200 text-slate-600 hover:bg-slate-50 px-3 py-2 rounded-lg text-xs font-medium transition-all">
                        <Download size={13} /> Export PNG
                    </button>
                </div>
            </div>

            {/* Circular Trade Alert */}
            {circularCount > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
                        <AlertTriangle size={18} className="text-red-600" />
                    </div>
                    <div>
                        <h4 className="text-sm font-bold text-red-800">Circular Trade Network Detected</h4>
                        <p className="text-xs text-red-600 mt-0.5 leading-relaxed">
                            {circularCount} GSTIN entities are involved in circular trading patterns (A→B→C→A).
                            Highlighted in <span className="font-bold text-red-700">RED</span> with thick red edges.
                            Circular trades are used to fraudulently inflate ITC claims.
                        </p>
                    </div>
                </div>
            )}

            {/* Controls Bar */}
            <div className="card px-4 py-3 flex items-center gap-4 flex-wrap">
                {/* Depth */}
                <div className="flex items-center gap-2">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Depth</label>
                    <div className="flex items-center gap-1">
                        {[1, 2, 3, 4].map(d => (
                            <button key={d} onClick={() => setDepth(d)}
                                className={`w-7 h-7 rounded-lg text-xs font-bold transition-all ${d === depth ? 'bg-teal-600 text-white shadow-sm' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                                {d}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="w-px h-5 bg-slate-200" />

                {/* Zoom Controls */}
                <div className="flex items-center gap-1">
                    {[
                        { icon: ZoomIn, action: zoomIn, title: 'Zoom In' },
                        { icon: ZoomOut, action: zoomOut, title: 'Zoom Out' },
                        { icon: Maximize, action: resetView, title: 'Fit View' },
                        { icon: RotateCcw, action: rearrange, title: 'Rearrange' },
                    ].map(({ icon: Icon, action, title }) => (
                        <button key={title} onClick={action} title={title}
                            className="w-7 h-7 rounded-lg bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors text-slate-600">
                            <Icon size={13} />
                        </button>
                    ))}
                </div>

                <div className="w-px h-5 bg-slate-200" />

                {/* Search Node */}
                <div className="relative flex items-center">
                    <input value={searchNode} onChange={e => setSearchNode(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && focusNode()}
                        placeholder="Find node..."
                        className="w-40 pl-3 pr-8 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:ring-2 focus:ring-teal-200 outline-none" />
                    <button onClick={focusNode} className="absolute right-2">
                        <Search size={12} className="text-slate-400" />
                    </button>
                </div>

                <div className="flex-1" />

                {/* Status indicator */}
                {loading ? (
                    <span className="text-xs text-teal-600 font-medium flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-teal-500 animate-pulse" /> Loading...
                    </span>
                ) : stabilized ? (
                    <span className="flex items-center gap-1.5 text-xs text-green-600 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500" /> Stable
                    </span>
                ) : (
                    <span className="flex items-center gap-1.5 text-xs text-amber-500 font-medium">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> Stabilizing...
                    </span>
                )}
            </div>

            {/* Graph + Legend + Info Panel */}
            <div className="grid grid-cols-[1fr_240px] gap-4">
                {/* Graph Canvas */}
                <div className="card overflow-hidden relative" style={{ height: '540px' }}>
                    <div ref={containerRef} className="w-full h-full" />
                    {loading && (
                        <div className="absolute inset-0 bg-white/85 flex items-center justify-center z-10">
                            <div className="flex flex-col items-center gap-3">
                                <div className="w-9 h-9 border-[3px] border-teal-500 border-t-transparent rounded-full animate-spin" />
                                <span className="text-sm text-slate-500 font-medium">Rendering graph...</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Panel */}
                <div className="space-y-4">
                    {/* Legend */}
                    <div className="card p-4">
                        <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                            <Layers size={12} /> Node Types
                        </p>
                        <div className="space-y-1.5">
                            {Object.entries(showTypes).sort((a, b) => b[1] - a[1]).map(([type, count]) => {
                                const c = NODE_COLORS[type] || NODE_COLORS.Default
                                return (
                                    <div key={type} className="flex items-center gap-2 text-xs">
                                        <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: c.bg }} />
                                        <span className="text-slate-600 flex-1">{type}</span>
                                        <span className="text-slate-400 font-mono text-[10px]">{count}</span>
                                    </div>
                                )
                            })}
                        </div>
                        <div className="border-t border-slate-100 mt-3 pt-3">
                            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Edge Types</p>
                            <div className="space-y-1.5">
                                <div className="flex items-center gap-2 text-xs">
                                    <div className="w-6 rounded flex-shrink-0 bg-red-600" style={{ height: '3px' }} />
                                    <span className="text-red-600 font-semibold">Circular Trade</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <div className="w-6 flex-shrink-0" style={{ borderTop: '2px dashed #ef4444' }} />
                                    <span className="text-red-500">Fraud Link</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <div className="w-6 h-px bg-slate-300 flex-shrink-0" />
                                    <span className="text-slate-500">Normal</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Selected Node Info */}
                    {selected && (
                        <div className="card p-4 animate-slide-up">
                            <div className="flex items-center justify-between mb-3">
                                <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                                    <Info size={12} /> Node Details
                                </p>
                                <button onClick={() => setSelected(null)}
                                    className="text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100 transition-colors">
                                    <X size={13} />
                                </button>
                            </div>
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="w-4 h-4 rounded-sm" style={{ backgroundColor: (NODE_COLORS[selected._type] || NODE_COLORS.Default).bg }} />
                                    <span className="text-sm font-bold text-slate-800">{selected._type}</span>
                                    {selected._circular && (
                                        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-bold">CIRCULAR</span>
                                    )}
                                </div>
                                <p className="text-xs font-mono text-teal-600 break-all">{selected.label}</p>
                                <div className="border-t border-slate-100 pt-2 space-y-1.5 max-h-[240px] overflow-y-auto">
                                    {Object.entries(selected._props || {}).filter(([k]) => !k.startsWith('_')).slice(0, 20).map(([k, v]) => (
                                        <div key={k} className="flex justify-between gap-2 text-[11px]">
                                            <span className="text-slate-400 truncate">{k}</span>
                                            <span className="text-slate-700 font-medium text-right truncate max-w-[120px] font-mono">{String(v)}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
