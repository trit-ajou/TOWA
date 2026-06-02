import { describe, expect, it } from 'vitest'

import { parseBackendMode, resolveDomainMode } from '@/backend/index'

describe('parseBackendMode', () => {
  it('treats unset as real (production safety default)', () => {
    expect(parseBackendMode('VITE_UI_BACKEND_MODE', undefined)).toBe('real')
  })

  it('treats empty string as real', () => {
    expect(parseBackendMode('VITE_UI_BACKEND_MODE', '')).toBe('real')
  })

  it('accepts real', () => {
    expect(parseBackendMode('VITE_UI_BACKEND_MODE', 'real')).toBe('real')
  })

  it('accepts emulated', () => {
    expect(parseBackendMode('VITE_UI_BACKEND_MODE', 'emulated')).toBe('emulated')
  })

  it('throws on typo / unknown value', () => {
    expect(() => parseBackendMode('VITE_UI_BACKEND_MODE', 'reel'))
      .toThrow(/invalid VITE_UI_BACKEND_MODE/)
  })

  it('includes the offending value in the error message', () => {
    expect(() => parseBackendMode('VITE_UI_BACKEND_MODE', 'mock'))
      .toThrow(/"mock"/)
  })
})

describe('resolveDomainMode — AND-gate semantics', () => {
  // master=real: domain stays real, emulated override is rejected outright
  describe('with master=real', () => {
    it('domain unset → real', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', undefined, 'real')).toBe('real')
    })

    it('domain empty → real', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', '', 'real')).toBe('real')
    })

    it('domain=real → real (no-op explicit)', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', 'real', 'real')).toBe('real')
    })

    it('domain=emulated → throws (the production-safety guarantee)', () => {
      expect(() => resolveDomainMode('VITE_UI_AI_BACKEND', 'emulated', 'real'))
        .toThrow(/VITE_UI_AI_BACKEND=emulated is rejected because VITE_UI_BACKEND_MODE=real/)
    })
  })

  // master=emulated: per-domain override is meaningful, can pick which stay real
  describe('with master=emulated', () => {
    it('domain unset → inherits emulated', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', undefined, 'emulated')).toBe('emulated')
    })

    it('domain empty → inherits emulated', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', '', 'emulated')).toBe('emulated')
    })

    it('domain=emulated → emulated', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', 'emulated', 'emulated')).toBe('emulated')
    })

    it('domain=real → real (selective live engine while master is dev)', () => {
      expect(resolveDomainMode('VITE_UI_AI_BACKEND', 'real', 'emulated')).toBe('real')
    })
  })

  it('throws on invalid per-domain value regardless of master', () => {
    expect(() => resolveDomainMode('VITE_UI_AI_BACKEND', 'fake', 'real'))
      .toThrow(/invalid VITE_UI_AI_BACKEND/)
    expect(() => resolveDomainMode('VITE_UI_AI_BACKEND', 'fake', 'emulated'))
      .toThrow(/invalid VITE_UI_AI_BACKEND/)
  })
})
