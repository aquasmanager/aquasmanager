<!-- components/SparklineChart.vue -->
<template>
  <div class="sparkline-container">
    <svg :viewBox="`0 0 ${width} ${height}`" class="full-width" style="overflow: visible;">
      <defs>
        <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="color" stop-opacity="0.28" />
          <stop offset="100%" :stop-color="color" stop-opacity="0" />
        </linearGradient>
      </defs>
      <!-- Plage cible en fond -->
      <rect
        v-if="targetBand"
        x="0"
        :y="targetBand.y"
        :width="width"
        :height="targetBand.height"
        rx="3"
        class="sparkline-band"
      />
      <!-- Aire sous la courbe (dégradé) puis courbe lissée -->
      <path v-if="data.length > 1" :d="areaPath" :fill="`url(#${gradientId})`" stroke="none" />
      <path
        v-if="data.length > 1"
        :d="linePath"
        fill="none"
        :stroke="color"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        vector-effect="non-scaling-stroke"
      />
      <!-- Dernier point en surbrillance -->
      <circle
        v-if="lastPoint"
        :cx="lastPoint.x"
        :cy="lastPoint.y"
        :r="isLastOutOfRange ? 4.5 : 4"
        :fill="isLastOutOfRange ? '#F2C037' : color"
        :stroke="isLastOutOfRange ? '#8a6d00' : 'none'"
        stroke-width="1.5"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue';

const gradientId = `spark-${useId()}`;

const props = withDefaults(defineProps<{
  data: number[];
  color?: string;
  width?: number;
  height?: number;
  targetMin?: number | null;
  targetMax?: number | null;
}>(), {
  color: '#027BE3',
  width: 150,
  height: 40,
  targetMin: null,
  targetMax: null,
});

const PADDING = 4;
const hasTarget = computed(() => props.targetMin != null || props.targetMax != null);

// L'échelle englobe aussi la plage cible pour que la bande reste visible
// et que la position de la courbe par rapport à la cible soit fidèle.
const domain = computed(() => {
  const values = [...props.data];
  if (props.targetMin != null) values.push(props.targetMin);
  if (props.targetMax != null) values.push(props.targetMax);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return { min, range: max - min || 1 };
});

function toY(val: number) {
  const { min, range } = domain.value;
  return props.height - ((val - min) / range) * (props.height - PADDING * 2) - PADDING;
}

const coords = computed(() =>
  props.data.map((val, index) => [(index / (props.data.length - 1)) * props.width, toY(val)] as const),
);

// Courbe lissée (Bézier entre points voisins, sans dépasser les valeurs)
const linePath = computed(() => {
  const pts = coords.value;
  if (pts.length === 0) return '';
  let d = `M${pts[0]![0].toFixed(1)},${pts[0]![1].toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const [x0, y0] = pts[i - 1]!;
    const [x1, y1] = pts[i]!;
    const cx = (x0 + x1) / 2;
    d += ` C${cx.toFixed(1)},${y0.toFixed(1)} ${cx.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`;
  }
  return d;
});

const areaPath = computed(() => (linePath.value ? `${linePath.value} L${props.width},${props.height} L0,${props.height} Z` : ''));

const lastPoint = computed(() => {
  const val = props.data[props.data.length - 1];
  if (val === undefined) return null;
  return { x: props.width, y: toY(val), val };
});

const targetBand = computed(() => {
  if (!hasTarget.value || props.data.length === 0) return null;
  const top = props.targetMax != null ? toY(props.targetMax) : 0;
  const bottom = props.targetMin != null ? toY(props.targetMin) : props.height;
  return { y: top, height: Math.max(bottom - top, 2) };
});

const isLastOutOfRange = computed(() => {
  const point = lastPoint.value;
  if (!point) return false;
  return (
    (props.targetMin != null && point.val < props.targetMin) ||
    (props.targetMax != null && point.val > props.targetMax)
  );
});
</script>

<style scoped>
.sparkline-band {
  fill: var(--app-ok);
  fill-opacity: 0.1;
}
</style>
