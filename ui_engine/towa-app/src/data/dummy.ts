import type { FileAdapter, ProjectRecord, PageRecord } from '@/file-adapter'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'

const seedProjects: ProjectRecord[] = [
  {
    id: 'proj-1',
    name: '원피스 1122화 — 화염의 기사',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 19,
    createdAt: '2026-03-10T08:00:00',
    updatedAt: '2026-03-22T22:30:00',
    status: 'in-progress',
    folder: '주간연재/점프',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
  },
  {
    id: 'proj-2',
    name: '주술회전 271화 — 사후',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 17,
    createdAt: '2026-03-09T09:00:00',
    updatedAt: '2026-03-22T18:00:00',
    status: 'done',
    folder: '주간연재/점프',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: true, inferenceMode: 'cloud' },
  },
  {
    id: 'proj-3',
    name: '블루 록 282화',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 20,
    createdAt: '2026-03-11T08:00:00',
    updatedAt: '2026-03-21T14:00:00',
    status: 'in-progress',
    folder: '주간연재/매거진',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
  },
  {
    id: 'proj-4',
    name: '나 혼자만 레벨업 시즌2 42화',
    sourceLang: 'ko',
    targetLang: 'en',
    pageCount: 65,
    createdAt: '2026-03-08T12:00:00',
    updatedAt: '2026-03-20T09:00:00',
    status: 'in-progress',
    folder: '웹툰/네이버',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: true, inferenceMode: 'cloud' },
  },
  {
    id: 'proj-5',
    name: '킹덤 789화 — 낙양의 함락',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 18,
    createdAt: '2026-03-20T10:00:00',
    updatedAt: '2026-03-22T15:00:00',
    status: 'todo',
    folder: '주간연재',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
  },
  {
    id: 'proj-6',
    name: '전독시 외전 — 소설 속 엑스트라',
    sourceLang: 'ko',
    targetLang: 'ja',
    pageCount: 28,
    createdAt: '2026-03-18T14:00:00',
    updatedAt: '2026-03-22T12:00:00',
    status: 'in-progress',
    folder: '웹툰/카카오',
    config: { autoDetect: true, autoInpaint: false, autoTranslate: false, inferenceMode: 'local' },
  },
  {
    id: 'proj-7',
    name: '요츠바랑! 15권 번역',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 180,
    createdAt: '2026-03-01T10:00:00',
    updatedAt: '2026-03-19T20:00:00',
    status: 'in-progress',
    folder: '단행본',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
  },
  {
    id: 'proj-8',
    name: '단편 — 고양이 소녀의 하루',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 8,
    createdAt: '2026-03-21T15:00:00',
    updatedAt: '2026-03-22T23:00:00',
    status: 'done',
    folder: '',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: true, inferenceMode: 'cloud' },
  },
]

function createSeedPages(projectId: string, count: number): PageRecord[] {
  const statuses: PageRecord['status'][] = ['done', 'in-progress', 'ai-processing', 'waiting']

  return Array.from({ length: count }, (_, i) => {
    const pageId = `${projectId}-page-${i + 1}`
    const status = statuses[Math.min(i, statuses.length - 1)]

    return {
      id: pageId,
      projectId,
      index: i + 1,
      status,
      textBlocks: [
        {
          id: `${pageId}-tb-1`,
          pageId,
          bbox: { x: 50, y: 80, width: 200, height: 60 },
          original: 'おはようございます！',
          translated: status === 'waiting' ? '' : '좋은 아침이에요!',
          font: 'Noto Sans KR',
          fontSize: 14,
          color: '#000000',
          status: status === 'waiting' ? 'detected' : 'translated',
        },
        {
          id: `${pageId}-tb-2`,
          pageId,
          bbox: { x: 300, y: 150, width: 180, height: 80 },
          original: 'なんだと？！信じられない！',
          translated: status === 'waiting' ? '' : '뭐라고?! 믿을 수 없어!',
          font: 'Noto Sans KR',
          fontSize: 16,
          color: '#000000',
          status: status === 'waiting' ? 'detected' : 'edited',
        },
        {
          id: `${pageId}-tb-3`,
          pageId,
          bbox: { x: 100, y: 400, width: 220, height: 50 },
          original: 'ここで待ってて',
          translated: status === 'waiting' ? '' : '여기서 기다려',
          font: 'Noto Sans KR',
          fontSize: 13,
          color: '#000000',
          status: status === 'waiting' ? 'detected' : 'translated',
        },
      ],
    }
  })
}

