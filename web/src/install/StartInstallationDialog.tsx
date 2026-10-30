import { Checkbox, Modal, NumberInput, RadioButton, RadioButtonGroup } from '@carbon/react'
import { useState } from 'react'

export interface StartValues { ceiling_height: number | null; raised_floor_height: number | null; default_mounting: 'overhead' | 'underfloor' }

const num = (v: string) => (v.trim() === '' ? null : Math.round(Number(v)))

/** "Mulai instalasi": heights the layout cannot read from a 2D plan. Empty ceiling = the prompt's value, else the wall height. */
export function StartInstallationDialog({ ceiling, raised, onSubmit, onClose, busy }: {
  ceiling: number | null; raised: number | null; busy: boolean; onSubmit(v: StartValues): void; onClose(): void
}) {
  const [c, setC] = useState(ceiling === null ? '' : String(ceiling))
  const [hasRaised, setHasRaised] = useState(raised !== null)
  const [r, setR] = useState(String(raised ?? 600))
  const [mount, setMount] = useState<'overhead' | 'underfloor'>('overhead')
  return (
    <Modal open modalHeading="Mulai instalasi" primaryButtonText="Mulai" secondaryButtonText="Batal" primaryButtonDisabled={busy}
      onRequestClose={onClose} onRequestSubmit={() => onSubmit({ ceiling_height: num(c), raised_floor_height: hasRaised ? num(r) : null, default_mounting: mount })}>
      <NumberInput id="si-ceiling" label="Tinggi plafon (mm)" helperText="Kosong: dari prompt, atau tinggi dinding" allowEmpty hideSteppers
        value={c} onChange={(e) => setC((e.target as HTMLInputElement).value)} />
      <Checkbox id="si-raised" labelText="Ada raised floor" checked={hasRaised} onChange={(_, { checked }) => setHasRaised(checked)} />
      {hasRaised && (
        <NumberInput id="si-raised-h" label="Tinggi raised floor (mm)" hideSteppers value={r} onChange={(e) => setR((e.target as HTMLInputElement).value)} />
      )}
      <RadioButtonGroup legendText="Pemasangan tray default" name="si-mount" valueSelected={mount}
        onChange={(v) => setMount(v as 'overhead' | 'underfloor')}>
        <RadioButton id="si-over" labelText="Overhead (digantung dari plafon)" value="overhead" />
        <RadioButton id="si-under" labelText="Underfloor (di bawah raised floor)" value="underfloor" />
      </RadioButtonGroup>
    </Modal>
  )
}
