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
import { type Store } from "vuex";
import { canvas, type Rectangle, type Viewport } from "zcanvas";
import { type Document } from "@/definitions/document";
import { fastRound } from "@/math/unit-math";
import InteractionPane from "@/rendering/actors/interaction-pane";
import type LayerRenderer from "@/rendering/actors/layer-renderer";
import { renderState } from "@/services/render-service";
import { type BitMapperyState } from "@/store";
import { zoomIn, zoomOut } from "@/store/actions/canvas-zoom";

class ZoomableCanvas extends canvas {
    public store: Store<BitMapperyState>; // Vuex root store reference
    public rescaleFn: () => void; // rescale handler used to match parent component with zCanvas rescales
    public refreshFn: () => void; // refresh handler used to force rebuild of all Layer renderers
    public documentScale: number;
    public zoomFactor: number;
    public interactionPane: InteractionPane;
    public guides: Rectangle[];
    public locked: boolean;
    public draggingSprite: LayerRenderer | null; // reference to Sprite that is being dragged (see LayerRenderer)

    private _bounds: DOMRect;
    private _interactionBlocked: boolean;
    private _frMul: number;

    constructor( opts: any, store: Store<BitMapperyState>, rescaleFn: () => void, refreshFn: () => void ) {
        super( opts );

        this.store = store;
        this.rescaleFn = rescaleFn;
        this.refreshFn = refreshFn;

        this.documentScale = 1;
        this.setZoomFactor( 1 );
        this.interactionPane = new InteractionPane();

        this.draggingSprite = null;

        this._frMul = 1 / ( 1000 / this.getFrameRate() ); // TODO: can be removed after update to zCanvas 6+
    }

    /**
     * Both setViewport and setDimensions route through the base's
     * updateCanvasSize which reassigns element.width/.height. Any such
     * assignment resets the 2D context, exposing the canvas CSS checkerboard
     * for one frame. We wrap both calls in a snapshot+restore so the previous
     * frame's pixels survive the resize until LayerRenderer children draw
     * themselves at the new dimensions in the next render pass.
     */
    setViewport( aWidth: number, aHeight: number ): void {
        this._snapshotAndCall(() => {
            // @ts-expect-error base method signature comes from zCanvas JS source
            super.setViewport( aWidth, aHeight );
        });
    }

    setDimensions( width: number, height: number, setAsPreferredDimensions = true, optImmediate = false ): void {
        this._snapshotAndCall(() => {
            // @ts-expect-error base method signature comes from zCanvas JS source
            super.setDimensions( width, height, setAsPreferredDimensions, optImmediate );
        });
    }

    private _snapshotAndCall( call: () => void ): void {
        const element = this.getElement();
        let snapshot: HTMLCanvasElement | null = null;

        if ( element.width > 0 && element.height > 0 ) {
            snapshot = document.createElement( "canvas" );
            snapshot.width  = element.width;
            snapshot.height = element.height;
            snapshot.getContext( "2d" )?.drawImage( element, 0, 0 );
        }

        call();

        if ( snapshot ) {
            const ctx = this.getCanvasContext();
            ctx.save();
            ctx.setTransform( 1, 0, 0, 1, 0, 0 );
            ctx.drawImage( snapshot, 0, 0, element.width, element.height );
            ctx.restore();
        }
    }

