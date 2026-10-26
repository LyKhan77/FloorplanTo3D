import {
  Accordion, AccordionItem, Button, Dropdown, FileUploaderDropContainer, FileUploaderItem, Form, InlineNotification,
  NumberInput, Stack, TextArea, TextInput, Toggle,
} from '@carbon/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useCreateProject, useProfiles } from '../api/hooks'
import { buildProjectForm } from '../lib/params'

const SITE_TYPES = ['data_hall', 'data_center', 'office', 'mixed', 'other']
const MAX_MB = 50

export function NewProjectPage() {
  const navigate = useNavigate()
  const create = useCreateProject()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [wallHeight, setWallHeight] = useState<number | null>(null)
  const [doorHeight, setDoorHeight] = useState<number | null>(null)
  const [wallThickness, setWallThickness] = useState<number | null>(null)
  const [floorName, setFloorName] = useState('')
  const [siteType, setSiteType] = useState('')
  const [mmPerPx, setMmPerPx] = useState('')
  const [useStrata, setUseStrata] = useState(true)
  const [profileId, setProfileId] = useState<string | null>(null)
  const { data: profiles = [] } = useProfiles()
  const [error, setError] = useState<string | null>(null)

  const pick = (files: File[]) => {
    const f = files[0]
    if (!f) return
    if (f.size > MAX_MB * 1024 * 1024) return setError(`File melebihi ${MAX_MB} MB`)
    setError(null)
    setFile(f)
    if (!name) setName(f.name.replace(/\.[^.]+$/, ''))
    setPreview(f.type.startsWith('image/') ? URL.createObjectURL(f) : null)
  }

  const submit = (start: boolean) => {
    if (!file) return setError('Pilih file denah terlebih dahulu')
    try {
      const form = buildProjectForm(file, {
        name, prompt, wallHeight, doorHeight, wallThickness, floorName, siteType,
        mmPerPx: mmPerPx ? Number(mmPerPx) : null, useStrata, profileId, start,
      })
      create.mutate(form, {
        onSuccess: (r) => navigate(`/projects/${r.project_id}?tab=pipeline`),
        onError: (e) => setError(e instanceof ApiError ? e.message : String(e)),
      })
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="narrow-form">
      <h1 className="page-title">Project baru</h1>
      <Form onSubmit={(e) => { e.preventDefault(); submit(true) }}>
        <Stack gap={6}>
          {error && <InlineNotification kind="error" title="Gagal" subtitle={error} lowContrast onClose={() => setError(null)} />}
          <div>
            <p className="cds--file--label">File denah</p>
            <p className="cds--label-description">JPEG, PNG, atau PDF, maksimal {MAX_MB} MB.</p>
            <FileUploaderDropContainer accept={['.jpg', '.jpeg', '.png', '.pdf']} labelText="Seret file ke sini atau klik untuk memilih"
              onAddFiles={(_e, { addedFiles }) => pick(addedFiles)} />
            {file && <FileUploaderItem name={file.name} status="edit" onDelete={() => { setFile(null); setPreview(null) }} />}
            {preview && <img src={preview} alt="Pratinjau denah" className="upload-preview" />}
          </div>
          <TextInput id="name" labelText="Nama project" value={name} onChange={(e) => setName(e.target.value)} />
          <TextArea id="prompt" labelText="Prompt" placeholder="Data hall lantai 1, tinggi dinding 4.5 m, pintu 2.4 m"
            value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} />
          <Accordion>
            <AccordionItem title="Parameter lanjutan">
              <Stack gap={5}>
                <NumberInput id="wall-height" label="Tinggi dinding (mm)" min={1} allowEmpty value={wallHeight ?? ''}
                  onChange={(_e, { value }) => setWallHeight(value === '' ? null : Number(value))} />
                <NumberInput id="door-height" label="Tinggi pintu (mm)" min={1} allowEmpty value={doorHeight ?? ''}
                  onChange={(_e, { value }) => setDoorHeight(value === '' ? null : Number(value))} />
                <NumberInput id="wall-thickness" label="Tebal dinding default (mm)" min={1} allowEmpty value={wallThickness ?? ''}
                  onChange={(_e, { value }) => setWallThickness(value === '' ? null : Number(value))} />
                <TextInput id="floor" labelText="Nama lantai" value={floorName} onChange={(e) => setFloorName(e.target.value)} />
                <Dropdown id="site-type" titleText="Tipe site" label="Pilih tipe site" items={SITE_TYPES}
                  selectedItem={siteType || null} onChange={({ selectedItem }) => setSiteType(selectedItem ?? '')} />
                <TextInput id="scale" labelText="Skala manual (mm per px)" helperText="Kosongkan agar dihitung dari grid dan dimensi"
                  value={mmPerPx} onChange={(e) => setMmPerPx(e.target.value)} />
                <Toggle id="strata" labelText="Gunakan Strata" toggled={useStrata} onToggle={setUseStrata} />
                <Dropdown id="profile" titleText="Profile (opsional)" label="Tanpa profile" helperText="Sweep dimulai dari parameter profile"
                  items={[null, ...profiles.map((p) => p.profile_id)]}
                  itemToString={(pid) => (pid ? profiles.find((p) => p.profile_id === pid)?.name ?? pid : 'Tanpa profile')}
                  selectedItem={profileId} onChange={({ selectedItem }) => setProfileId(selectedItem ?? null)} />
              </Stack>
            </AccordionItem>
          </Accordion>
          <div className="form-actions">
            <Button type="submit" disabled={create.isPending}>Mulai pipeline</Button>
            <Button kind="secondary" disabled={create.isPending} onClick={() => submit(false)}>Buat tanpa menjalankan</Button>
            <Button kind="ghost" onClick={() => navigate('/projects')}>Batal</Button>
          </div>
        </Stack>
      </Form>
    </div>
  )
}
