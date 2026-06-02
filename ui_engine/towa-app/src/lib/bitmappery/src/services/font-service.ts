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
import { createCanvas } from "@/utils/canvas-util";

const GOOGLE_FONTS_URL = "https://fonts.googleapis.com/css?family=";

const loadedFonts: Set<string> = new Set();

// Google Fonts deemed non-GDPR compliant. Request consent first
export const fontsConsented = (): boolean => window.localStorage?.getItem( "gfontConsent" ) === "true";

export const consentFonts = (): void => {
    window.localStorage?.setItem?.( "gfontConsent", "true" );
};

export const rejectFonts = (): void => {
    window.localStorage?.setItem?.( "gfontRejected", "true" );
};

/**
 * Lazily loads a Google font (defined in the list above)
 * Returns boolean true indicating whether font was cache
 * or false when it has just been loaded (and added to the cache)
 */
export const loadGoogleFont = ( fontName: string ): Promise<boolean> => {
    return loadGoogleFontDetailed( fontName ).then( r => r.loaded && !r.freshlyLoaded );
};

/**
 * loadGoogleFont의 확장. 호출자가 폰트가 이번 호출로 처음 로드됐는지 알 수 있도록
 * { loaded, freshlyLoaded } 반환. freshlyLoaded=true이면 호출자는 측정 정확한 상태로
 * 한 번 더 렌더링을 트리거해야 한다 (첫 렌더는 fallback 폰트로 측정된 가능성).
 *
 * 내부는 document.fonts.load API로 실제 폰트 로드 완료를 기다린다. CSS @font-face 요청이
 * onload 됐다고 해서 폰트가 OS에 실제 등록된 것은 아니기 때문 (기존 250ms setTimeout은
 * 보장이 약함).
 */
export const loadGoogleFontDetailed = (
    fontName: string,
): Promise<{ loaded: boolean; freshlyLoaded: boolean }> => {
    return new Promise(( resolve, reject ) => {
        if ( !fontsConsented() ) {
            reject();
            return;
        }
        if ( loadedFonts.has( fontName )) {
            resolve({ loaded: true, freshlyLoaded: false });
            return;
        }
        const css = document.createElement( "link" );
        css.setAttribute( "rel", "stylesheet" );
        css.setAttribute( "type", "text/css" );
        css.onload = async (): Promise<void> => {
            // CSS file이 로드됨. 그러나 실제 글리프 파일은 아직 로드되지 않았을 수 있음.
            // document.fonts.load로 실제 폰트 로드 보장.
            try {
                if ( document.fonts && typeof document.fonts.load === "function" ) {
                    await document.fonts.load( `16px "${fontName}"` );
                } else {
                    // fallback: 옛 ctx.measureText 트리거 + 250ms 대기 (기존 동작)
                    const { ctx } = createCanvas();
                    ctx.font = `16px ${fontName}`;
                    ctx.fillText( "foo", 0, 0 );
                    await new Promise( r => window.setTimeout( r, 250 ));
                }
                loadedFonts.add( fontName );
                resolve({ loaded: true, freshlyLoaded: true });
            } catch ( e ) {
                console.warn( `document.fonts.load failed for ${fontName}`, e );
                loadedFonts.add( fontName ); // 그래도 캐시에 박아 추가 시도 방지
                resolve({ loaded: false, freshlyLoaded: false });
            }
        };
        css.onerror = ( e: Event ): void => {
            console.error( `Could not load font ${fontName}`, e );
            reject();
        }
        css.setAttribute( "href", `${GOOGLE_FONTS_URL}${fontName}` );
        document.getElementsByTagName( "head" )[ 0 ].appendChild( css );
    });
};
