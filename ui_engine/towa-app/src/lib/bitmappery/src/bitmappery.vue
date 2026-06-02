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
<template>
    <div id="bitmappery-app" ref="app">
        <section class="main">
            <toolbox
                v-if="showToolbox"
                ref="toolbox"
                class="toolbox"
                :class="{ 'collapsed': !toolboxOpened }"
            />
            <div class="document-container">
                <component :is="documentCanvas" ref="documentCanvas" />
            </div>
            <div
                v-if="showOptionsPanel || showLayerPanel"
                ref="panels"
                class="panels"
                :class="{ 'collapsed': !openedPanels.length }"
            >
                <tool-options-panel
                    v-if="showOptionsPanel"
                    class="tool-options-panel"
                />
                <layer-panel
                    v-if="showLayerPanel"
                    class="layer-panel"
                />
            </div>
        </section>
    </div>
</template>

<script lang="ts">
import { type Component, defineAsyncComponent } from "vue";
import { mapState, mapGetters, mapMutations, mapActions } from "vuex";
import ToolOptionsPanel from "@/components/tool-options-panel/tool-options-panel.vue";
import LayerPanel from "@/components/layer-panel/layer-panel.vue";
import Toolbox from "@/components/toolbox/toolbox.vue";
import type { Document } from "@/definitions/document";
import ToolTypes from "@/definitions/tool-types";
import DocumentFactory from "@/factories/document-factory";
import { isMobile } from "@/utils/environment-util";
import { isFeatureEnabled } from "@/config/towa-features";
import { loadImageFiles } from "@/services/file-loader-queue";
import { renderState } from "@/services/render-service";
import ImageToDocumentManager from "@/mixins/image-to-document-manager";
import { readClipboardFiles, readDroppedFiles } from "@/utils/file-util";
import { truncate } from "@/utils/string-util";
let lastDocumentId = null;

// wrapper for loading dynamic components with custom loading states
type IAsyncComponent = { component: Promise<Component>};
function asyncComponent( key: string, importFn: () => Promise<any> ): IAsyncComponent {
    return defineAsyncComponent({
        loader: async () => {
            try {
                const component = await importFn();
                return component;
            } catch ( e ) {
                // @ts-expect-error 'import.meta' property not allowed, not an issue Vite takes care of it
                if ( import.meta.env.MODE !== "production" ) {
                    console.error( e );
                }
                reject();
            }
        }
    });
}

export default {
    mixins: [ ImageToDocumentManager ],
    components: {
        ToolOptionsPanel,
        LayerPanel,
        Toolbox,
    },
    data: () => ({}),
    computed: {
        ...mapState("bmp", [
            "blindActive",
            "dialog",
            "modal",
            "openedPanels",
            "toolboxOpened",
            "windowSize",
        ]),
        ...mapGetters("bmp", [
            "activeDocument",
            "isLoading",
        ]),
        documentCanvas(): IAsyncComponent {
            return asyncComponent( "dc", () => import( "@/components/document-canvas/document-canvas.vue" ));
        },
        activeModal(): IAsyncComponent | null {
            // 모든 modal 컴포넌트가 정리됨 (#58). 호출이 와도 항상 null 반환.
            return null;
        },
        showLoader(): boolean {
            return this.isLoading || renderState.pending > 0;
        },
        // TOWA: bitmappery 기본 UI는 mode preset으로 일괄 off, towa-app이 대체
        showToolbox(): boolean { return isFeatureEnabled( "UI_TOOLBOX" ); },
        showOptionsPanel(): boolean { return isFeatureEnabled( "UI_TOOL_OPTIONS_PANEL" ); },
        showLayerPanel(): boolean { return isFeatureEnabled( "UI_LAYER_PANEL" ); },
    },
    watch: {
        activeDocument( document: Document ): void {
            if ( !document?.layers ) {
                this.resetHistory();
                if ( isMobile() ) {
                    this.closeOpenedPanels();
                }
            } else {
                const { id } = document;
                if ( id !== lastDocumentId ) {
                    lastDocumentId = id;
                    this.resetHistory();
                }
            }
        },
        toolboxOpened(): void {
            this.$nextTick( () => this.$refs.documentCanvas?.calcIdealDimensions?.() );
        },
        openedPanels(): void {
            this.$nextTick( () => this.$refs.documentCanvas?.calcIdealDimensions?.() );
        },
    },
    async created(): Promise<void> {
        await this.setupServices( this.$t );
        // prepare adaptive view for mobile environment
        this.setToolboxOpened( true );
        if ( isMobile() ) {
            this.closeOpenedPanels();
        }
    },
    mounted(): void {
        // no need to remove the below as we will require it throughout the application lifetime
        window.addEventListener( "resize", this.handleResize.bind( this ));
        this.$refs.app?.addEventListener( "wheel", ( e: WheelEvent ) => {
            if ( e.ctrlKey ) {
                e.preventDefault(); e.stopPropagation(); // prevent zoom using touchpad
            }
        });
        if ( import.meta.env.MODE === "production" ) {
            window.onbeforeunload = e => {
                if ( !!this.activeDocument ) {
                    e.preventDefault();
                    return this.$t( "warningUnload" );
                }
            };
        }

        // if File content is pasted or dragged into the application, parse and load image files within

        const loadFiles = async ({ images, documents, thirdParty, url }) => {
            const LOADING_KEY = `drop_${Date.now()}`;
            this.setLoading( LOADING_KEY );
            try {
                loadImageFiles( images, this.addLoadedFile.bind( this ));
                for ( const file of documents ) {
                    const document = await DocumentFactory.fromBlob( file );
                    this.addNewDocument( document );
                }
                await this.loadThirdPartyDocuments( thirdParty );
                if ( typeof url === "string" && url.length > 0 ) {
                    try {
                        const resource = await fetch( url );
                        loadImageFiles([ await resource.blob() ], this.addLoadedFile.bind( this ));
                    } catch {
                        this.openDialog({
                            type: "error",
                            message: this.$t( "corsError", { file: truncate( decodeURIComponent( url ).split( "/" ).at( -1 ), 40 ) })
                        });
                    }
                }
            } catch {
                // aren't these caught internally ?
            }
            this.unsetLoading( LOADING_KEY );
        };

        window.addEventListener( "paste", event => {
            loadFiles( readClipboardFiles( event?.clipboardData ));
        }, false );

        this.$el.addEventListener( "dragover", event => {
            event.stopPropagation();
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
        }, false );
        this.$el.addEventListener( "drop", event => {
            loadFiles( readDroppedFiles( event?.dataTransfer ));
            event.preventDefault();
            event.stopPropagation();
        }, false );
    },
    methods: {
        ...mapMutations("bmp", [
            "addNewDocument",
            "closeModal",
            "closeOpenedPanels",
            "openDialog",
            "resetHistory",
            "setToolboxOpened",
            "setToolOptionValue",
            "setLoading",
            "setWindowSize",
            "unsetLoading",
        ]),
        ...mapActions("bmp", [
            "setupServices",
        ]),
        handleResize(): void {
            this.setWindowSize({ width: window.innerWidth, height: window.innerHeight });
            // prevent maximum zoom at previous small window size to lead to excessively large document canvas
            this.setToolOptionValue({ tool: ToolTypes.ZOOM, option: "level", value: 1 });
            // re-calculate document canvas dimensions (flex layout handles width automatically)
            this.$nextTick(() => this.$refs.documentCanvas?.calcIdealDimensions?.());
        },
    }
};
</script>

