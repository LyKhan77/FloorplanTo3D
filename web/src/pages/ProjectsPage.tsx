import {
  Button, DataTable, DataTableSkeleton, Modal, OverflowMenu, OverflowMenuItem, Pagination, Table, TableBody,
  TableCell, TableContainer, TableHead, TableHeader, TableRow, TableToolbar, TableToolbarContent, TableToolbarSearch,
} from '@carbon/react'
import { Add } from '@carbon/icons-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useDeleteProject, useProjects } from '../api/hooks'
import { StatusTag } from '../components/StatusTag'
import { formatTime } from '../lib/format'
import { stageLabel } from '../lib/runState'

const HEADERS = [
  { key: 'name', header: 'Nama' },
  { key: 'floor', header: 'Lantai' },
  { key: 'status', header: 'Status' },
  { key: 'active_stage', header: 'Tahap aktif' },
  { key: 'validator_score', header: 'Skor validator' },
  { key: 'fit', header: 'Cocok gambar' },
  { key: 'head_version', header: 'Versi' },
  { key: 'updated_at', header: 'Diperbarui' },
]

export function ProjectsPage() {
  const { data, isLoading } = useProjects()
  const del = useDeleteProject()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)
  const [toDelete, setToDelete] = useState<string | null>(null)
  const items = useMemo(() => data?.items ?? [], [data])
  const rows = items.map((p) => ({ ...p, id: p.project_id }))

  if (isLoading) return <DataTableSkeleton headers={HEADERS} aria-label="Memuat project" />

  return (
    <>
      <h1 className="page-title">Projects</h1>
      {items.length === 0 ? (
        <div className="empty-state">
          <p>Belum ada project. Upload denah untuk memulai.</p>
          <Button renderIcon={Add} onClick={() => navigate('/projects/new')}>Upload denah pertama</Button>
        </div>
      ) : (
        <DataTable rows={rows} headers={HEADERS} isSortable>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps, onInputChange }) => (
            <TableContainer>
              <TableToolbar>
                <TableToolbarContent>
                  <TableToolbarSearch onChange={(e) => onInputChange(e as React.ChangeEvent<HTMLInputElement>)} placeholder="Cari project" persistent />
                  <Button renderIcon={Add} onClick={() => navigate('/projects/new')}>Project baru</Button>
                </TableToolbarContent>
              </TableToolbar>
              <Table {...getTableProps()} aria-label="Daftar project">
                <TableHead>
                  <TableRow>
                    {headers.map((h) => {
                      const { key, ...props } = getHeaderProps({ header: h })
                      return <TableHeader key={key} {...props}>{h.header}</TableHeader>
                    })}
                    <TableHeader aria-label="Aksi" />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tableRows.slice((page - 1) * size, page * size).map((row) => {
                    const p = items.find((i) => i.project_id === row.id)!
                    const { key, ...rowProps } = getRowProps({ row })
                    return (
                      <TableRow key={key} {...rowProps}>
                        <TableCell><Link to={`/projects/${p.project_id}`}>{p.name}</Link></TableCell>
                        <TableCell>{p.floor ?? '—'}</TableCell>
                        <TableCell><StatusTag status={p.status} /></TableCell>
                        <TableCell>{p.active_stage === null ? '—' : stageLabel(p.active_stage)}</TableCell>
                        <TableCell className="mono">{p.validator_score ?? '—'}</TableCell>
                        <TableCell className="mono" title={p.fit == null && p.iou != null ? `Output lama: IoU ${p.iou} (ukuran lain), regenerate untuk kecocokan gambar` : undefined}>{p.fit ?? '—'}</TableCell>
                        <TableCell className="mono">{p.head_version ? `v${p.head_version}` : '—'}</TableCell>
                        <TableCell>{formatTime(p.updated_at)}</TableCell>
                        <TableCell className="cds--table-column-menu">
                          <OverflowMenu size="sm" flipped aria-label={`Aksi untuk ${p.name}`}>
                            <OverflowMenuItem itemText="Buka" onClick={() => navigate(`/projects/${p.project_id}`)} />
                            <OverflowMenuItem itemText="Jalankan ulang" onClick={() => api.post(`/api/projects/${p.project_id}/runs`, { kind: 'full' })} />
                            <OverflowMenuItem itemText="Regenerate" onClick={() => api.post(`/api/projects/${p.project_id}/regenerate`, { version: 'HEAD' })} />
                            <OverflowMenuItem itemText="Hapus" isDelete hasDivider onClick={() => setToDelete(p.project_id)} />
                          </OverflowMenu>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
              <Pagination page={page} pageSize={size} pageSizes={[10, 25, 50]} totalItems={tableRows.length}
                onChange={({ page: p, pageSize }) => { setPage(p); setSize(pageSize) }} />
            </TableContainer>
          )}
        </DataTable>
      )}
      <Modal open={toDelete !== null} danger modalHeading="Hapus project?" primaryButtonText="Hapus" secondaryButtonText="Batal"
        onRequestClose={() => setToDelete(null)}
        onRequestSubmit={() => { if (toDelete) del.mutate(toDelete); setToDelete(null) }}>
        <p>Project, run, spec, dan output akan dihapus permanen.</p>
      </Modal>
    </>
  )
}
