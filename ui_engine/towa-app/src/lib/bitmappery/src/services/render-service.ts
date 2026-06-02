/**
 * The MIT License (MIT)
 *
 * Igor Zinken 2020-2025 - https://www.igorski.nl
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
import { reactive } from "vue";
import type { Layer } from "@/definitions/document";
import { LayerTypes } from "@/definitions/layer-types";
import { getRendererForLayer } from "@/factories/renderer-factory";
import { hasFilters, isEqual as isFiltersEqual } from "@/factories/filters-factory";
import { isEqual as isTextEqual } from "@/factories/text-factory";
import { createCanvas, cloneCanvas, matchDimensions } from "@/utils/canvas-util";
import { replaceLayerSource } from "@/utils/layer-util";
import { clone } from "@/utils/object-util";
import { getLayerCache, setLayerCache } from "@/rendering/cache/bitmap-cache";
import type { RenderCache } from "@/rendering/cache/bitmap-cache";
import { maskImage } from "@/rendering/operations/masking";
import { renderMultiLineText } from "@/rendering/operations/text";
import { loadGoogleFont, loadGoogleFontDetailed } from "@/services/font-service";
import FilterWorker from "@/workers/filter.worker?worker";
import wasmUrl from "@/wasm/bin/filters.wasm?url";

type RenderJob = {
    id: number;
    success: ( data: { pixelData: ArrayLike<number> } ) => void;
    error: ( error?: any ) => void;
};

const jobQueue: RenderJob[] = [];
let UID = 0;

let useWasm = false;
let wasmWorker: Worker;

// expose an Object in which we can keep track of pending render jobs
export const renderState = reactive({ pending: 0, reset: () => renderState.pending = 0 });

export const setWasmFilters = ( enabled: boolean ): void => {
    useWasm = enabled;
    if ( enabled && !wasmWorker ) {
        wasmWorker = new FilterWorker();
        wasmWorker.onmessage = handleWorkerMessage;
        wasmWorker.postMessage({ cmd: "initWasm", wasmUrl });
    }
};

export const renderEffectsForLayer = async ( layer: Layer, useCaching = true ): Promise<void> => {
    const renderer = getRendererForLayer( layer );

    if ( !renderer || !layer.source ) {
        return;
    }

    ++renderState.pending;

    let { width, height } = layer;
    const { cvs, ctx } = createCanvas( width, height );

    const cached = useCaching ? getLayerCache( layer ) : null;
    const cacheToSet: RenderCache = {};

    const applyMask     = !!layer.mask;
    const applyFilter   = hasFilters( layer.filters );
    let hasCachedFilter = applyFilter && cached?.filterData && isFiltersEqual( layer.filters, cached.filters );

    // step 1. render layer source contents

    let scheduleFontRerender = false;
    if ( layer.type === LayerTypes.LAYER_TEXT ) {
        const meta = layer.meta as Record<string, unknown> | undefined;
        // text.value는 번역문 슬롯. 비어있을 때 'fixed' 모드는 meta.original을 fallback으로
        // 그려서 검출만 끝난 상태에도 캔버스에 원문이 보이게 한다. (issue #29)
        const fallback = meta?.boxMode === "fixed" && typeof meta?.original === "string"
            ? ( meta.original as string ) : "";
        const effectiveValue = layer.text.value || fallback;
        if ( effectiveValue ) {
            // text.value가 비어있을 때만 원문을 임시 렌더용으로 끼워넣는다. 저장되는
            // layer.text는 그대로 유지 (정책: text.value = 번역문 슬롯).
            const effectiveText = layer.text.value ? layer.text : { ...layer.text, value: effectiveValue };
            let textBitmap;
            if ( cached?.textBitmap && isTextEqual( effectiveText, cached.text )) {
                //console.info( "reading rendered text from cache" );
                textBitmap = cached.textBitmap;
            } else {
                const renderResult = await renderText({ ...layer, text: effectiveText } as Layer );
                textBitmap = renderResult.bitmap;
                scheduleFontRerender = renderResult.fontFreshlyLoaded;
                if ( meta?.boxMode === "fixed" ) {
                    // TOWA-style 텍스트 layer: layer.left/top/width/height 보존, source만 교체.
                    layer.source = textBitmap;
                } else {
                    // native bitmappery 동작: layer를 텍스트 크기로 축소 + 중앙 보정.
                    replaceLayerSource( layer, textBitmap );
                }
                //console.info( "writing rendered text to cache" );
                cacheToSet.text = { ...effectiveText };
                cacheToSet.textBitmap = textBitmap;
                hasCachedFilter = false; // new contents need to be refiltered
                ({ width, height } = textBitmap );
            }
            matchDimensions( textBitmap, cvs );
            ctx.drawImage( textBitmap, 0, 0 );
        }
    } else if ( !hasCachedFilter ) {
        //console.info( "draw unfiltered source, will apply filter next: " + applyFilter );
        ctx.drawImage( layer.source, 0, 0 );
    }

    // step 2. apply filters, this step can be cached to avoid unnecessary crunching

    if ( applyFilter ) {
        let imageData;
        if ( hasCachedFilter ) {
            //console.info( "reading filtered content from cache" );
            imageData = cached.filterData;
        } else {
            try {
                imageData = await runFilterJob( cvs, { filters: layer.filters });
                //console.info( "writing filtered content to cache" );
                cacheToSet.filters    = { ...layer.filters };
                cacheToSet.filterData = imageData;
            } catch ( error ) {
                // TODO: communicate error ?
                console.info( `Caught error "${error}" during runFilterJob()` );
                renderState.pending = Math.max( 0, renderState.pending - 1 );
                return;
            }
        }
        ctx.clearRect( 0, 0, width, height );
        ctx.putImageData( imageData, 0, 0 );
    }

    // step 3. apply mask
    // TODO: hook this into cache as well ? then again this is the last action in an otherwise cached queue...

    if ( applyMask ) {
        //console.info( "apply mask" );
        const unmaskedBitmap = cloneCanvas( cvs );
        renderer.setUnmaskedBitmap( unmaskedBitmap );
        renderMask( layer, ctx, applyFilter ? unmaskedBitmap : layer.source, width, height );
    } else {
        renderer.setUnmaskedBitmap( undefined );
    }

    // step 4. update cache and on-screen canvas contents

    if ( useCaching && Object.keys( cacheToSet ).length ) {
        setLayerCache( layer, cacheToSet );
    }

    renderState.pending = Math.max( 0, renderState.pending - 1 );

    // note that updating the bitmap will also adjust the renderer bounds
    // as appropriate (f.i. if rotation were handled by this service), the
    // Layer model remains unaffected by this
    renderer.setBitmap( cvs, width, height );
    renderer.invalidate();

    // 폰트가 이번 사이클에 처음 로드됐다면, 이전 measure는 fallback 폰트로 한 결과일 수
    // 있으므로 정확한 폰트로 한 번 더 그림. cacheEffects는 자체적으로 debounce 되어 있음.
    if ( scheduleFontRerender ) {
        // 캐시 무효화: 동일 text로 비교되면 캐시된 (잘못된) textBitmap을 재사용해버리므로
        // text 캐시를 비워 강제 재측정.
        if ( useCaching ) {
            const stale = getLayerCache( layer ) ?? {};
            setLayerCache( layer, { ...stale, text: undefined, textBitmap: undefined } as RenderCache );
        }
        requestAnimationFrame(() => {
            renderer.cacheEffects();
        });
    }
};

/* internal methods */