    setDocumentScale(
        targetWidth: number, targetHeight: number, scale: number, zoom: number,
        activeDocument: Document = null,
        anchor: { localX: number; localY: number; focalX: number; focalY: number } | null = null,
    ): void {
        const oldViewport = { ...this._viewport };
        const oldWidth    = this._width;
        const oldHeight   = this._height;
        const { width: vpW, height: vpH } = oldViewport;

        // anchor 모드: 클릭/커서 위치의 world point가 화면에서 같은 viewport 위치에 유지
        // 기본 모드: 캔버스가 viewport보다 크면 이전 viewport ratio 유지, 작으면 centered
        let worldRatioX: number, worldRatioY: number;
        let focalX: number, focalY: number;

        if ( anchor ) {
            // localX/Y는 canvas element 내부 좌표 (world point 식별용)
            worldRatioX = ( oldViewport.left + anchor.localX ) / oldWidth;
            worldRatioY = ( oldViewport.top  + anchor.localY ) / oldHeight;
            // focalX/Y는 viewport(container) 내 좌표 (줌 후에도 이 화면 위치 유지)
            focalX = anchor.focalX / vpW;
            focalY = anchor.focalY / vpH;
        } else {
            // 캔버스가 viewport보다 클 때만 이전 ratio 의미 있음
            const oldScrollW = oldWidth  - vpW;
            const oldScrollH = oldHeight - vpH;
            const ratioX = oldScrollW > 0 ? ( oldViewport.left / oldScrollW ) : 0.5;
            const ratioY = oldScrollH > 0 ? ( oldViewport.top  / oldScrollH ) : 0.5;
            worldRatioX = focalX = ratioX;
            worldRatioY = focalY = ratioY;
        }

        this.setDimensions( fastRound( targetWidth ), fastRound( targetHeight ), true, true );
        this.setZoomFactor( scale * zoom );

        // 캔버스가 viewport보다 크면 element는 viewport 좌상단 (offset 0), viewport pan으로 anchor 유지
        // 캔버스가 작으면 element offset(transform)으로 anchor 유지 (viewport.left=0)
        let newViewportLeft: number, newViewportTop: number;
        let elementOffsetX: number, elementOffsetY: number;

        // 캔버스가 viewport보다 크면 anchor 유지(클릭 위치 고정), 작으면 centered로 snap.
        // 사용자 직관: 캔버스가 화면에 다 들어오면 가운데 정렬이 자연스러움.
        // 줌인 상태에서 자유 이동이 필요하면 Space+드래그 pan 도구 사용.
        if ( this._width >= vpW ) {
            elementOffsetX = 0;
            newViewportLeft = anchor
                ? worldRatioX * this._width - focalX * vpW
                : ( this._width - vpW ) * worldRatioX;
        } else {
            newViewportLeft = 0;
            elementOffsetX = ( vpW - this._width ) / 2;
        }
        if ( this._height >= vpH ) {
            elementOffsetY = 0;
            newViewportTop = anchor
                ? worldRatioY * this._height - focalY * vpH
                : ( this._height - vpH ) * worldRatioY;
        } else {
            newViewportTop = 0;
            elementOffsetY = ( vpH - this._height ) / 2;
        }

        this.panViewport( fastRound( newViewportLeft ), fastRound( newViewportTop ), true );

        // TOWA: canvas element 위치를 직접 제어. .center CSS는 document-canvas.vue에서 비활성화됨.
        this._element.style.position = "absolute";
        this._element.style.left = `${fastRound( elementOffsetX )}px`;
        this._element.style.top  = `${fastRound( elementOffsetY )}px`;
        this._element.style.transform = ""; // .center 클래스의 잔존 transform 제거

        if ( activeDocument ) {
            this.documentScale = activeDocument.width / this._width;
        }
    }

    getActiveDocument(): Document {
        return this.store.getters["bmp/activeDocument"];
    }

    setInteractive( isInteractive: boolean ): void {
        this._interactionBlocked = !isInteractive;
    }

    getViewport(): Viewport {
        return this._viewport;
    }

    setZoomFactor( scale: number ): void {
        this.zoomFactor = scale;

        // This zoom factor logic should move into the zCanvas
        // library where updateCanvasSize() takes this additional factor into account

        this._canvasContext.scale( scale, scale );
        this.invalidate();
    }

    setLock( locked: boolean ): void {
        this.locked = locked; // freezes current Canvas contents for a single render cycle
    }

    setGuides( guides: Rectangle[] ): void {
        this.guides = guides;
    }

    requestDeferredRender( force = this._animate ): void {
        // keeps render loop going when Canvas is animatable
        if ( !this._disposed && force && !this._renderPending ) {
            this._renderPending = true;
            this._renderId = window.requestAnimationFrame( this._renderHandler as FrameRequestCallback );
        }
    }

    zoomViewport( factor: number ): void {
        factor > 0 ? zoomOut( this.store ) : zoomIn( this.store );
    }

    /* zCanvas.canvas overrides */

    // TODO : can be removed after update to zCanvas 5.1.5 (requires Webpack 5 migration)
    getCoordinate(): DOMRect {
        if ( this._bounds === null ) {
            this._bounds = this._element.getBoundingClientRect();
        }
        return this._bounds;
    }

    // see QQQ comments to see what the difference is. Ideally these changes
    // should eventually be propagated to the zCanvas library.

