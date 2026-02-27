import React, { useEffect, useRef, useState } from 'react'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'
import { getGraphData } from '../api'

const NODE_COLORS = {
    GSTIN: '#3b82f6',
    Invoice: '#f59e0b',
    Return: '#22c55e',
    IRN: '#8b5cf6',
    EWayBill: '#ec4899',
    LineItem: '#6b7280',
    BankTransaction: '#14b8a6',
    PurchaseRegisterEntry: '#f97316',
    Taxpayer: '#1e3a5f',
}

export default function GraphVisualization({ gstin }) {
    const containerRef = useRef(null)
    const networkRef = useRef(null)
    const [depth, setDepth] = useState(2)
    const [loading, setLoading] = useState(false)
    const [stats, setStats] = useState({ nodes: 0, edges: 0 })

    useEffect(() => {
        if (!gstin) return
        setLoading(true)
        getGraphData(gstin, depth)
            .then(r => {
                const { nodes: rawNodes, edges: rawEdges } = r.data
                setStats({ nodes: rawNodes.length, edges: rawEdges.length })

                const nodes = new DataSet(
                    rawNodes.map(n => ({
                        id: n.id,
                        label: n.label?.length > 20 ? n.label.slice(0, 17) + '...' : n.label,
                        title: `${n.type}: ${n.label}`,
                        color: NODE_COLORS[n.type] || '#94a3b8',
                        shape: n.type === 'GSTIN' ? 'diamond' : n.type === 'Invoice' ? 'box' : 'dot',
                        size: n.type === 'GSTIN' ? 30 : 20,
                        font: { color: '#fff', size: 10 },
                    }))
                )

                const edges = new DataSet(
                    rawEdges.map((e, i) => ({
                        id: `e-${i}`,
                        from: e.from,
                        to: e.to,
                        label: e.label,
                        arrows: 'to',
                        font: { size: 8, color: '#9ca3af' },
                        color: { color: '#d1d5db', hover: '#3b82f6' },
                    }))
                )

                if (networkRef.current) networkRef.current.destroy()

                networkRef.current = new Network(containerRef.current, { nodes, edges }, {
                    physics: {
                        solver: 'forceAtlas2Based',
                        forceAtlas2Based: { gravitationalConstant: -80, springLength: 150 },
                        stabilization: { iterations: 200 },
                    },
                    interaction: { hover: true, tooltipDelay: 200, zoomView: true },
                    layout: { improvedLayout: true },
                })
            })
            .catch(() => { })
            .finally(() => setLoading(false))

        return () => { if (networkRef.current) networkRef.current.destroy() }
    }, [gstin, depth])

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-800">Knowledge Graph Explorer</h2>
                <div className="flex items-center gap-3 text-sm">
                    <label className="text-gray-600">Depth:</label>
                    <input
                        type="range" min={1} max={4} value={depth}
                        onChange={e => setDepth(Number(e.target.value))}
                        className="w-32"
                    />
                    <span className="w-6 text-center font-mono">{depth}</span>
                    <span className="text-gray-400 ml-4">{stats.nodes} nodes · {stats.edges} edges</span>
                </div>
            </div>

            {/* Legend */}
            <div className="flex gap-4 text-xs">
                {Object.entries(NODE_COLORS).map(([type, color]) => (
                    <div key={type} className="flex items-center gap-1.5">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                        <span className="text-gray-600">{type}</span>
                    </div>
                ))}
            </div>

            {/* Graph Canvas */}
            <div className="bg-white rounded-xl shadow-sm border relative" style={{ height: '600px' }}>
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
                        <span className="text-gray-500">Loading graph...</span>
                    </div>
                )}
                <div ref={containerRef} className="w-full h-full" />
            </div>
        </div>
    )
}
