<!--
  Zone de signature au doigt, au stylet ou à la souris. v-model : image PNG
  (data URL, fond transparent), chaîne vide tant que rien n'est tracé.
-->
<template>
  <div class="signature-pad">
    <canvas
      ref="canvas"
      class="signature-pad__canvas"
      @pointerdown="start"
      @pointermove="move"
      @pointerup="end"
      @pointerleave="end"
      @pointercancel="end"
    />
    <div v-if="!modelValue" class="signature-pad__hint text-grey-5">{{ t('frags.signaturePad.hint') }}</div>
    <q-btn
      v-if="modelValue"
      flat
      dense
      no-caps
      size="sm"
      icon="restart_alt"
      :label="t('frags.signaturePad.clear')"
      color="grey-8"
      class="signature-pad__clear"
      @click="clear"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

defineProps<{ modelValue: string }>();
const { t } = useI18n();
const emit = defineEmits<{ 'update:modelValue': [value: string] }>();

const canvas = ref<HTMLCanvasElement | null>(null);
let ctx: CanvasRenderingContext2D | null = null;
let drawing = false;
let last: { x: number; y: number } | null = null;
let hasInk = false;

let cssWidth = 0;

// Le clavier mobile qui se ferme déclenche un « resize » : on ne retaille le
// canevas que si sa largeur change vraiment, en gardant le tracé en cours.
function resize() {
  const el = canvas.value;
  if (!el) return;
  const { width, height } = el.getBoundingClientRect();
  if (!width || Math.round(width) === cssWidth) return;
  const previous = hasInk ? el.toDataURL('image/png') : null;
  cssWidth = Math.round(width);
  const ratio = window.devicePixelRatio || 1;
  el.width = Math.round(width * ratio);
  el.height = Math.round(height * ratio);
  ctx = el.getContext('2d');
  if (!ctx) return;
  ctx.scale(ratio, ratio);
  ctx.lineWidth = 2.4;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.strokeStyle = '#1a237e';
  if (previous) {
    const image = new Image();
    image.onload = () => ctx?.drawImage(image, 0, 0, width, height);
    image.src = previous;
  }
}

function point(event: PointerEvent) {
  const rect = canvas.value!.getBoundingClientRect();
  return { x: event.clientX - rect.left, y: event.clientY - rect.top };
}

function start(event: PointerEvent) {
  if (!ctx) return;
  drawing = true;
  last = point(event);
  canvas.value?.setPointerCapture(event.pointerId);
  ctx.beginPath();
  ctx.arc(last.x, last.y, 1.2, 0, Math.PI * 2);
  ctx.fillStyle = '#1a237e';
  ctx.fill();
  hasInk = true;
}

function move(event: PointerEvent) {
  if (!drawing || !ctx || !last) return;
  const current = point(event);
  ctx.beginPath();
  ctx.moveTo(last.x, last.y);
  ctx.lineTo(current.x, current.y);
  ctx.stroke();
  last = current;
}

function end() {
  if (!drawing) return;
  drawing = false;
  last = null;
  if (hasInk && canvas.value) emit('update:modelValue', canvas.value.toDataURL('image/png'));
}

function clear() {
  const el = canvas.value;
  if (el && ctx) ctx.clearRect(0, 0, el.width, el.height);
  hasInk = false;
  emit('update:modelValue', '');
}

onMounted(() => {
  resize();
  window.addEventListener('resize', resize);
});
onBeforeUnmount(() => window.removeEventListener('resize', resize));
</script>

<style scoped>
.signature-pad {
  position: relative;
  height: 180px;
  border: 1px dashed var(--app-border-color);
  border-radius: 10px;
  background: #fff;
}

.signature-pad__canvas {
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
  cursor: crosshair;
}

.signature-pad__hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  font-size: 18px;
}

.signature-pad__clear {
  position: absolute;
  top: 4px;
  right: 4px;
}
</style>
