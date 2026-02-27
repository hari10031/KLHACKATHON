import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { getGraphData } from '../api'
import { jsPDF } from 'jspdf'
import {
    ZoomIn, ZoomOut, Maximize, RotateCcw, Layers, Info,
    ChevronDown, Download, Search, X, FileText, AlertTriangle,
    GitBranch, Shield, Activity
} from 'lucide-react'

const NODE_COLORS = {
    GSTIN: { bg: '#3b82f6', border: '#2563eb', font: '#ffffff', shape: 'diamond', size: 35 },
    Invoice: { bg: '#f59e0b', border: '#d97706', font: '#ffffff', shape: 'box', size: 22 },
    'GSTR-1': { bg: '#22c55e', border: '#16a34a', font: '#ffffff', shape: 'ellipse', size: 20 },
    'GSTR-2B': { bg: '#06b6d4', border: '#0891b2', font: '#ffffff', shape: 'ellipse', size: 20 },
    'GSTR-3B': { bg: '#a855f7', border: '#9333ea', font: '#ffffff', shape: 'ellipse', size: 20 },
    Return: { bg: '#8b5cf6', border: '#7c3aed', font: '#ffffff', shape: 'ellipse', size: 20 },
    IRN: { bg: '#8b5cf6', border: '#7c3aed', font: '#ffffff', shape: 'hexagon', size: 18 },
    EWayBill: { bg: '#ec4899', border: '#db2777', font: '#ffffff', shape: 'hexagon', size: 18 },
    Mismatch: { bg: '#ef4444', border: '#dc2626', font: '#ffffff', shape: 'triangle', size: 28 },
    Taxpayer: { bg: '#1e3a5f', border: '#0f172a', font: '#ffffff', shape: 'star', size: 30 },
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
                    _type: t,
                    _props: n.properties || {},
                    _circular: isCircular || false,
                }
            })

            const visEdges = rawEdges.map((e, i) => {
                const isCircularEdge = e.circular === true
                const isFraudEdge = (e.label === 'INVOLVES' || e.label === 'DETECTED_FOR')
                return {
                    id: `e${i}`,
                    from: e.from,
                    to: e.to,
                    label: isCircularEdge ? `${e.label || ''} ⚠️` : (e.label || ''),
                    font: { size: 8, color: isCircularEdge ? '#dc2626' : '#94a3b8', strokeWidth: 0, face: 'Inter, sans-serif' },
                    color: {
                        color: isCircularEdge ? '#dc2626' : isFraudEdge ? '#ef4444' : '#cbd5e1',
                        highlight: '#3b82f6',
                        opacity: isCircularEdge ? 1.0 : 0.7,
                    },
                    width: isCircularEdge ? 4 : isFraudEdge ? 2.5 : 1,
                    dashes: isFraudEdge && !isCircularEdge ? [5, 5] : false,
                    arrows: { to: { enabled: true, scaleFactor: isCircularEdge ? 0.8 : 0.5 } },
                    smooth: { type: 'curvedCW', roundness: isCircularEdge ? 0.25 : 0.15 },
                    _circular: isCircularEdge,
                }
            })

            nodesRef.current.clear()
            edgesRef.current.clear()
            nodesRef.current.add(visNodes)
            edgesRef.current.add(visEdges)
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
                const nodeId = params.nodes[0]
                const node = nodesRef.current.get(nodeId)
                setSelected(node)
            } else {
                setSelected(null)
            }
        })

        network.on('stabilized', () => { setStabilized(true) })

        return () => network.destroy()
    }, [])

    const zoomIn = () => networkRef.current?.moveTo({ scale: networkRef.current.getScale() * 1.3, animation: { duration: 300 } })
    const zoomOut = () => networkRef.current?.moveTo({ scale: networkRef.current.getScale() * 0.7, animation: { duration: 300 } })
    const resetView = () => networkRef.current?.fit({ animation: { duration: 500, easingFunction: 'easeInOutQuad' } })
    const rearrange = () => {
        setStabilized(false)
        networkRef.current?.stabilize(200)
    }

    const focusNode = () => {
        if (!searchNode) return
        const found = nodesRef.current.get({
            filter: n => (n.label || '').toLowerCase().includes(searchNode.toLowerCase())
        })
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
        link.download = `gst-graph-${gstin}.png`
        link.href = canvas.toDataURL('image/png')
        link.click()
    }

    const exportPDF = () => {
        const canvas = containerRef.current?.querySelector('canvas')
        if (!canvas) return
        const imgData = canvas.toDataURL('image/png')
        const pdf = new jsPDF({
            orientation: canvas.width > canvas.height ? 'landscape' : 'portrait',
            unit: 'px',
            format: [canvas.width, canvas.height],
        })
        pdf.addImage(imgData, 'PNG', 0, 0, canvas.width, canvas.height)
        // Add title
        pdf.setFontSize(14)
        pdf.setTextColor(30, 41, 59)
        pdf.text(`GST Knowledge Graph — ${gstin}`, 20, 24)
        pdf.setFontSize(9)
        pdf.setTextColor(100, 116, 139)
        pdf.text(`${stats.nodes} nodes, ${stats.edges} edges | Depth: ${depth} | Generated: ${new Date().toLocaleString()}`, 20, 40)
        pdf.save(`gst-graph-${gstin}.pdf`)
    }

    return (
        <div className="space-y-4 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800">Knowledge Graph</h2>
                    <p className="text-sm text-slate-500 mt-0.5">
                        {stats.nodes} nodes, {stats.edges} edges — Depth: {depth}
                        {circularCount > 0 && <span className="text-red-600 font-semibold ml-2">| {circularCount} entities in circular trades</span>}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {circularCount > 0 && (
                        <button onClick={() => setShowCircularOnly(!showCircularOnly)}
                            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${showCircularOnly ? 'bg-red-600 text-white shadow-md' : 'bg-red-50 text-red-700 border border-red-200 hover:bg-red-100'}`}>
                            <GitBranch size={13} /> Circular Trades
                        </button>
                    )}
                    <button onClick={exportPDF} className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-xs font-medium transition-all shadow-sm">
                        <FileText size={13} /> Export PDF
                    </button>
                    <button onClick={exportPNG} className="flex items-center gap-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 px-3 py-2 rounded-lg text-xs font-medium transition-all">
                        <Download size={13} /> Export PNG
                    </button>
                </div>
            </div>

            {/* Circular Trade Alert Banner */}
            {circularCount > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
                        <AlertTriangle size={20} className="text-red-600" />
                    </div>
                    <div>
                        <h4 className="text-sm font-bold text-red-800">Circular Trade Network Detected</h4>
                        <p className="text-xs text-red-600 mt-0.5">
                            {circularCount} GSTIN entities are involved in circular trading patterns (A→B→C→A).
                            These are highlighted in <span className="font-bold text-red-700">RED</span> on the graph with thick red edges.
                            Circular trades are used to fraudulently inflate ITC claims.
                        </p>
                    </div>
                </div>
            )}

            {/* Controls Bar */}
            <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-sm flex items-center gap-4 flex-wrap">
                {/* Depth */}
                <div className="flex items-center gap-2">
                    <label className="text-xs font-semibold text-slate-500">Depth</label>
                    <div className="flex items-center gap-1">
                        {[1, 2, 3, 4].map(d => (
                            <button key={d} onClick={() => setDepth(d)}
                                className={`w-7 h-7 rounded-md text-xs font-bold transition-all ${d === depth ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'}`}>
                                {d}
                            </button>
                        ))}
                    </div>
                </div>

                <div className="w-px h-6 bg-slate-200" />

                {/* Zoom */}
                <div className="flex items-center gap-1">
                    <button onClick={zoomIn} className="w-7 h-7 rounded-md bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"><ZoomIn size={13} /></button>
                    <button onClick={zoomOut} className="w-7 h-7 rounded-md bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"><ZoomOut size={13} /></button>
                    <button onClick={resetView} className="w-7 h-7 rounded-md bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"><Maximize size={13} /></button>
                    <button onClick={rearrange} className="w-7 h-7 rounded-md bg-slate-100 hover:bg-slate-200 flex items-center justify-center transition-colors"><RotateCcw size={13} /></button>
                </div>

                <div className="w-px h-6 bg-slate-200" />

                {/* Search */}
                <div className="relative flex items-center">
                    <input value={searchNode} onChange={e => setSearchNode(e.target.value)} onKeyDown={e => e.key === 'Enter' && focusNode()}
                        placeholder="Find node..." className="w-40 pl-3 pr-8 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:ring-2 focus:ring-blue-200 outline-none" />
                    <button onClick={focusNode} className="absolute right-1.5"><Search size={12} className="text-slate-400" /></button>
                </div>

                <div className="flex-1" />

                {/* Status */}
                {loading ? (
                    <span className="text-xs text-blue-500 font-medium animate-pulse">Loading graph...</span>
                ) : stabilized ? (
                    <span className="flex items-center gap-1.5 text-xs text-green-600 font-medium"><span className="w-1.5 h-1.5 rounded-full bg-green-500" /> Stable</span>
                ) : (
                    <span className="flex items-center gap-1.5 text-xs text-amber-500 font-medium"><span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" /> Stabilizing...</span>
                )}
            </div>

            {/* Graph + Legend + Info Panel */}
            <div className="grid grid-cols-[1fr_240px] gap-4">
                {/* Graph Canvas */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden relative" style={{ height: '540px' }}>
                    <div ref={containerRef} className="w-full h-full" />
                    {loading && (
                        <div className="absolute inset-0 bg-white/80 flex items-center justify-center z-10">
                            <div className="flex flex-col items-center gap-2">
                                <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
                                <span className="text-sm text-slate-500">Rendering graph...</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Right Panel */}
                <div className="space-y-4">
                    {/* Legend */}
                    <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                            <Layers size={12} /> Node Types
                        </h4>
                        <div className="space-y-1.5">
                            {Object.entries(showTypes).sort((a, b) => b[1] - a[1]).map(([type, count]) => {
                                const c = NODE_COLORS[type] || NODE_COLORS.Default
                                return (
                                    <div key={type} className="flex items-center gap-2 text-xs">
                                        <span className="w-3.5 h-3.5 rounded-sm flex-shrink-0" style={{ backgroundColor: c.bg }} />
                                        <span className="text-slate-600 flex-1">{type}</span>
                                        <span className="text-slate-400 font-mono">{count}</span>
                                    </div>
                                )
                            })}
                        </div>
                        {/* Edge Legend */}
                        <div className="border-t border-slate-100 mt-3 pt-3">
                            <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Edge Types</h4>
                            <div className="space-y-1.5">
                                <div className="flex items-center gap-2 text-xs">
                                    <div className="w-6 h-0.5 bg-red-600 rounded flex-shrink-0" style={{ height: '4px' }} />
                                    <span className="text-red-600 font-semibold">Circular Trade</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <div className="w-6 flex-shrink-0" style={{ borderTop: '2px dashed #ef4444' }} />
                                    <span className="text-red-500">Fraud Link</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <div className="w-6 h-0.5 bg-slate-300 rounded flex-shrink-0" />
                                    <span className="text-slate-500">Normal</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Selected Node Info */}
                    {selected && (
                        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm animate-slide-in">
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                                    <Info size={12} /> Node Details
                                </h4>
                                <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-600"><X size={14} /></button>
                            </div>
                            <div className="space-y-2">
                                <div className="flex items-center gap-2 mb-2">
                                    <span className="w-4 h-4 rounded" style={{ backgroundColor: (NODE_COLORS[selected._type] || NODE_COLORS.Default).bg }} />
                                    <span className="text-sm font-semibold text-slate-800">{selected._type}</span>
                                    {selected._circular && (
                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-100 text-red-700 font-bold">CIRCULAR</span>
                                    )}
                                </div>
                                <p className="text-xs font-mono text-blue-600 break-all">{selected.label}</p>
                                <div className="border-t border-slate-100 pt-2 space-y-1.5 max-h-[250px] overflow-y-auto">
                                    {Object.entries(selected._props || {}).filter(([k]) => !k.startsWith('_')).slice(0, 20).map(([k, v]) => (
                                        <div key={k} className="flex justify-between gap-2 text-[11px]">
                                            <span className="text-slate-400 truncate">{k}</span>
                                            <span className="text-slate-700 font-medium text-right truncate max-w-[120px]">{String(v)}</span>
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