/**
 * Canvas로 placeholder 이미지 생성 (텍스트 기반).
 * 브라우저 환경에서만 동작.
 */
function generatePlaceholderImage(
  text: string, bgColor: string, fgColor: string, w: number, h: number,
): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = bgColor
  ctx.fillRect(0, 0, w, h)
  ctx.fillStyle = fgColor
  ctx.font = 'bold 18px sans-serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  const lines = text.split('\n')
  const lineHeight = 24
  const startY = h / 2 - ((lines.length - 1) * lineHeight) / 2
  lines.forEach((line, i) => {
    ctx.fillText(line, w / 2, startY + i * lineHeight)
  })
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob!), 'image/png')
  })
}

function blobToCanvas(blob: Blob): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(img.src)
      resolve(canvas)
    }
    img.onerror = reject
    img.src = URL.createObjectURL(blob)
  })
}

const projectThumbnailConfig: Record<string, { text: string; bg: string; fg: string }> = {
  'proj-1': { text: 'ONE\nPIECE', bg: '#1a1230', fg: '#9569B4' },
  'proj-2': { text: 'JJK\n271', bg: '#1e1510', fg: '#e84a8a' },
  'proj-3': { text: 'BLUE\nLOCK', bg: '#0d1a2a', fg: '#4a90d9' },
  'proj-4': { text: 'SL\nS2', bg: '#15102a', fg: '#a78bfa' },
  'proj-5': { text: 'KINGDOM\n789', bg: '#1a1a0d', fg: '#c8b560' },
  'proj-6': { text: 'ORV\nEX', bg: '#101520', fg: '#5b9ea6' },
  'proj-7': { text: 'YOTSU\nBA', bg: '#15201a', fg: '#4ade80' },
  'proj-8': { text: 'CAT\nGIRL', bg: '#1a1020', fg: '#c084fc' },
}

/**
 * IndexedDB가 비어있으면 더미 데이터를 seed로 삽입.
 * 이미 데이터가 있으면 아무것도 하지 않음.
 * @returns 삽입 여부
 */
export async function seedDummyDataIfEmpty(adapter: FileAdapter): Promise<boolean> {
  const existing = await adapter.listProjects()
  if (existing.length > 0) {
    // 기존 데이터가 있지만 page-layers가 없으면 (이전 버전 seed) 전체 재생성
    const firstPageLayers = await adapter.getLayerData('proj-1-page-1')
    if (firstPageLayers) return false
    // page-layers 없음 → DB 초기화 후 재생성
    for (const p of existing) {
      await adapter.deleteProject(p.id)
    }
  }

  // 프로젝트 저장
  for (const project of seedProjects) {
    await adapter.saveProject(project)

    // 페이지 저장 + 원본 이미지 + bitmappery 문서 + 썸네일
    const thumbConfig = projectThumbnailConfig[project.id]
    const bg = thumbConfig?.bg ?? '#1a1726'
    const fg = thumbConfig?.fg ?? '#4a4560'
    const pages = createSeedPages(project.id, project.pageCount)
    for (const page of pages) {
      await adapter.savePage(page)

      // 원본 이미지 (800×1200)
      const imgBlob = await generatePlaceholderImage(
        `${project.name}\nPage ${page.index}`, bg, fg, 800, 1200,
      )
      await adapter.saveOriginalImage(page.id, imgBlob)

      // bitmappery 문서 생성 → 직렬화 → page-layers에 저장
      const imgCanvas = await blobToCanvas(imgBlob)
      const doc = DocumentFactory.create({
        name: `page-${page.id}`,
        width: imgCanvas.width,
        height: imgCanvas.height,
        layers: [
          LayerFactory.create({
            name: 'original',
            source: imgCanvas,
            width: imgCanvas.width,
            height: imgCanvas.height,
          }),
        ],
      })
      const docBlob = await DocumentFactory.toBlob(doc)
      await adapter.saveLayerData(page.id, docBlob)

      // 썸네일 (200×300)
      const thumbBlob = await generatePlaceholderImage(`P${page.index}`, bg, fg, 200, 300)
      await adapter.saveThumbnail(page.id, thumbBlob)
    }
  }

  return true
}
