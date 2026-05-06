import type { Module } from 'vuex'
import type {
  AuthBackend,
  CurrentSessionInfo,
  EngineError,
  LoginResult,
  SessionUser,
} from '@/backend/contracts'
import { BackendError } from '@/backend/errors'

const STORAGE_KEY = 'towa.auth.session'

export interface AuthState {
  sessionKey: string | null
  user: SessionUser | null
  creditBalance: number
  reservedUnits: number
  error: EngineError | null
  isLoading: boolean
}

interface PersistedSession {
  sessionKey: string
  user: SessionUser
  creditBalance: number
  reservedUnits: number
}

// 외부 의존성 — Phase 2에서 main.ts가 store.dispatch('auth/init', backend.auth)로 주입
interface AuthModuleContext {
  auth: AuthBackend | null
}

const ctx: AuthModuleContext = { auth: null }

const auth: Module<AuthState, unknown> = {
  namespaced: true,

  state: (): AuthState => ({
    sessionKey: null,
    user: null,
    creditBalance: 0,
    reservedUnits: 0,
    error: null,
    isLoading: false,
  }),

  getters: {
    isLoggedIn: (state) => state.sessionKey != null,
  },

  mutations: {
    SET_SESSION(state, p: PersistedSession) {
      state.sessionKey = p.sessionKey
      state.user = p.user
      state.creditBalance = p.creditBalance
      state.reservedUnits = p.reservedUnits
      state.error = null
    },
    CLEAR_SESSION(state) {
      state.sessionKey = null
      state.user = null
      state.creditBalance = 0
      state.reservedUnits = 0
    },
    SET_ERROR(state, e: EngineError | null) {
      state.error = e
    },
    SET_LOADING(state, v: boolean) {
      state.isLoading = v
    },
    SET_CREDIT(state, balance: number) {
      state.creditBalance = balance
    },
  },

  actions: {
    /** Phase 2에서 main.ts가 호출: store.dispatch('auth/init', backend.auth) */
    init(_, authBackend: AuthBackend) {
      ctx.auth = authBackend
    },

    async devLogin({ commit }, { email, nickname }: { email: string; nickname?: string }) {
      if (!ctx.auth) throw new Error('auth module not initialized — dispatch auth/init first')
      commit('SET_LOADING', true)
      commit('SET_ERROR', null)
      try {
        const result: LoginResult = await ctx.auth.devLogin({ email, nickname })
        const persist: PersistedSession = {
          sessionKey: result.sessionKey,
          user: result.user,
          creditBalance: result.creditBalance,
          reservedUnits: result.reservedUnits,
        }
        commit('SET_SESSION', persist)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(persist))
      } catch (e) {
        if (e instanceof BackendError) {
          commit('SET_ERROR', e.payload)
        } else {
          commit('SET_ERROR', {
            code: 'unknown',
            message: String(e),
            retryable: false,
            details: null,
          })
        }
        throw e
      } finally {
        commit('SET_LOADING', false)
      }
    },

    async restoreFromStorage({ commit }) {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      try {
        const parsed = JSON.parse(raw) as PersistedSession
        commit('SET_SESSION', parsed)
        // ctx.auth가 주입된 후에만 서버 검증 가능
        if (ctx.auth) {
          try {
            const info: CurrentSessionInfo = await ctx.auth.getCurrentUser({
              sessionKey: parsed.sessionKey,
            })
            commit('SET_CREDIT', info.creditBalance)
          } catch {
            commit('CLEAR_SESSION')
            localStorage.removeItem(STORAGE_KEY)
          }
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      }
    },

    logout({ commit }) {
      commit('CLEAR_SESSION')
      localStorage.removeItem(STORAGE_KEY)
    },

    async refreshCredit({ state, commit }) {
      if (!ctx.auth || !state.sessionKey) return
      try {
        const info: CurrentSessionInfo = await ctx.auth.getCurrentUser({
          sessionKey: state.sessionKey,
        })
        commit('SET_CREDIT', info.creditBalance)
        const raw = localStorage.getItem(STORAGE_KEY)
        if (raw) {
          try {
            const parsed = JSON.parse(raw) as PersistedSession
            parsed.creditBalance = info.creditBalance
            parsed.reservedUnits = info.reservedUnits
            localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed))
          } catch {
            // ignore
          }
        }
      } catch {
        // 토큰 무효화는 다른 호출에서 처리됨
      }
    },
  },
}

export default auth
