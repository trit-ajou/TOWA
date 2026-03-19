/**
 * TOWA Feature Flags for bitmappery
 *
 * bitmappery의 각 기능을 개별적으로 on/off 할 수 있는 feature flag 시스템.
 * false로 설정하면 해당 기능이 UI에서 숨겨지며, true로 되돌리면 재활성화됨.
 * 코드 삭제 없이 비활성화하는 방식.
 */
export const TOWA_FEATURES = {
    // ── 도구 (Tools) ──
    TOOL_MOVE: true,
    TOOL_DRAG: true,
    TOOL_LASSO: true,
    TOOL_SELECTION: true,
    TOOL_WAND: true,
    TOOL_SCALE: true,
    TOOL_EYEDROPPER: true,
    TOOL_ROTATE: true,
    TOOL_MIRROR: true,
    TOOL_FILL: true,
    TOOL_BRUSH: true,
    TOOL_ERASER: true,
    TOOL_CLONE: true,
    TOOL_TEXT: true,
    TOOL_ZOOM: true,

    // ── 파일/Import/Export ──
    FILE_IMAGE_OPEN: true,
    FILE_IMAGE_EXPORT: true,
    FILE_PSD_IMPORT: true,
    FILE_PDF_IMPORT: true,
    FILE_GIF_EXPORT: false,
    FILE_BPY_SAVE: true,
    FILE_BPY_LOAD: true,

    // ── 클라우드 스토리지 ──
    CLOUD_DROPBOX: false,
    CLOUD_GOOGLE_DRIVE: false,
    CLOUD_S3: false,

    // ── 문서 조작 (Document) ──
    DOC_RESIZE: true,
    DOC_CANVAS_SIZE: true,
    DOC_CROP_SELECTION: true,
    DOC_GRID_TO_LAYERS: true,

    // ── 레이어 ──
    LAYER_BASIC: true,
    LAYER_MASK: true,
    LAYER_MERGE: true,
    LAYER_EFFECTS: true,
    LAYER_BLEND_MODES: true,
    LAYER_REORDER: true,

    // ── 편집 ──
    EDIT_HISTORY: true,
    EDIT_CLIPBOARD: true,
    EDIT_STROKE_SELECTION: true,
    EDIT_SELECTION_SAVE: true,
    EDIT_DELETE: true,

    // ── 뷰/UI ──
    VIEW_SNAP: true,
    VIEW_ANTIALIAS: true,
    VIEW_PIXEL_GRID: true,
    UI_PREFERENCES: true,

    // ── 기타 ──
    FONT_GOOGLE_FONTS: true,
    FILTER_WASM: true,
} as const;

export type FeatureKey = keyof typeof TOWA_FEATURES;

export const isFeatureEnabled = ( key: FeatureKey ): boolean => TOWA_FEATURES[ key ];