/**
 * Run a image processing job in a dedicated Worker.
 *
 * @param {HTMLCanvasElement} source content to process
 * @param {Object} jobSettings job/cmd-specific properties
 * @return {Promise<ImageData>} processed source as ImageData (can be stored in cache)
 */
const runFilterJob = ( source: HTMLCanvasElement, jobSettings: any ): Promise<ImageData> => {
    const { width, height } = source;
    const imageData = source.getContext( "2d" )!.getImageData( 0, 0, width, height );
    const wasm      = useWasm && wasmWorker;

    return new Promise( async ( resolve, reject ) => {
        const id = ( ++UID );
        let worker: Worker;
        let onComplete: () => void;

        if ( wasm ) {
            worker = wasmWorker;
        } else {
            // when not in WASM mode, Worker is lazily created per process so we can parallelize
            worker = new FilterWorker();
            worker.onmessage = handleWorkerMessage;
            onComplete = () => worker.terminate();
        }
        jobQueue.push({
            id,
            success: async data => {
                imageData.data.set( data.pixelData );
                onComplete?.();
                resolve( imageData );
            },
            error: optError => {
                // TODO: when wasm, disable wasm mode and return to JS worker ?
                onComplete?.();
                reject( optError );
            }
        });
        worker.postMessage({ cmd: wasm ? "filterWasm" : "filter", id, imageData, ...clone( jobSettings ) });
    })
};

function handleWorkerMessage({ data }: MessageEvent ): void {
    const jobQueueObj = getJobFromQueue( data?.id );
    if ( data?.cmd === "complete" ) {
        jobQueueObj?.success( data );
    }
    if ( data?.cmd === "error" ) {
        jobQueueObj?.error( data?.error );
    }
}

const renderText = async ( layer: Layer ): Promise<{ bitmap: HTMLCanvasElement; fontFreshlyLoaded: boolean }> => {
    const { text } = layer;
    let font = text.font;
    let fontFreshlyLoaded = false;
    try {
        const r = await loadGoogleFontDetailed( font );
        fontFreshlyLoaded = r.freshlyLoaded;
    } catch {
        font = "Arial"; // fall back to universally available Arial
    }
    const { cvs, ctx } = createCanvas();
    const meta = layer.meta as Record<string, unknown> | undefined;
    const box = meta?.boxMode === "fixed"
        ? { width: layer.width, height: layer.height }
        : undefined;
    renderMultiLineText( ctx, text, box );

    // render outlines to debug cropped bounding box
    //ctx.fillStyle = "rgba(255,0,0,.5)";
    //ctx.fillRect( 0, 0, cvs.width, cvs.height );

    return { bitmap: cvs, fontFreshlyLoaded };
};

const renderMask = ( layer: Layer, ctx: CanvasRenderingContext2D, sourceBitmap: HTMLCanvasElement, width: number, height: number ): void => {
    if ( !layer.mask ) {
        return;
    }
    maskImage( ctx, sourceBitmap, layer.mask, width, height, layer.maskX, layer.maskY );
};

function getJobFromQueue( jobId: number ): RenderJob | undefined {
    const jobQueueObj = jobQueue.find(({ id }) => id === jobId );
    if ( !jobQueueObj ) {
        return undefined;
    }
    jobQueue.splice( jobQueue.indexOf( jobQueueObj ), 1 );
    return jobQueueObj;
}
