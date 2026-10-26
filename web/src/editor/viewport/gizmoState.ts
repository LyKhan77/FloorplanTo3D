/** Gizmo drag state shared with the marquee and click handlers (the click that ends a gizmo drag selects nothing). */
export const gizmoState = { dragging: false, endedAt: 0 }

export const justDragged = () => gizmoState.dragging || performance.now() - gizmoState.endedAt < 300
