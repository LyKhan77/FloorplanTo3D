import { Button, Dropdown, TextInput } from '@carbon/react'
import { useState } from 'react'

const REASONS = ['garis anotasi', 'duplikat', 'bukan dinding', 'lainnya']

/** Geometry deletes need a reason (provenance log); "lainnya" asks for free text. */
export function DeleteWithReason({ id, label, onDelete }: { id: string; label: string; onDelete(reason: string): void }) {
  const [choice, setChoice] = useState<string | null>(null)
  const [other, setOther] = useState('')
  const reason = choice === 'lainnya' ? other.trim() : choice ?? ''
  return (
    <div className="editor-delete">
      <Dropdown id={`${id}-reason`} titleText="Alasan hapus" label="Pilih alasan" size="sm" items={REASONS} selectedItem={choice}
        onChange={({ selectedItem }) => setChoice(selectedItem ?? null)} />
      {choice === 'lainnya' && (
        <TextInput id={`${id}-other`} labelText="Alasan lain" size="sm" value={other} onChange={(e) => setOther(e.target.value)} />
      )}
      <Button kind="danger--tertiary" size="sm" disabled={!reason} onClick={() => onDelete(reason)}>{label}</Button>
    </div>
  )
}
