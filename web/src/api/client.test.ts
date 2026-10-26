import { expect, test } from 'vitest'
import { outputsBase } from './client'

test('outputs URL uses the bare version number the API route expects (/outputs/{v:int}/...)', () => {
  expect(outputsBase('p1', 3)).toBe('/api/projects/p1/outputs/3')
})