    render( now: DOMHighResTimeStamp = 0 ): void {
        const delta = now - this._lastRender;

        this._renderPending = false;
        this._lastRender    = now - ( delta % this._renderInterval );

        // QQQ to prevent flickering between frames in which states update, we
        // can lock the canvas to keep the existing contents on screen
        if ( renderState.pending > 0 || this.locked ) {
            // console.info("no render. pending:" + renderState.pending + " lock:" + this.locked);
            this.locked = false;
            return this.requestDeferredRender( true );
        }

        // Hold the previous frame as long as any LayerRenderer child has not finished
        // preparing its bitmap. Without this guard the ctx.clearRect below would run
        // against renderers whose drawBitmap is gated on _bitmapReady=false, exposing
        // the canvas CSS checkerboard for the duration of the asynchronous cacheEffects
        // pipeline. We only inspect children that look like LayerRenderer (have a
        // `layer` property); guides and the interaction pane never carry a bitmap.
        for ( let i = 0; i < this._children.length; ++i ) {
            const child = this._children[ i ] as any;
            if ( !child.layer ) {
                continue;
            }
            if ( !child.getBitmap || !child.getBitmap() || child._bitmapReady === false ) {
                return this.requestDeferredRender( true );
            }
        }

        // in case a resize was requested execute it now as we will
        // immediately draw new contents onto the screen

        if ( this._enqueuedSize ) {
            updateCanvasSize( this );
        }

        const ctx = this._canvasContext;
        let theSprite;

        const framesSinceLastRender = delta * this._frMul;

        if ( ctx ) {

            // QQQ zoomFactor must be taken into account

            const { zoomFactor } = this;

            const width  = fastRound( this._width  / zoomFactor );
            const height = fastRound( this._height / zoomFactor );

            const viewport = { ...this._viewport };
            Object.entries( viewport ).forEach(([ key, value ]): void => {
                viewport[ key ] = ( value as number ) / zoomFactor;
            });

            // E.O. QQQ

            // clear previous canvas contents either by flooding it
            // with the optional background colour, or by clearing all pixel content

            if ( this._bgColor ) {
                ctx.fillStyle = this._bgColor;
                ctx.fillRect( 0, 0, width, height );
            }
            else {
                ctx.clearRect( 0, 0, width, height );
            }

            const useExternalUpdateHandler = typeof this._updateHandler === "function";

            if ( useExternalUpdateHandler ) {
                this._updateHandler( now, framesSinceLastRender );
            }

            // draw the children onto the canvas

            theSprite = this._children[ 0 ];

            while ( theSprite ) {
                if ( !useExternalUpdateHandler ) {
                    theSprite.update( now, framesSinceLastRender );
                }
                theSprite.draw( ctx, viewport );
                theSprite = theSprite.next;
            }
        }
        this.requestDeferredRender();
    }

    handleInteraction( aEvent: Event ): void {
        if ( this._interactionBlocked ) {
            return;
        }
        const numChildren = this._children.length;
        const viewport    = this._viewport;
        let theChild, found;

        if ( numChildren > 0 ) {

            // reverse loop to first handle top layers
            theChild = this._children[ numChildren - 1 ];

            switch ( aEvent.type ) {

                // all touch events
                default:
                    let eventOffsetX = 0, eventOffsetY = 0;

                    const touches: TouchList = ( event as TouchEvent ).changedTouches;
                    let i = 0;
                    let l = touches ? touches.length : 0;

                    if ( l > 0 ) {
                        let { x, y } = this.getCoordinate();
                        if ( viewport ) {
                            // TODO when canvas isn't full screen the pointer is nowhere to be seen
                            x -= viewport.left;
                            y -= viewport.top;
                        }

                        // zCanvas supports multitouch, process all pointers

                        for ( i = 0; i < l; ++i ) {
                            const touch = touches[ i ];
                            const { identifier } = touch;

                            eventOffsetX = ( touch.pageX - x ) / this.zoomFactor; // QQQ
                            eventOffsetY = ( touch.pageY - y ) / this.zoomFactor; // QQQ

                            switch ( aEvent.type ) {
                                // on touchstart events, when we a Sprite handles the event, we
                                // map the touch identifier to this Sprite
                                case "touchstart":
                                    while ( theChild ) {
                                        if ( !this._activeTouches.includes( theChild ) && theChild.handleInteraction( eventOffsetX, eventOffsetY, event )) {
                                            this._activeTouches[ identifier ] = theChild;
                                            break;
                                        }
                                        theChild = theChild.last;
                                    }
                                    theChild = this._children[ numChildren - 1 ];
                                    break;
                                // on all remaining touch events we retrieve the Sprite associated
                                // with the event pointer directly
                                default:
                                    theChild = this._activeTouches[ identifier ];
                                    if ( theChild?.handleInteraction( eventOffsetX, eventOffsetY, event )) {
                                        // all events other than touchmove should be treated as a release
                                        if ( aEvent.type !== "touchmove" ) {
                                            this._activeTouches[ identifier ] = null;
                                        }
                                    }
                                    break;

                            }
                        }
                    }
                    break;

                // all mouse events
                case "mousedown":
                case "mousemove":
                case "mouseup":
                    let { offsetX, offsetY } = ( aEvent as MouseEvent );
                    // QQQ in case move and up event are fired outside of the canvas element
                    // we must translate the event coordinates to be relative to the canvas
                    if ( aEvent.target !== this._element ) {
                        const { x, y } = this.getCoordinate();
                        offsetX = ( aEvent as MouseEvent ).pageX - x;
                        offsetY = ( aEvent as MouseEvent ).pageY - y;
                    }
                    if ( viewport ) {
                        offsetX += viewport.left;
                        offsetY += viewport.top;
                    }
                    offsetX /= this.zoomFactor; // QQQ
                    offsetY /= this.zoomFactor; // QQQ

                    while ( theChild ) {
                        found = theChild.handleInteraction( offsetX, offsetY, aEvent );
                        if ( found ) {
                            break;
                        }
                        theChild = theChild.last;
                    }
                    break;

                // scroll wheel
                case "wheel":
                    const { deltaX, deltaY } = aEvent as WheelEvent;
                    const WHEEL_SPEED = 20;
                    const xSpeed = deltaX === 0 ? 0 : deltaX > 0 ? WHEEL_SPEED : -WHEEL_SPEED;
                    const ySpeed = deltaY === 0 ? 0 : deltaY > 0 ? WHEEL_SPEED : -WHEEL_SPEED;
                    // ctrlKey indicates (MacBook) touchpad gesture
                    if (( aEvent as WheelEvent ).ctrlKey ) {
                        aEvent.preventDefault();
                        aEvent.stopImmediatePropagation();
                        this.zoomViewport( ySpeed );
                    } else {
                        this.panViewport( viewport.left + xSpeed, viewport.top + ySpeed, true );
                    }
                    break;
            }
        }
        if ( this._preventDefaults ) {
            aEvent.stopPropagation();
            aEvent.preventDefault();
        }
        // update the Canvas contents
        this.invalidate();
    }

