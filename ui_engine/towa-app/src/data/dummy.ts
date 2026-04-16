import type { FileAdapter, ProjectRecord } from '@/file-adapter'
import type { PageSnapshotMeta, PageSnapshot } from '@/file-adapter/contracts'
import type { PageStatus } from '@/types/page'
import type { TextBlock } from '@/types/text-block'
import { createUlid } from '@/utils/ulid'
// @ts-expect-error bitmappery JS module
import DocumentFactory from '@bitmappery/factories/document-factory'
// @ts-expect-error bitmappery JS module
import LayerFactory from '@bitmappery/factories/layer-factory'

interface SeedProjectSpec extends Omit<ProjectRecord, 'id'> {
  coverText: string
  coverBg: string
  coverFg: string
}

const seedProjects: SeedProjectSpec[] = [
  {
    name: '원피스 1122화 — 화염의 기사',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 19,
    createdAt: '2026-03-10T08:00:00',
    updatedAt: '2026-03-22T22:30:00',
    status: 'in-progress',
    folder: '주간연재/점프',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
    coverText: 'ONE\nPIECE',
    coverBg: '#1a1230',
    coverFg: '#9569B4',
  },
  {
    name: '주술회전 271화 — 사후',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 17,
    createdAt: '2026-03-09T09:00:00',
    updatedAt: '2026-03-22T18:00:00',
    status: 'done',
    folder: '주간연재/점프',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: true, inferenceMode: 'cloud' },
    coverText: 'JJK\n271',
    coverBg: '#1e1510',
    coverFg: '#e84a8a',
  },
  {
    name: '블루 록 282화',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 20,
    createdAt: '2026-03-11T08:00:00',
    updatedAt: '2026-03-21T14:00:00',
    status: 'in-progress',
    folder: '주간연재/매거진',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
    coverText: 'BLUE\nLOCK',
    coverBg: '#0d1a2a',
    coverFg: '#4a90d9',
  },
  {
    name: '나 혼자만 레벨업 시즌2 42화',
    sourceLang: 'ko',
    targetLang: 'en',
    pageCount: 65,
    createdAt: '2026-03-08T12:00:00',
    updatedAt: '2026-03-20T09:00:00',
    status: 'in-progress',
    folder: '웹툰/네이버',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: true, inferenceMode: 'cloud' },
    coverText: 'SL\nS2',
    coverBg: '#15102a',
    coverFg: '#A78BFA',
  },
  {
    name: '킹덤 789화 — 낙양의 함락',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 18,
    createdAt: '2026-03-20T10:00:00',
    updatedAt: '2026-03-22T15:00:00',
    status: 'todo',
    folder: '주간연재',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
    coverText: 'KINGDOM\n789',
    coverBg: '#1a1a0d',
    coverFg: '#C8B560',
  },
  {
    name: '전독시 외전 — 소설 속 엑스트라',
    sourceLang: 'ko',
    targetLang: 'ja',
    pageCount: 28,
    createdAt: '2026-03-18T14:00:00',
    updatedAt: '2026-03-22T12:00:00',
    status: 'in-progress',
    folder: '웹툰/카카오',
    config: { autoDetect: true, autoInpaint: false, autoTranslate: false, inferenceMode: 'local' },
    coverText: 'ORV\nEX',
    coverBg: '#101520',
    coverFg: '#5B9EA6',
  },
  {
    name: '요츠바랑! 15권 번역',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 180,
    createdAt: '2026-03-01T10:00:00',
    updatedAt: '2026-03-19T20:00:00',
    status: 'in-progress',
    folder: '단행본',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: false, inferenceMode: 'cloud' },
    coverText: 'YOTSU\nBA',
    coverBg: '#15201a',
    coverFg: '#4ADE80',
  },
  {
    name: '단편 — 고양이 소녀의 하루',
    sourceLang: 'ja',
    targetLang: 'ko',
    pageCount: 8,
    createdAt: '2026-03-21T15:00:00',
    updatedAt: '2026-03-22T23:00:00',
    status: 'done',
    folder: '',
    config: { autoDetect: true, autoInpaint: true, autoTranslate: true, inferenceMode: 'cloud' },
    coverText: 'CAT\nGIRL',
    coverBg: '#1a1020',
    coverFg: '#C084FC',
  },
]

function createSeedTextBlocks(pageId: string, status: PageStatus): TextBlock[] {
  return [
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
  ]
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

/**
 * IndexedDB가 비어있으면 더미 데이터를 seed로 삽입.
 * 이미 데이터가 있으면 아무것도 하지 않음.
 * @returns 삽입 여부
 */
export async function seedDummyDataIfEmpty(adapter: FileAdapter): Promise<boolean> {
  const existing = await adapter.listProjects()
  if (existing.length > 0) return false

  const statuses: PageStatus[] = ['done', 'in-progress', 'ai-processing', 'waiting']

  for (const seed of seedProjects) {
    const project: ProjectRecord = {
      id: createUlid(),
      name: seed.name,
      sourceLang: seed.sourceLang,
      targetLang: seed.targetLang,
      pageCount: seed.pageCount,
      createdAt: seed.createdAt,
      updatedAt: seed.updatedAt,
      status: seed.status,
      folder: seed.folder,
      config: seed.config,
      thumbnailUrl: seed.thumbnailUrl,
    }

    // pageCount를 0으로 시작 (createPage가 increment)
    await adapter.createProject({ ...project, pageCount: 0 })

    const bg = seed.coverBg
    const fg = seed.coverFg

    for (let i = 0; i < project.pageCount; i++) {
      const pageId = createUlid()
      const status = statuses[Math.min(i, statuses.length - 1)]
      const textBlocks = createSeedTextBlocks(pageId, status)

      // 원본 이미지 (800x1200)
      const imgBlob = await generatePlaceholderImage(
        `${project.name}\nPage ${i + 1}`, bg, fg, 800, 1200,
      )

      // bitmappery 문서 생성 → 직렬화 → layerBlob
      const imgCanvas = await blobToCanvas(imgBlob)
      const doc = DocumentFactory.create({
        name: `page-${pageId}`,
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
      const layerBlob = await DocumentFactory.toBlob(doc)

      // 썸네일 (200x300)
      const thumbnail = await generatePlaceholderImage(`${seed.coverText}\nP${i + 1}`, bg, fg, 200, 300)

      const pageMeta: PageSnapshotMeta = {
        id: pageId,
        projectId: project.id,
        index: i + 1, // createPage가 override하지만 논리적 일관성을 위해
        status,
        textBlocks,
      }

      const snapshot: PageSnapshot = {
        page: pageMeta,
        originalImage: imgBlob,
        layerBlob,
        thumbnail,
      }

      await adapter.createPage(project.id, snapshot)
    }
  }

  return true
}
