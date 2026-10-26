import { TextInput } from '@carbon/react'
import { useState } from 'react'

interface Props {
  id: string
  label: string
  value: number | null | undefined
  min?: number
  max?: number
  onCommit(mm: number): void
}

/** Integer mm field; commits on blur or Enter, rejects empty or out-of-range input inline without emitting an op. */
export function MmInput(props: Props) {
  // a new value from the store (undo, another edit) restarts the field
  return <MmField key={String(props.value)} {...props} />
}

function MmField({ id, label, value, min = 1000, max = 12000, onCommit }: Props) {
  const [text, setText] = useState(value == null ? '' : String(value))
  const [touched, setTouched] = useState(false)
  const n = Number(text)
  const valid = text.trim() !== '' && Number.isFinite(n) && n >= min && n <= max
  const commit = () => {
    setTouched(true)
    if (valid && Math.round(n) !== value) onCommit(Math.round(n))
  }
  return (
    <TextInput id={id} labelText={label} size="sm" inputMode="numeric" value={text} onChange={(e) => setText(e.target.value)}
      onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') commit() }}
      invalid={touched && !valid} invalidText={`Isi ${min}–${max} mm`} />
  )
}