<style lang="scss">
/**
 * note child components use scoped styling
 * here we set the global typography and layout styles
 * we expect to use throughout
 */
@use "sass:math";

@use "@/styles/_colors";
@use "@/styles/_global";
@use "@/styles/_mixins";
@use "@/styles/_variables";
@use "@/styles/panel";

#bitmappery-app {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    background-image: linear-gradient(to bottom, colors.$color-bg-dark 35%, colors.$color-bg-light 90%);
    height: 100%;
    font-size: 14px;
    // container query root: child elements use @container bitmappery (...)
    // so layout responds to bitmappery's actual size, not viewport width
    container-type: inline-size;
    container-name: bitmappery;
    @include mixins.noSelect();

    .main {
        @include mixins.boxSize();
        height: calc(100% - #{variables.$menu-height});
        position: relative;

        @include mixins.large() {
            padding: variables.$spacing-medium;
        }
    }

    // TOWA: header-menu가 비활성화된 모드에서는 .main이 부모(=#bitmappery-app)를 꽉 채우고
    // padding/document-container margin도 제거 (캔버스 영역 하단 여백 방지).
    &.header-hidden .main {
        height: 100%;
        @include mixins.large() {
            padding: 0;
        }
    }
    &.header-hidden .document-container {
        margin: 0;
    }
    // canvas-wrapper는 @include component.component() 으로 .component__content height/padding이
    // heading-height 기준 calc. 우리는 component__header를 v-if로 숨기므로 이 보정도 제거해야
    // 캔버스가 wrapper 전체를 채움 (하단 여백 방지).
    &.header-hidden .canvas-wrapper .component__content {
        height: 100%;
        padding: 0;
    }

    .blind {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,.5);
        z-index: 400; // below overlays (see _variables.scss)
    }

    .document-container {
        flex: 1;
        min-width: 0;
        margin: 0 variables.$spacing-medium;
    }

    /* three column layout on tablet / desktops */

    @include mixins.large() {
        .main {
            display: flex;
            flex-direction: row;
            align-items: stretch;
        }
        .toolbox,
        .panels {
            &.collapsed {
                width: panel.$collapsed-panel-width;
                min-height: variables.$heading-height;

                .component__title {
                    display: none;
                }
                .component__header-button {
                    right: variables.$spacing-xxsmall !important;
                }
            }
        }
        .panels {
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
            height: calc(100% - variables.$spacing-xsmall );
            $optionsHeight: 250px;
            
            .tool-options-panel {
                height: calc(#{$optionsHeight - math.div( variables.$spacing-medium, 2 )});
            }
            .layer-panel {
                margin-top: variables.$spacing-medium;
            }

            @include mixins.minHeight( 900px ) {
                $optionsHeight: 390px;
                .tool-options-panel {
                    height: calc(#{$optionsHeight - math.div( variables.$spacing-medium, 2 )});
                }
                .layer-panel {
                    height: calc(100% - #{$optionsHeight + math.div( variables.$spacing-medium, 2 )});
                    margin-top: variables.$spacing-medium;
                }
            }
        }

        .toolbox {
            flex-shrink: 0;
            width: 105px;
        }
        .panels {
            width: 300px;
        }
    }

    /* three row layout on phones */

    @include mixins.mobile() {
        .toolbox {
            position: fixed;
            top: variables.$menu-height;
            width: 100%;
            height: variables.$menu-height;
        }
        .panels {
            position: fixed;
            width: 100%;
            max-height: 50%;
            //max-height: calc(100% - #{variables.$menu-height * 3});
            bottom: 0;
            overflow-y: scroll;
            border-top: 1px solid colors.$color-bg;

            &.collapsed {
                height: variables.$menu-height;
            }
        }
        .document-container {
            position: fixed;
            top: variables.$menu-height * 2;
            width: 100%;
            height: calc(100% - #{variables.$menu-height * 3 });
            margin: 0;
        }
    }
}
</style>
