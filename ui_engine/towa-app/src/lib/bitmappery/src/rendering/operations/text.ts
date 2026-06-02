/**
 * The MIT License (MIT)
 *
 * Igor Zinken 2020-2022 - https://www.igorski.nl
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
import type { Text } from "@/definitions/document";
import { fastRound } from "@/math/unit-math";

type MeasuredLineDef = {
    line: string;
    top: number;
    width: number;
};

export type TextBox = {
    width: number;
    height: number;
};

/**
 * Renders a Layers text Object as multi line text onto given context.
 *
 * If `box` is provided the canvas is sized to the box and the text is positioned
 * using `text.align` / `text.verticalAlign`. Otherwise (legacy bitmappery path)
 * the canvas is sized to the text bounding box and drawn at (0,0).
 */
export const renderMultiLineText = ( ctx: CanvasRenderingContext2D, text: Text, box?: TextBox ): void => {
    const measured = measureLines( text.value.split( "\n" ), text, ctx );
    const { lines } = measured;
    const textWidth  = measured.width;
    const textHeight = measured.height;

    const canvasWidth  = box ? Math.max( 1, Math.round( box.width  )) : textWidth;
    const canvasHeight = box ? Math.max( 1, Math.round( box.height )) : textHeight;

    // size canvas
    ctx.canvas.width  = canvasWidth;
    ctx.canvas.height = canvasHeight;

    applyTextStyleToContext( text, ctx );

    const yOffset = box ? computeVerticalOffset( text.verticalAlign, canvasHeight, textHeight ) : 0;

    lines.forEach(({ line, top, width }) => {
        const xOffset = box ? computeHorizontalOffset( text.align, canvasWidth, width ) : 0;
        if ( !text.spacing ) {
            ctx.fillText( line, xOffset, top + yOffset );
        } else {
            const letters = line.split( "" );
            letters.forEach(( letter, letterIndex ) => {
                ctx.fillText( letter, xOffset + fastRound( letterIndex * text.spacing ), top + yOffset );
            });
        }
    });
};

function computeHorizontalOffset( align: Text[ "align" ], canvasWidth: number, lineWidth: number ): number {
    switch ( align ) {
        case "center": return fastRound(( canvasWidth - lineWidth ) / 2 );
        case "right":  return fastRound( canvasWidth - lineWidth );
        default:       return 0;
    }
}

function computeVerticalOffset( verticalAlign: Text[ "verticalAlign" ], canvasHeight: number, textHeight: number ): number {
    switch ( verticalAlign ) {
        case "middle": return fastRound(( canvasHeight - textHeight ) / 2 );
        case "bottom": return fastRound( canvasHeight - textHeight );
        default:       return 0;
    }
}

/* internal methods */

/**
 * Measure the bounding box occupied by given lines of text for given text properties
 *
 * @param {string[]} lines of text to render
 * @param {Object} text Layer text Object
 * @param {CanvasRenderingContext2D} ctx
 * @return {{ lines: MeasuredLineDef[], width: Number, height: Number }} bounding box of the rendered text
 */
function measureLines( lines: string[], text: Text, ctx: CanvasRenderingContext2D ):
    { lines: MeasuredLineDef[], width: number, height: number } {
    applyTextStyleToContext( text, ctx );

    const linesOut: MeasuredLineDef[] = [];
    let width  = 0;
    let height = 0;

    let lineHeight  = text.lineHeight;
    let textMetrics = ctx.measureText( "Wq" );
    // if no custom line height was given, calculate optimal height for font
    if ( !lineHeight ) {
        lineHeight = textMetrics.actualBoundingBoxAscent + textMetrics.actualBoundingBoxDescent;
    }
    // Safety padding: 한국어/일본어/이모지 글리프가 actualBoundingBoxAscent를 초과해
    // 그려지는 경우(특히 첫 줄)에 canvas top 위로 잘리는 것을 방지. font size의 20%.
    const topPadding = Math.ceil( text.size * 0.2 );
    const topOffset = topPadding + textMetrics.actualBoundingBoxAscent;
    let top = 0;

    lines.forEach(( line, lineIndex ) => {
        top = fastRound( topOffset + ( lineIndex * lineHeight ));
        let lineWidth: number;
        if ( !text.spacing ) {
            textMetrics = ctx.measureText( line );
            lineWidth = textMetrics.actualBoundingBoxRight;
        } else {
            const letters = line.split( "" );
            lineWidth = letters.length * text.spacing;
        }
        width = Math.max( width, lineWidth );
        linesOut.push({ line, top, width: lineWidth });
        height += lineHeight;
    });
    return {
        lines  : linesOut,
        width  : Math.ceil( width ),
        height : Math.ceil( height + topPadding ),
    };
}

function applyTextStyleToContext( text: Text, ctx: CanvasRenderingContext2D ): void {
    ctx.font      = `${text.size}${text.unit} "${text.font}"`;
    ctx.fillStyle = text.color;
}
