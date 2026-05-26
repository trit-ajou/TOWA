/**
 * TOWA Mode Presets
 *
 * translator (역자): 텍스트 도구 + 이동/줌만. header-menu 숨김.
 * typesetter (식자): 전체 이미지 편집 도구. File 메뉴는 towa-app이 대체.
 */
import type { FeatureKey } from "./towa-features";
import { setModeOverrides } from "./towa-features";

export type TowaMode = "translator" | "typesetter";

export const MODE_PRESETS: Record<TowaMode, Partial<Record<FeatureKey, boolean>>> = {
    translator: {
        // 텍스트 관련 도구만 활성화
        TOOL_TEXT: true,
        TOOL_MOVE: true,
        TOOL_DRAG: true,
        TOOL_ZOOM: true,
        TOOL_SCALE: true,
        // 나머지 도구 비활성화
        TOOL_LASSO: false,
        TOOL_SELECTION: false,
        TOOL_WAND: false,
        TOOL_EYEDROPPER: false,
        TOOL_ROTATE: false,
        TOOL_MIRROR: false,
        TOOL_FILL: false,
        TOOL_BRUSH: false,
        TOOL_ERASER: false,
        TOOL_CLONE: false,
        // UI 간소화
        UI_HEADER_MENU: false,
        // 파일 관련 전부 비활성화 (towa-app이 관리)
        FILE_IMAGE_OPEN: false,
        FILE_IMAGE_EXPORT: false,
        FILE_BPY_SAVE: false,
        FILE_BPY_LOAD: false,
        FILE_PSD_IMPORT: false,
        FILE_PDF_IMPORT: false,
    },
    typesetter: {
        // 대부분 기본값(true) 유지, 파일 관련만 비활성화
        FILE_IMAGE_OPEN: false,
        FILE_BPY_SAVE: false,
        FILE_BPY_LOAD: false,
    },
};

export const setTowaMode = ( mode: TowaMode ): void => {
    setModeOverrides( MODE_PRESETS[ mode ] ?? {} );
};