    dispose(): void {
        super.dispose();

        this.interactionPane?.dispose();
        this.interactionPane = null;
    }
}
export default ZoomableCanvas;

/* internal methods */

/**
 * literal clone of zCanvas code, only duplicated here because
 * of custom render() method. When zoomFactor code is ported to base zCanvas
 * library this can go (and custom render() can just call super class behaviour
 * after the deferred logic calculation)
 */
function updateCanvasSize( canvasInstance: ZoomableCanvas ): void {
    // @ts-expect-error protected property access
    const scaleFactor = canvasInstance._HDPIscaleRatio;
    const viewport = canvasInstance.getViewport();
    let width, height;

    // @ts-expect-error protected property access
    if ( canvasInstance._enqueuedSize ) {
        // @ts-expect-error protected property access
        ({ width, height } = canvasInstance._enqueuedSize );
        // @ts-expect-error protected property access
        canvasInstance._enqueuedSize = null;
        // @ts-expect-error protected property access
        canvasInstance._width  = width;
        // @ts-expect-error protected property access
        canvasInstance._height = height;
    }

    if ( viewport ) {
        // @ts-expect-error protected property access
        const cvsWidth  = canvasInstance._width;
        // @ts-expect-error protected property access
        const cvsHeight = canvasInstance._height;

        width  = Math.min( viewport.width,  cvsWidth );
        height = Math.min( viewport.height, cvsHeight );

        // in case viewport was panned beyond the new canvas dimensions
        // reset pan to center.
/*
        if ( viewport.left > cvsWidth ) {
            viewport.left  = cvsWidth * .5;
            viewport.right = viewport.width + viewport.left;
        }
        if ( viewport.top > cvsHeight ) {
            viewport.top    = cvsHeight * .5;
            viewport.bottom = viewport.height + viewport.top;
        }
*/
    }

    if ( width && height ) {
        const element = canvasInstance.getElement();

        element.width  = width  * scaleFactor;
        element.height = height * scaleFactor;

        element.style.width  = `${width}px`;
        element.style.height = `${height}px`;
    }
    canvasInstance.getCanvasContext().scale( scaleFactor, scaleFactor );

    // non-smoothing must be re-applied when the canvas dimensions change...

    if ( canvasInstance.getSmoothing() === false ) {
        canvasInstance.setSmoothing( false );
    }
    // @ts-expect-error protected property access
    canvasInstance._bounds = null; // TODO : can be removed after update to zCanvas 5.1.5 (requires Webpack 5 migration)
}
