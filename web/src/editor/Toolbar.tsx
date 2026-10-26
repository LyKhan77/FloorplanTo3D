import {
  Area, AreaCustom, ArrowsVertical, Cube, Cursor_1, Map, Pedestrian, Redo, Renew, RightPanelClose, RightPanelOpen,
  Ruler, Save, SidePanelClose, SidePanelOpen, Undo,
} from '@carbon/icons-react'
import { Button, Checkbox, ProgressBar } from '@carbon/react'
import { useState, type ComponentType } from 'react'
import { AUTO_REGENERATE_KEY, autoRegenerate } from './useSave'
import { useEditorStore, type Mode, type Tool } from './store'

const MODES: [Mode, string, ComponentType][] = [['orbit', 'Orbit', Cube], ['top', 'Top', Map], ['walk', 'Walk', Pedestrian]]
const TOOLS: [Tool, string, ComponentType][] = [
  ['select', 'Select', Cursor_1], ['distance', 'Ukur jarak', Ruler], ['room-area', 'Luas ruang', Area],
  ['area', 'Luas bebas', AreaCustom], ['height', 'Ukur tinggi', ArrowsVertical],
]

interface Props {
  left: boolean
  right: boolean
  onToggleLeft(): void
  onToggleRight(): void
  onSave?: () => void
  onRegenerate?: () => void
  saving?: boolean
  regen?: { running: boolean; progress: number | null; stage: string | null }
}

function Toggle({ label, icon, active, onClick }: { label: string; icon: ComponentType; active: boolean; onClick(): void }) {
  return (
    <Button kind={active ? 'secondary' : 'ghost'} size="sm" hasIconOnly renderIcon={icon} iconDescription={label}
      tooltipPosition="bottom" aria-pressed={active} onClick={onClick} />
  )
}

export function Toolbar({ left, right, onToggleLeft, onToggleRight, onSave, onRegenerate, saving, regen }: Props) {
  const [auto, setAuto] = useState(autoRegenerate)
  const { mode, tool, snap, ops, past, future, baseVersion, setMode, setTool, setSnap, undo, redo } = useEditorStore()
  return (
    <div className="editor__toolbar" role="toolbar" aria-label="Toolbar editor">
      <Toggle label={left ? 'Sembunyikan panel kiri' : 'Tampilkan panel kiri'} icon={left ? SidePanelClose : SidePanelOpen}
        active={false} onClick={onToggleLeft} />
      <span className="editor__group">{MODES.map(([m, label, icon]) => <Toggle key={m} label={label} icon={icon} active={mode === m} onClick={() => setMode(m)} />)}</span>
      <span className="editor__group">{TOOLS.map(([t, label, icon]) => <Toggle key={t} label={label} icon={icon} active={tool === t} onClick={() => setTool(t)} />)}</span>
      <Checkbox id="editor-snap" labelText="Snap 600" checked={snap} onChange={(_, { checked }) => setSnap(checked)} />
      <span className="editor__group">
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={Undo} iconDescription="Undo (Ctrl+Z)" tooltipPosition="bottom" disabled={!past.length} onClick={undo} />
        <Button kind="ghost" size="sm" hasIconOnly renderIcon={Redo} iconDescription="Redo (Ctrl+Shift+Z)" tooltipPosition="bottom" disabled={!future.length} onClick={redo} />
      </span>
      <span className="editor__version mono">{baseVersion === null ? '—' : `v${baseVersion}`}{ops.length ? ` (unsaved: ${ops.length})` : ''}</span>
      <span className="editor__spacer" />
      {regen?.progress != null && (
        <ProgressBar className="editor__progress" size="small" label={regen.stage ?? 'regenerate'} value={regen.progress} max={100}
          helperText={`${Math.round(regen.progress)}%`} />
      )}
      <Button size="sm" kind="primary" renderIcon={Save} disabled={!onSave || !ops.length || saving} onClick={onSave}>
        {saving ? 'Menyimpan…' : 'Save'}
      </Button>
      <Button size="sm" kind="tertiary" renderIcon={Renew} disabled={!onRegenerate || !!ops.length || regen?.running}
        title={ops.length ? 'Save dulu' : undefined} onClick={onRegenerate}>Regenerate</Button>
      <Checkbox id="editor-auto-regen" labelText="Regenerate otomatis setelah Save" checked={auto}
        onChange={(_, { checked }) => {
          setAuto(checked)
          try { localStorage.setItem(AUTO_REGENERATE_KEY, checked ? '1' : '0') } catch { /* private mode: keep the session choice */ }
        }} />
      <Toggle label={right ? 'Sembunyikan panel kanan' : 'Tampilkan panel kanan'} icon={right ? RightPanelClose : RightPanelOpen}
        active={false} onClick={onToggleRight} />
    </div>
  )
}
