import { Buffer } from "buffer";
import FloatingVue, { vTooltip } from "floating-vue";
import * as Vue from "vue";
import { createStore } from "vuex";
import { createI18n } from "vue-i18n";
import BitMappery from "./bitmappery.vue";
import messages from "./messages.json";
import storeConfig from "./store";

FloatingVue.options.themes.tooltip.delay.show = 500;
import "floating-vue/dist/style.css"; // required for tooltips

// required for psd.js
globalThis.Buffer = Buffer;

// Create VueI18n instance (Composition API mode + global injection for $t in templates)
const i18n = createI18n({
    legacy: false,
    globalInjection: true,
    messages
});

const app = Vue.createApp( BitMappery );
app.use( createStore({ modules: { bmp: storeConfig } }));
app.use( i18n );
app.directive( "tooltip", vTooltip );
app.mount( "#bitmappery-app" );
