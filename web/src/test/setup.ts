import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// vitest runs without globals, so Testing Library cannot register its own auto-cleanup
afterEach(cleanup)

// jsdom has no layout; Carbon's Dropdown scrolls the highlighted option into view
Element.prototype.scrollIntoView ??= () => {}

// Carbon's Modal observes its body size; jsdom has no ResizeObserver
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
