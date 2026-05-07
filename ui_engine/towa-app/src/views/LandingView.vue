<script setup lang="ts">
import { computed } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import { ScanText, Eraser, Languages, Brush, ArrowRight, Sparkles, Zap, Layers } from 'lucide-vue-next'

const store = useStore()
const router = useRouter()

const isLoggedIn = computed<boolean>(() => store.getters['auth/isLoggedIn'])

function primaryAction() {
  router.push(isLoggedIn.value ? '/library' : '/login')
}

const workflow = [
  { num: '01', title: '검출', sub: 'Detect', icon: ScanText, color: '#9569B4', desc: '말풍선·텍스트 자동 인식' },
  { num: '02', title: '지움', sub: 'Inpaint', icon: Eraser, color: '#e84a8a', desc: '원문 삭제 및 배경 복원' },
  { num: '03', title: '번역', sub: 'Translate', icon: Languages, color: '#fb8b24', desc: '문맥 기반 자동 번역' },
  { num: '04', title: '식자', sub: 'Typeset', icon: Brush, color: '#4ade80', desc: '폰트·정밀 편집까지' },
]
</script>

<template>
  <div class="font-korean overflow-x-hidden">
    <!-- ============ HERO ============ -->
    <section class="relative min-h-[calc(100vh-48px)] bg-grain">
      <!-- Halftone backdrop -->
      <div class="absolute inset-0 bg-halftone opacity-60 pointer-events-none" />
      <!-- Diagonal accent stripe -->
      <div
        class="absolute -top-10 -right-20 w-[440px] h-[180px] bg-hatch opacity-50 -rotate-12 pointer-events-none"
      />

      <div class="relative max-w-6xl mx-auto px-6 lg:px-10 pt-16 lg:pt-24 pb-20">
        <!-- Tag chip -->
        <div class="inline-flex items-center gap-2 mb-8 anim-fade">
          <span class="h-px w-10 bg-towa-accent" />
          <span class="text-[11px] tracking-[0.3em] text-towa-text-muted uppercase font-display font-medium">
            Manhwa · Manga · Webtoon Studio
          </span>
        </div>

        <!-- Display title -->
        <div class="grid lg:grid-cols-12 gap-8 items-end">
          <div class="lg:col-span-8">
            <h1
              class="font-display font-bold leading-[0.92] tracking-tight text-towa-text"
              style="font-size: clamp(3.5rem, 9vw, 7.5rem)"
            >
              <span class="block anim-rise delay-1">번역의</span>
              <span class="block anim-rise delay-2">
                모든 단계를
              </span>
              <span class="block anim-rise delay-3">
                <span class="marker">한 화면에서.</span>
              </span>
            </h1>
          </div>

          <div class="lg:col-span-4 anim-rise delay-4">
            <p class="text-base text-towa-text-muted leading-relaxed mb-6 max-w-xs">
              만화·웹툰 번역가를 위한 올인원 워크스테이션.
              AI 자동화와 픽셀 단위 정밀 편집이
              하나의 흐름 안에 묶여있습니다.
            </p>
            <div class="flex flex-col gap-3">
              <button
                class="group flex items-center justify-between gap-3 bg-towa-accent hover:bg-towa-accent-hover transition-colors rounded-none border-2 border-towa-text px-5 py-3 text-white font-display font-medium"
                style="box-shadow: 5px 5px 0 0 var(--towa-text)"
                @click="primaryAction"
              >
                <span>{{ isLoggedIn ? '내 라이브러리로' : '시작하기' }}</span>
                <ArrowRight :size="18" class="transition-transform group-hover:translate-x-1" />
              </button>
              <a
                href="#workflow"
                class="text-xs text-towa-text-muted hover:text-towa-text transition-colors text-center"
              >
                먼저 둘러보기 ↓
              </a>
            </div>
          </div>
        </div>

        <!-- TOWA blockletter watermark -->
        <div
          aria-hidden="true"
          class="absolute -bottom-8 left-0 right-0 flex justify-center pointer-events-none anim-fade delay-5"
        >
          <span
            class="font-display font-bold tracking-tight select-none"
            style="
              font-size: clamp(7rem, 22vw, 18rem);
              line-height: 1;
              color: transparent;
              -webkit-text-stroke: 1px rgba(149, 105, 180, 0.18);
            "
          >
            TOWA
          </span>
        </div>
      </div>
    </section>

    <!-- ============ WORKFLOW (4 manga panels) ============ -->
    <section id="workflow" class="relative bg-towa-surface border-t-2 border-towa-text">
      <div class="max-w-6xl mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div class="flex items-end justify-between mb-12 flex-wrap gap-4">
          <div>
            <div class="text-[11px] tracking-[0.3em] text-towa-pink uppercase font-display font-medium mb-3">
              Workflow / 작업 흐름
            </div>
            <h2 class="font-display font-bold text-towa-text leading-tight" style="font-size: clamp(2rem, 4vw, 3.25rem)">
              4단계의 흐름,<br />
              하나의 도구.
            </h2>
          </div>
          <p class="text-sm text-towa-text-muted max-w-md">
            검출부터 식자까지 — 단계별로 나뉘어 있던 작업을 한 캔버스 위에서.
            각 단계는 AI가 시작하고, 사람이 마무리합니다.
          </p>
        </div>

        <!-- Panel grid: asymmetric 4-step manga panels -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
          <div
            v-for="(step, i) in workflow"
            :key="step.num"
            class="anim-pop"
            :class="`delay-${i + 1}`"
          >
            <div
              class="group relative bg-towa-bg p-6 transition-transform hover:-translate-y-1 hover:-translate-x-1 cursor-default"
              :style="{
                border: '2px solid var(--towa-text)',
                boxShadow: `6px 6px 0 0 ${step.color}`,
              }"
            >
              <!-- Panel number -->
              <div class="flex items-baseline justify-between mb-6">
                <span
                  class="font-display font-bold text-3xl"
                  :style="{ color: step.color }"
                >
                  {{ step.num }}
                </span>
                <component :is="step.icon" :size="20" :style="{ color: step.color }" />
              </div>
              <!-- Title -->
              <h3 class="font-display font-bold text-2xl text-towa-text mb-1">
                {{ step.title }}
              </h3>
              <div class="text-[10px] tracking-[0.3em] text-towa-text-muted uppercase font-display mb-4">
                {{ step.sub }}
              </div>
              <p class="text-sm text-towa-text-muted leading-relaxed">
                {{ step.desc }}
              </p>

              <!-- Inter-step arrow (hidden on last + on small screens) -->
              <div
                v-if="i < workflow.length - 1"
                class="hidden lg:flex absolute -right-7 top-1/2 -translate-y-1/2 items-center justify-center w-6 h-6 z-10 text-towa-text-muted"
                aria-hidden="true"
              >
                <ArrowRight :size="20" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ SPLIT FEATURE: AI vs Pixel ============ -->
    <section class="relative bg-towa-bg border-t-2 border-towa-text">
      <div class="max-w-6xl mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div class="grid lg:grid-cols-2 gap-10 lg:gap-16">
          <!-- LEFT: AI -->
          <div class="relative">
            <div class="text-[11px] tracking-[0.3em] text-towa-accent uppercase font-display font-medium mb-3 flex items-center gap-2">
              <Sparkles :size="13" /> 자동화
            </div>
            <h3
              class="font-display font-bold text-towa-text mb-6 leading-tight"
              style="font-size: clamp(1.75rem, 3.5vw, 2.75rem)"
            >
              지루한 반복은<br />AI에게.
            </h3>
            <p class="text-sm text-towa-text-muted leading-relaxed mb-6 max-w-md">
              텍스트 검출, 인페인팅, 1차 번역까지 — 시간 잡아먹던 반복 작업을
              모델 엔진이 일괄 처리합니다. 한 페이지에 분 단위 걸리던 작업이
              초 단위로 단축되고, 번역가는 검수와 표현에 집중할 수 있게 됩니다.
            </p>
            <ul class="space-y-2 text-sm text-towa-text">
              <li class="flex items-start gap-2"><Zap :size="14" class="text-towa-accent mt-0.5 shrink-0" /> 페이지 단위 일괄 처리</li>
              <li class="flex items-start gap-2"><Zap :size="14" class="text-towa-accent mt-0.5 shrink-0" /> 다국어 검출/번역 모델 (한·일·영·중)</li>
              <li class="flex items-start gap-2"><Zap :size="14" class="text-towa-accent mt-0.5 shrink-0" /> 클라우드/로컬 추론 모두 지원</li>
            </ul>
          </div>

          <!-- RIGHT: Precision -->
          <div class="relative">
            <div class="text-[11px] tracking-[0.3em] text-towa-pink uppercase font-display font-medium mb-3 flex items-center gap-2">
              <Brush :size="13" /> 정밀 편집
            </div>
            <h3
              class="font-display font-bold text-towa-text mb-6 leading-tight"
              style="font-size: clamp(1.75rem, 3.5vw, 2.75rem)"
            >
              마지막 1px은<br />당신의 손으로.
            </h3>
            <p class="text-sm text-towa-text-muted leading-relaxed mb-6 max-w-md">
              결과물의 품질을 결정하는 식자·인페인트의 마무리 단계는
              내장된 픽셀 에디터(bitmappery 기반)로 직접 다듬습니다.
              레이어, 폰트 변형, 마스크, 자유 변형 — 익숙한 도구가 그 자리에.
            </p>
            <ul class="space-y-2 text-sm text-towa-text">
              <li class="flex items-start gap-2"><Layers :size="14" class="text-towa-pink mt-0.5 shrink-0" /> 레이어 기반 비파괴 편집</li>
              <li class="flex items-start gap-2"><Layers :size="14" class="text-towa-pink mt-0.5 shrink-0" /> 텍스트 / 마스크 / 자유 변형</li>
              <li class="flex items-start gap-2"><Layers :size="14" class="text-towa-pink mt-0.5 shrink-0" /> 프로젝트 단위 자동 저장</li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ DEMO PLACEHOLDER ============ -->
    <section class="relative bg-towa-surface border-t-2 border-towa-text overflow-hidden">
      <div class="absolute inset-0 bg-halftone-dense opacity-30 pointer-events-none" />
      <div class="relative max-w-6xl mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div class="text-center mb-10">
          <div class="text-[11px] tracking-[0.3em] text-towa-text-muted uppercase font-display font-medium mb-3">
            Coming soon
          </div>
          <h3 class="font-display font-bold text-towa-text" style="font-size: clamp(2rem, 4vw, 3rem)">
            데모 / 사용 가이드
          </h3>
        </div>

        <div
          class="aspect-video bg-towa-bg max-w-4xl mx-auto flex items-center justify-center"
          style="border: 2px solid var(--towa-text); box-shadow: 8px 8px 0 0 var(--towa-accent)"
        >
          <div class="text-center px-6">
            <div class="text-sm text-towa-text-muted mb-2 font-display tracking-wider uppercase">Preview</div>
            <div class="font-display text-towa-text-muted text-lg">— 작업 화면 데모 영상 자리 —</div>
            <a
              class="inline-block mt-6 text-xs text-towa-accent hover:text-towa-accent-hover underline underline-offset-4 decoration-2"
              href="#"
              @click.prevent
            >
              사용 가이드 보기 (준비 중)
            </a>
          </div>
        </div>
      </div>
    </section>

    <!-- ============ FINAL CTA ============ -->
    <section class="relative bg-towa-bg border-t-2 border-towa-text">
      <div class="max-w-4xl mx-auto px-6 lg:px-10 py-20 lg:py-28 text-center">
        <h2
          class="font-display font-bold text-towa-text leading-[0.95] mb-8"
          style="font-size: clamp(2.5rem, 6vw, 5rem)"
        >
          이제,<br />
          <span class="marker">번역가의 시간</span>을<br />돌려놓을 차례.
        </h2>
        <button
          class="group inline-flex items-center gap-3 bg-towa-pink hover:bg-towa-pink/90 transition-colors px-8 py-4 text-white font-display font-medium text-base"
          style="border: 2px solid var(--towa-text); box-shadow: 6px 6px 0 0 var(--towa-text)"
          @click="primaryAction"
        >
          <span>{{ isLoggedIn ? '내 라이브러리로' : '시작하기' }}</span>
          <ArrowRight :size="18" class="transition-transform group-hover:translate-x-1" />
        </button>
      </div>
    </section>

    <!-- ============ FOOTER ============ -->
    <footer class="bg-towa-surface border-t-2 border-towa-text">
      <div class="max-w-6xl mx-auto px-6 lg:px-10 py-10">
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 text-xs text-towa-text-muted">
          <div class="flex items-center gap-3">
            <span class="font-display font-bold text-towa-text tracking-wider">TOWA</span>
            <span>Translator's One-stop Workstation with AI</span>
          </div>
          <div class="flex items-center gap-5">
            <a class="hover:text-towa-text transition-colors" href="#" @click.prevent>가이드</a>
            <a class="hover:text-towa-text transition-colors" href="#" @click.prevent>변경 이력</a>
            <a class="hover:text-towa-text transition-colors" href="#" @click.prevent>문의</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>
