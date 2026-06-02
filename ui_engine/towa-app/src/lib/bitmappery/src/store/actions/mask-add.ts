/**
 * The MIT License (MIT)
 *
 * Igor Zinken 2021-2026 - https://www.igorski.nl
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
import { type Store } from "vuex";
import { type Layer } from "@bitmappery/definitions/document";
import { enqueueState } from "@bitmappery/factories/history-state-factory";
import { clipContextToSelection } from "@bitmappery/rendering/operations/clipping";
import { getCanvasInstance } from "@bitmappery/services/canvas-service";
import { type BitMapperyState } from "@bitmappery/store";
import { createCanvas } from "@bitmappery/utils/canvas-util";

export const addMask = ( store: Store<BitMapperyState>, layer: Layer, index: number ): void => {
    const { cvs: mask, ctx } = createCanvas( layer.width, layer.height );

    const activeDocument = store.getters["bmp/activeDocument"];
    const currentSelection = activeDocument?.activeSelection ?? [];
    const hasSelection = currentSelection.length > 0;

    if ( hasSelection ) {
        ctx.save();
        clipContextToSelection( ctx, currentSelection, layer.left, layer.top, activeDocument.invertSelection );
        ctx.fillStyle = store.getters["bmp/activeColor"];
        ctx.fill();
        ctx.restore();
    }
    
    const commit  = () => {
        store.commit( "bmp/updateLayer", { index, opts: { mask } });
        store.commit( "bmp/setActiveLayerMask", index );

        if ( hasSelection ) {
            getCanvasInstance()?.interactionPane.setSelection( [], false );
        }
    };
    commit();

    enqueueState( `maskAdd_${index}`, {
        undo() {
            store.commit( "bmp/updateLayer", { index, opts: { mask: null } });
            store.commit( "bmp/setActiveLayerMask", null );

            if ( hasSelection ) {
                getCanvasInstance()?.interactionPane.setSelection( currentSelection, false );
            }
        },
        redo: commit,
    });
};