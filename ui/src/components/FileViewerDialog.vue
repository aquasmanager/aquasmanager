<!--
  Visionneuse de fichiers (PDF, images) dans l'appli : certificats de cession,
  documents d'achat… PDF affiché page par page avec pdf.js (chargé à la
  demande), zoom, téléchargement. Ouverte via useFileViewerStore().show().
-->
<template>
  <q-dialog v-model="store.open" :maximized="$q.screen.lt.md" @hide="reset">
    <q-card class="viewer column no-wrap" :class="{ 'viewer--large': !$q.screen.lt.md }">
      <q-bar class="viewer__bar q-py-lg">
        <q-icon :name="isPdf ? 'picture_as_pdf' : 'image'" size="20px" class="q-mr-sm" />
        <div class="col ellipsis text-weight-medium">{{ store.file?.title }}</div>
        <q-btn flat round dense icon="zoom_out" :disable="zoom <= MIN_ZOOM" :aria-label="t('viewer.zoomOut')" @click="setZoom(zoom / STEP)">
          <q-tooltip>{{ t('viewer.zoomOut') }}</q-tooltip>
        </q-btn>
        <div class="text-caption q-mx-xs zoom-label">{{ Math.round(zoom * 100) }} %</div>
        <q-btn flat round dense icon="zoom_in" :disable="zoom >= MAX_ZOOM" :aria-label="t('viewer.zoomIn')" @click="setZoom(zoom * STEP)">
          <q-tooltip>{{ t('viewer.zoomIn') }}</q-tooltip>
        </q-btn>
        <q-btn flat round dense icon="fit_screen" :aria-label="t('viewer.fit')" @click="setZoom(1)">
          <q-tooltip>{{ t('viewer.fit') }}</q-tooltip>
        </q-btn>
        <q-btn flat round dense icon="download" :disable="!blob" :aria-label="t('viewer.download')" @click="download">
          <q-tooltip>{{ t('viewer.download') }}</q-tooltip>
        </q-btn>
        <q-btn v-close-popup flat round dense icon="close" :aria-label="t('common.close')" />
      </q-bar>

      <div ref="scroller" class="viewer__body col scroll">
        <div v-if="loading" class="flex flex-center full-height q-pa-xl column">
          <q-spinner color="primary" size="3em" />
          <div class="text-grey-7 q-mt-sm">{{ t('viewer.loading') }}</div>
        </div>
        <div v-else-if="error" class="flex flex-center full-height q-pa-xl column text-center">
          <q-icon name="error_outline" color="negative" size="40px" />
          <div class="q-mt-sm">{{ error }}</div>
        </div>
        <!-- Pages du PDF (canvas ajoutés par renderPdf) -->
        <div v-show="isPdf && !loading && !error" ref="pages" class="viewer__pages" />
        <div v-if="!isPdf && imageUrl && !loading" class="viewer__image">
          <img :src="imageUrl" :alt="store.file?.title" :style="{ width: `${zoom * 100}%` }" />
        </div>
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { PDFDocumentLoadingTask, PDFDocumentProxy } from 'pdfjs-dist/legacy/build/pdf.mjs';
import workerUrl from 'pdfjs-dist/legacy/build/pdf.worker.min.mjs?url';
import { useFileViewerStore } from 'src/stores/fileViewerStore';
import { apiErrorMessage } from 'src/utils/apiError';

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const STEP = 1.25;

const { t } = useI18n();
const $q = useQuasar();
const store = useFileViewerStore();

const loading = ref(false);
const error = ref<string | null>(null);
const blob = shallowRef<Blob | null>(null);
const imageUrl = ref<string | null>(null);
const zoom = ref(1);
const scroller = ref<HTMLElement | null>(null);
const pages = ref<HTMLElement | null>(null);
let pdf: PDFDocumentProxy | null = null;
let task: PDFDocumentLoadingTask | null = null;
let renderRun = 0;

