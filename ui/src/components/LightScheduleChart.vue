<template>
  <v-chart :option="option" :style="{ height: `${height}px` }" autoresize />
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import type { EChartsOption, LineSeriesOption } from 'echarts';
import type { LightChannel } from 'src/types/light';
import { axisStyle, chartBase, dot, escapeHtml } from 'src/utils/chart';
import { DAY_MINUTES, formatMinute, interpolate, programLevel, visibleColor } from 'src/utils/lightSchedule';

const $q = useQuasar();

const { t } = useI18n();
const props = withDefaults(
  defineProps<{
    channels: LightChannel[];
    nowMinute?: number | null;
    playhead?: number | null;
    height?: number;
    highlightId?: number | null;
  }>(),
  { nowMinute: null, playhead: null, height: 260, highlightId: null },
);

// Courbe programmée sur 24 h : on ajoute 00:00 et 24:00 (valeurs interpolées) pour
// montrer le passage de minuit comme le firmware le calcule.
function points(ch: LightChannel): [number, number][] {
  const pts = [...ch.schedule].sort((a, b) => a.minute - b.minute);
  if (pts.length === 0) return [[0, 0], [DAY_MINUTES, 0]];
  const edge = Math.round(interpolate(pts, 0));
  return [[0, edge], ...pts.map((p): [number, number] => [p.minute, p.intensity]), [DAY_MINUTES, edge]];
}

// Courbe réellement produite (clair de lune, plafond, seuil) : échantillonnée toutes les
// 2 minutes, plus les points du programme pour garder les angles nets.
function effectivePoints(ch: LightChannel): [number, number][] {
  const minutes = new Set<number>(ch.schedule.map((p) => p.minute));
  for (let m = 0; m <= DAY_MINUTES; m += 2) minutes.add(m);
  return [...minutes].sort((a, b) => a - b).map((m): [number, number] => [m, Math.round(programLevel(ch, m % DAY_MINUTES) * 10) / 10]);
}

// Le programme dépasse-t-il ce que le canal produit vraiment (plafond, seuil) ?
function isClipped(ch: LightChannel): boolean {
  return ch.schedule.some((p) => p.intensity > ch.max_intensity || (p.intensity > 0 && p.intensity < ch.min_intensity));
}

const option = computed<EChartsOption>(() => {
  const dark = $q.dark.isActive;
  const axis = axisStyle(dark);
  const marks = [
    ...(props.nowMinute != null
      ? [{ xAxis: props.nowMinute, lineStyle: { color: '#94a3b8', type: 'dashed' as const }, label: { formatter: t('chart.now'), color: '#94a3b8' } }]
      : []),
    ...(props.playhead != null
      ? [{ xAxis: props.playhead, lineStyle: { color: '#f59e0b', width: 2 }, label: { formatter: formatMinute(props.playhead), color: '#f59e0b' } }]
      : []),
  ];
  const series: LineSeriesOption[] = props.channels.map((ch) => {
    const color = visibleColor(ch.color, dark);
    const strong = props.highlightId == null || ch.id === props.highlightId;
    return {
      type: 'line',
      name: ch.name,
      data: effectivePoints(ch),
      color,
      lineStyle: { width: strong ? 3 : 1 },
      showSymbol: false,
      emphasis: { disabled: true },
    };
  });
  // Canal sélectionné : programme saisi (pointillés, avec ses points) et plafond, s'ils diffèrent du réel
  const focused = props.channels.find((ch) => ch.id === props.highlightId);
  if (focused) {
    const color = visibleColor(focused.color, dark);
    const clipped = isClipped(focused);
    series.push({
      type: 'line',
      name: '',
      data: points(focused),
      color,
      lineStyle: { width: 1, type: 'dashed', opacity: clipped ? 0.8 : 0 },
      showSymbol: true,
      symbolSize: 6,
      silent: true,
      emphasis: { disabled: true },
      ...(focused.max_intensity < 100
        ? {
            markLine: {
              symbol: 'none',
              silent: true,
              data: [{ yAxis: focused.max_intensity, lineStyle: { color, type: 'dotted' as const }, label: { formatter: t('lights.chart.ceiling', { n: focused.max_intensity }), color, position: 'insideEndTop' as const } }],
            },
          }
        : {}),
    });
  }
  // Repères « maintenant » et tête de lecture, même sans canal
  series.push({ type: 'line', name: '', data: [], markLine: { symbol: 'none', silent: true, data: marks } });
  return {
    ...chartBase(dark),
    grid: { left: 8, right: 16, top: 24, bottom: props.channels.length > 1 ? 40 : 8, containLabel: true },
    legend: { ...chartBase(dark).legend, show: props.channels.length > 1, bottom: 0, data: props.channels.map((ch) => ch.name) },
    xAxis: {
      type: 'value',
      min: 0,
      max: DAY_MINUTES,
      // Téléphone : une graduation toutes les 4 h au lieu de 2 h
      interval: $q.screen.lt.sm ? 240 : 120,
      ...axis,
      splitLine: { show: false },
      axisLabel: { ...axis.axisLabel, formatter: (v: number) => formatMinute(v) },
    },
    yAxis: { type: 'value', min: 0, max: 100, interval: 25, ...axis, axisLabel: { ...axis.axisLabel, formatter: '{value} %' } },
    tooltip: {
      ...chartBase(dark).tooltip,
      trigger: 'axis',
      // Intensité de chaque canal à l'instant survolé, interpolée comme le firmware
      formatter: (params) => {
        const first = (Array.isArray(params) ? params[0] : params) as { axisValue?: number | string } | undefined;
        const minute = Math.round(Number(first?.axisValue ?? NaN));
        if (!props.channels.length || Number.isNaN(minute)) return '';
        const rows = props.channels.map((ch) => {
          const pts = [...ch.schedule].sort((a, b) => a.minute - b.minute);
          const programmed = pts.length ? Math.round(interpolate(pts, minute % DAY_MINUTES)) : 0;
          const value = Math.round(programLevel(ch, minute % DAY_MINUTES));
          const note = value !== programmed ? ` <span style="opacity:.7">(${t('lights.chart.programmed', { n: programmed })})</span>` : '';
          return `${dot(visibleColor(ch.color, dark))}${escapeHtml(ch.name)} : <b>${value} %</b>${note}`;
        });
        return [`<b>${formatMinute(minute)}</b>`, ...rows].join('<br>');
      },
    },
    series,
  };
});
</script>
