import {
  Button, Dropdown, FileUploader, InlineNotification, Loading, Modal, OverflowMenu, OverflowMenuItem, Tab, TabList,
  TabPanel, TabPanels, Tabs,
} from '@carbon/react'
import { Renew, StopFilled } from '@carbon/icons-react'
import { useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useCancelRun, useImportSpec, useProject, useRegenerate, useRuns, useStartRun } from '../api/hooks'
import { useProjectEvents } from '../api/sse'
import type { ApiEvent } from '../api/types'
import { LogViewer } from '../components/LogViewer'
import { StagePanel } from '../components/StagePanel'
import { StageTimeline } from '../components/StageTimeline'
import { StatusTag } from '../components/StatusTag'
import { applyEvent, stageLabel } from '../lib/runState'

const TABS = ['pipeline', 'logs', 'review', 'editor', 'outputs', 'versions']
const TAB_LABELS = ['Pipeline', 'Logs', 'Review', 'Editor', 'Outputs', 'Versions']

export function ProjectDetailPage({ outputsTab, versionsTab }: {
  outputsTab?: (id: string) => React.ReactNode
  versionsTab?: (id: string) => React.ReactNode
}) {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = Math.max(TABS.indexOf(params.get('tab') ?? 'pipeline'), 0)
  const { data: project, isLoading } = useProject(id)
  const { data: runs = [] } = useRuns(id)
  const regenerate = useRegenerate(id)
  const startRun = useStartRun(id)
  const cancel = useCancelRun(id)
  const importSpec = useImportSpec(id)
  const [events, setEvents] = useState<ApiEvent[]>([])
  const [selected, setSelected] = useState(0)
  const [importOpen, setImportOpen] = useState(false)
  const [fromStageOpen, setFromStageOpen] = useState(false)
  const [fromStage, setFromStage] = useState(1)
  const [error, setError] = useState<string | null>(null)

  useProjectEvents(id, (e) => {
    setEvents((prev) => (prev.length && prev[prev.length - 1].seq >= e.seq ? prev : [...prev, e]))
    if (e.type === 'stage.started' && e.stage !== null) setSelected(e.stage)
  })
  // the stored run plus live events (replaying already-applied events is idempotent)
  const latest = project?.latest_run ?? null
  const run = useMemo(() => (latest ? events.reduce(applyEvent, latest) : null), [latest, events])

  if (isLoading || !project) return <Loading withOverlay={false} description="Memuat project" />
  const active = run && (run.status === 'queued' || run.status === 'running')
  const fail = (e: unknown) => setError(e instanceof ApiError ? e.message : String(e))

  return (
    <>
      <div className="detail-head">
        <div>
          <h1 className="page-title">{project.name}</h1>
          <div className="detail-meta">
            {run ? <StatusTag status={run.status} /> : <StatusTag status="new" />}
            <span className="mono">HEAD {project.head ? `v${project.head}` : '—'}</span>
            <span className="mono helper">{project.project_id}</span>
          </div>
        </div>
        <div className="detail-actions">
          <Button kind="tertiary" size="md" onClick={() => setImportOpen(true)}>Impor spec</Button>
          <OverflowMenu aria-label="Jalankan ulang" renderIcon={() => <span className="overflow-label">Jalankan ulang ▾</span>} size="lg" flipped>
            <OverflowMenuItem itemText="Full (0–10)" onClick={() => startRun.mutate({ kind: 'full' }, { onError: fail })} />
            <OverflowMenuItem itemText="Dari tahap…" onClick={() => setFromStageOpen(true)} />
          </OverflowMenu>
          <Button renderIcon={Renew} disabled={!project.head || !!active}
            onClick={() => regenerate.mutate('HEAD', { onError: fail })}>Regenerate</Button>
          {active && run && <Button kind="danger" renderIcon={StopFilled} onClick={() => cancel.mutate(run.run_id, { onError: fail })}>Batalkan run</Button>}
        </div>
      </div>
      {error && <InlineNotification kind="error" title="Gagal" subtitle={error} lowContrast onClose={() => setError(null)} />}
      {regenerate.data?.reused && <InlineNotification kind="info" title="Output sudah ada" subtitle="Versi ini sudah dibangun; output dipakai ulang." lowContrast />}

      <Tabs selectedIndex={tab} onChange={({ selectedIndex }) => setParams({ tab: TABS[selectedIndex] })}>
        <TabList aria-label="Bagian project">{TAB_LABELS.map((t) => <Tab key={t}>{t}</Tab>)}</TabList>
        <TabPanels>
          <TabPanel>
            {run ? (
              <div className="pipeline-grid">
                <StageTimeline run={run} selected={selected} onSelect={setSelected} />
                <StagePanel projectId={id} run={run} n={selected} events={events} onOpenEditor={() => setParams({ tab: 'editor' })} />
              </div>
            ) : (
              <p className="helper">Belum ada run. Impor spec lalu tekan Regenerate, atau jalankan pipeline penuh.</p>
            )}
          </TabPanel>
          <TabPanel><LogViewer projectId={id} runs={runs} events={events} /></TabPanel>
          <TabPanel><p className="helper">Overlay bernomor dan keputusan Strata tersedia di M5/M6.</p></TabPanel>
          <TabPanel><p className="helper">Web editor tersedia di M4.</p></TabPanel>
          <TabPanel>{outputsTab?.(id)}</TabPanel>
          <TabPanel>{versionsTab?.(id)}</TabPanel>
        </TabPanels>
      </Tabs>

      <Modal open={importOpen} modalHeading="Impor spec" primaryButtonText="Tutup" passiveModal onRequestClose={() => setImportOpen(false)}>
        <FileUploader labelTitle="File spec (.json)" labelDescription="Spec utuh, mis. benchmarks/gatsu/gt_spec.json"
          buttonLabel="Pilih file" accept={['.json']} filenameStatus="edit"
          onChange={async (e) => {
            const f = (e.target as HTMLInputElement).files?.[0]
            if (!f) return
            importSpec.mutate(await f.text(), { onSuccess: () => setImportOpen(false), onError: fail })
          }} />
      </Modal>
      <Modal open={fromStageOpen} modalHeading="Jalankan ulang dari tahap" primaryButtonText="Jalankan" secondaryButtonText="Batal"
        onRequestClose={() => setFromStageOpen(false)}
        onRequestSubmit={() => { startRun.mutate({ kind: 'from_stage', from_stage: fromStage }, { onError: fail }); setFromStageOpen(false) }}>
        <Dropdown id="from-stage" titleText="Tahap" label="Tahap" items={Array.from({ length: 10 }, (_, i) => i + 1)}
          itemToString={(n) => (n === null ? '' : `${n} · ${stageLabel(n)}`)} selectedItem={fromStage}
          onChange={({ selectedItem }) => setFromStage(selectedItem ?? 1)} />
      </Modal>
    </>
  )
}
