// Single source of truth for TanStack Query keys (#39).
// All invalidations go through one of these factories so call sites stay
// consistent and we don't accidentally diverge on subtle shape mismatches.

export const queryKeys = {
  projects: {
    all: () => ['projects'] as const,
  },
  folders: {
    all: () => ['folders'] as const,
  },
  pages: {
    byProject: (projectId: string) => ['pages', projectId] as const,
    /** Lightweight per-page summary (no list iteration) for callsites that
     *  already know a single id and want reactive metadata. */
    one: (projectId: string, pageId: string) =>
      ['pages', projectId, pageId] as const,
  },
  trash: {
    all: () => ['trash'] as const,
  },
  binary: {
    pageSnapshot: (pageId: string) => ['binary', 'page-snapshot', pageId] as const,
    thumbnail: (pageId: string) => ['binary', 'thumbnail', pageId] as const,
  },
} as const
