// 简化的布局实现，避免 elkjs 的 web-worker 依赖问题
export interface LayoutNode {
  id: string
  width?: number
  height?: number
  x?: number
  y?: number
  children?: LayoutNode[]
}

export interface LayoutEdge {
  id: string
  sources: string[]
  targets: string[]
}

export interface LayoutResult {
  nodes: LayoutNode[]
  edges: LayoutEdge[]
}

export async function layoutWorkflow(nodes: LayoutNode[], edges: LayoutEdge[]): Promise<LayoutResult> {
  // 简单的网格布局实现
  const nodeWidth = 200
  const nodeHeight = 100
  const spacing = 50
  
  const layoutedNodes = nodes.map((node, index) => {
    const row = Math.floor(index / 4) // 每行4个节点
    const col = index % 4
    
    return {
      ...node,
      width: node.width || nodeWidth,
      height: node.height || nodeHeight,
      x: col * (nodeWidth + spacing),
      y: row * (nodeHeight + spacing),
    }
  })
  
  return {
    nodes: layoutedNodes,
    edges,
  }
}

export default layoutWorkflow
