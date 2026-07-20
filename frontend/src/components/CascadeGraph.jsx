import { useEffect, useState } from 'react'
import { Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react'
import { AlertTriangle, ChevronRight, CircleDot, Euro, Timer, Zap } from 'lucide-react'
import { currency } from '../utils'

function LogisticsNode({ data, selected }) {
  const { node } = data
  return <div className={`flow-node ${node.health} ${selected ? 'selected' : ''}`}>
    <Handle type="target" position={Position.Left} />
    <div className="flow-node-top"><span className="node-health"><i />{node.kind}</span>{node.impact > 0 && <span className="node-impact">{currency(node.impact)}</span>}</div>
    <strong>{node.label}</strong>
    <p>{node.detail}</p>
    <div className="flow-node-footer"><Timer size={12} />{node.time_to_impact}</div>
    <Handle type="source" position={Position.Right} />
  </div>
}

const nodeTypes = { logistics: LogisticsNode }

// Nodes lay out by their role suffix (AN-xxxx-source → column 0, etc.) so
// cascades read left-to-right; unknown roles fall back to a grid.
const ROLE_COLUMNS = { source: 0, sequence: 1, plan: 1, load: 1, pick: 1, quality: 1, dock: 2, line: 2, station: 3, outcome: 2 }

const nodePosition = (node, index) => {
  const role = node.id.split('-').pop()
  const column = ROLE_COLUMNS[role]
  if (column !== undefined) return { x: 40 + column * 320, y: 165 + (index % 2) * 150 }
  return { x: 40 + (index % 3) * 320, y: 100 + Math.floor(index / 3) * 170 }
}

const toFlowNodes = (graph, activeId) => (graph?.nodes || []).map((node, index) => ({
  id: node.id, type: 'logistics',
  position: nodePosition(node, index),
  data: { node }, selected: activeId === node.id,
}))
const toFlowEdges = (graph) => (graph?.edges || []).map((edge, index) => ({
  id: `${edge.source}-${edge.target}-${index}`, source: edge.source, target: edge.target, label: `${edge.probability}%`,
  markerEnd: { type: MarkerType.ArrowClosed, color: '#d8b878' }, animated: edge.probability > 70,
  style: { stroke: edge.probability > 70 ? '#d8b878' : '#7a7390', strokeWidth: edge.probability > 70 ? 2 : 1.25 },
  labelStyle: { fill: '#e6d6b0', fontSize: 10, fontWeight: 700 }, labelBgStyle: { fill: '#221f31', fillOpacity: 0.88 },
}))

export function CascadeGraph({ graph, selectedId, onSelect, compact = false }) {
  const [activeId, setActiveId] = useState(selectedId)
  // Nodes live in ReactFlow state so drag changes actually apply; re-seed them
  // only when the underlying cascade (not the selection) changes.
  const [nodes, setNodes, onNodesChange] = useNodesState(toFlowNodes(graph, selectedId))
  const [edges, setEdges, onEdgesChange] = useEdgesState(toFlowEdges(graph))
  useEffect(() => {
    // Re-seed on graph change, but keep positions the user dragged: live events
    // refetch the graph frequently and must not snap the layout back.
    setNodes((current) => {
      const kept = new Map(current.map((node) => [node.id, node.position]))
      return toFlowNodes(graph, activeId).map((node) => kept.has(node.id) ? { ...node, position: kept.get(node.id) } : node)
    })
    setEdges(toFlowEdges(graph))
  }, [graph]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    setActiveId(selectedId)
    setNodes((current) => current.map((node) => ({ ...node, selected: node.id === selectedId })))
  }, [selectedId, setNodes])
  const selected = graph?.nodes?.find((node) => node.id === activeId) || graph?.nodes?.[0]
  const handleClick = (_, node) => { setActiveId(node.id); onSelect?.(node.data.node) }
  if (!graph?.nodes?.length) return <div className="graph-empty">No dependency path exists for this finding.</div>
  return <div className={`cascade-explorer ${compact ? 'compact' : ''}`}>
    <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} nodeTypes={nodeTypes} onNodeClick={handleClick} fitView fitViewOptions={{ padding: compact ? 0.26 : 0.16 }} minZoom={0.35} maxZoom={1.45} proOptions={{ hideAttribution: true }}>
      <Background color="#575072" gap={30} size={1} className="graph-background" />
      {!compact && <><Controls showInteractive={false} /><MiniMap nodeColor={(node) => ({ critical: '#e0808f', risk: '#d8b878', watch: '#9d94c9', healthy: '#7fc7ad' })[node.data?.node?.health] || '#9d94c9'} maskColor="rgba(16, 14, 26, .74)" /></>}
    </ReactFlow>
    {selected && <div className="graph-inspector"><span><CircleDot size={13} />Selected dependency</span><strong>{selected.label}</strong><p>{selected.detail}</p><div><b><Timer size={13} />{selected.time_to_impact}</b>{selected.impact > 0 && <b><Euro size={13} />{currency(selected.impact)}</b>}</div></div>}
  </div>
}

export function CascadeLegend() {
  return <div className="cascade-legend"><span><i className="critical" />Critical path</span><span><i className="risk" />At risk</span><span><i className="watch" />Watch</span><span><i className="healthy" />Protected</span></div>
}

export function CascadeSummary({ anomaly, onExplore }) {
  if (!anomaly) return null
  return <div className="cascade-summary">
    <div className="cascade-warning"><AlertTriangle size={18} /><span>Active cascade</span></div>
    <h3>{anomaly.title}</h3><p>{anomaly.summary}</p>
    <div className="cascade-summary-meta"><span><Zap size={15} />{anomaly.time_to_impact} to impact</span><strong>{currency(anomaly.impact)} at risk</strong></div>
    <button className="primary-button" onClick={onExplore}>Trace this cascade <ChevronRight size={16} /></button>
  </div>
}
