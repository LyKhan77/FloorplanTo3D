import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Template } from '../../api/types'
import { LibraryPanel } from './LibraryPanel'

const tpl = (id: string, name: string, category: string, tags: string[] = []): Template => ({
  id, version: '1.0.0', name, category, tags, thumbnail_url: `/t/${id}.png`, asset_url: '', dims: { w: 600, d: 1200, h: 2000 },
})
const templates = [
  tpl('rack-42u-600x1200', 'Rack 42U', 'rack', ['server']),
  tpl('crac-unit-generic', 'Crac Unit', 'cooling', ['hvac']),
  tpl('ups-cabinet-generic', 'UPS Cabinet', 'power'),
]
const names = () => screen.queryAllByRole('listitem').map((li) => li.querySelector('strong')?.textContent)

describe('LibraryPanel', () => {
  it('search filters by name, id and tags, category narrows', () => {
    render(<LibraryPanel templates={templates} />)
    expect(names()).toHaveLength(3)
    const search = screen.getByRole('searchbox')
    fireEvent.change(search, { target: { value: 'HVAC' } })
    expect(names()).toEqual(['Crac Unit'])
    fireEvent.change(search, { target: { value: 'ups-cab' } })
    expect(names()).toEqual(['UPS Cabinet'])
    fireEvent.change(search, { target: { value: 'rack' } })
    expect(names()).toEqual(['Rack 42U'])
    fireEvent.change(search, { target: { value: '' } })
    fireEvent.click(screen.getByRole('combobox', { name: /Kategori/ }))
    fireEvent.click(screen.getByRole('option', { name: 'cooling' }))
    expect(names()).toEqual(['Crac Unit'])
  })

  it('cards carry id@version in dataTransfer', () => {
    render(<LibraryPanel templates={templates} />)
    const data: Record<string, string> = {}
    const dataTransfer = { setData: (k: string, v: string) => { data[k] = v }, effectAllowed: '' }
    fireEvent.dragStart(screen.getByText('UPS Cabinet').closest('li')!, { dataTransfer })
    expect(data['application/x-template']).toBe('ups-cabinet-generic@1.0.0')
  })
})
