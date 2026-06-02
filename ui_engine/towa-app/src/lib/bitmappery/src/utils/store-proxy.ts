/**
 * Creates proxy wrappers around the Vuex store that automatically
 * prefix all commits, dispatches, and getter accesses with the "bmp/" namespace.
 * This allows services (KeyboardService, history-state-factory, etc.)
 * to use the store without knowing about the namespace.
 */
import type { Store, Commit, Dispatch } from "vuex";
import type { BitMapperyState } from "@/store";

const BMP_NS = "bmp/";

interface NamespacedStoreProxy {
    state: BitMapperyState;
    getters: any;
    commit: Commit;
    dispatch: Dispatch;
}

export function createNamespacedProxy( store: Store<any> ): NamespacedStoreProxy {
    const state = ( store.state.bmp ?? store.state ) as BitMapperyState;

    const getters = new Proxy( store.getters, {
        get( target, prop: string ) {
            // Try namespaced first, fallback to direct
            return target[ BMP_NS + prop ] ?? target[ prop ];
        },
    });

    const commit: Commit = ( type: string, payload?: any, options?: any ) => {
        const nsType = type.startsWith( BMP_NS ) ? type : BMP_NS + type;
        return store.commit( nsType, payload, options );
    };

    const dispatch: Dispatch = ( type: string, payload?: any, options?: any ) => {
        const nsType = type.startsWith( BMP_NS ) ? type : BMP_NS + type;
        return store.dispatch( nsType, payload, options );
    };

    return { state, getters, commit, dispatch };
}