const isPdf = computed(() => {
  const type = store.file?.contentType ?? blob.value?.type ?? '';
  return type === 'application/pdf' || (store.file?.filename ?? '').toLowerCase().endsWith('.pdf');
});

watch(
  () => store.open && store.file,
  (file) => {
    if (file) void load();
  },
);

async function load() {
  const file = store.file;
  if (!file) return;
  loading.value = true;
  error.value = null;
  zoom.value = 1;
  try {
    blob.value = await file.load();
    if (isPdf.value) {
      // pdf.js chargé seulement à la première ouverture d'un PDF
      const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs');
      pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
      task = pdfjs.getDocument({
        data: new Uint8Array(await blob.value.arrayBuffer()),
        // Copiées à la compilation (quasar.config.ts) ; sans elles, police de secours
        standardFontDataUrl: '/pdfjs/standard_fonts/',
      });
      pdf = await task.promise;
      loading.value = false;
      await renderPdf();
    } else {
      imageUrl.value = URL.createObjectURL(blob.value);
      loading.value = false;
    }
  } catch (err) {
    loading.value = false;
    error.value = apiErrorMessage(err, t('viewer.failed'));
  }
}

// Chaque page à la largeur de la fenêtre × zoom, nette sur les écrans haute densité
async function renderPdf() {
  const doc = pdf;
  const container = pages.value;
  if (!doc || !container) return;
  const run = ++renderRun;
  const available = Math.max(200, (scroller.value?.clientWidth ?? 800) - 32);
  const ratio = window.devicePixelRatio || 1;
  for (let n = 1; n <= doc.numPages; n += 1) {
    const page = await doc.getPage(n);
    if (run !== renderRun) return;
    const base = page.getViewport({ scale: 1 });
    const scale = (available / base.width) * zoom.value;
    const viewport = page.getViewport({ scale: scale * ratio });
    const canvas = document.createElement('canvas');
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = `${Math.floor(viewport.width / ratio)}px`;
    canvas.style.height = `${Math.floor(viewport.height / ratio)}px`;
    canvas.className = 'viewer__page';
    await page.render({ canvas, viewport }).promise;
    if (run !== renderRun) return;
    // Première page affichée dès qu'elle est prête, les suivantes à la suite
    if (n === 1) container.replaceChildren(canvas);
    else container.appendChild(canvas);
  }
}

function setZoom(value: number) {
  zoom.value = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));
  if (isPdf.value) void renderPdf();
}

function download() {
  if (!blob.value || !store.file) return;
  const url = URL.createObjectURL(blob.value);
  const link = document.createElement('a');
  link.href = url;
  link.download = store.file.filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function reset() {
  renderRun += 1;
  void task?.destroy();
  task = null;
  pdf = null;
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value);
  imageUrl.value = null;
  blob.value = null;
  error.value = null;
  pages.value?.replaceChildren();
}

// Rotation ou redimensionnement : pages recalculées à la nouvelle largeur
let resizeTimer: ReturnType<typeof setTimeout> | undefined;
function onResize() {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (store.open && isPdf.value) void renderPdf();
  }, 250);
}
window.addEventListener('resize', onResize);
onBeforeUnmount(() => window.removeEventListener('resize', onResize));
</script>

<style scoped>
.viewer--large {
  width: min(1000px, 94vw);
  max-width: 94vw;
  height: 90vh;
}

.viewer__bar {
  gap: 2px;
}

.zoom-label {
  min-width: 44px;
  text-align: center;
}

.viewer__body {
  background: var(--app-page-bg, #f1f5f9);
}

.viewer__pages {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px;
}

.viewer__pages :deep(.viewer__page) {
  background: #fff;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.2);
  max-width: none;
}

.viewer__image {
  padding: 16px;
  text-align: center;
}

.viewer__image img {
  max-width: none;
  height: auto;
}
</style>
