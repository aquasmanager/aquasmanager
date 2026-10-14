<!--
  Historique d'un capteur sur 24 h / 7 j / 30 j / 90 j (moyenne, minimum et
  maximum par intervalle), ou d'un paramètre saisi à la main (relevés un par
  un, jusqu'à tout l'historique). Zoom : molette, pincement ou barre du bas.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    :icon="isBinary ? 'water' : 'show_chart'"
    :title="t('sensors.history')"
    :subtitle="parameter ? parameter.full_name || parameter.name : sensor?.name"
    width="860px"
    :cancel-label="t('common.close')"
    hide-submit
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset(initialPeriod)"
  >
    <div class="row items-center justify-between gap-sm">
      <q-btn-toggle
        v-model="period"
        unelevated
        dense
        toggle-color="primary"
        color="grey-2"
        text-color="grey-8"
        :options="PERIODS"
        @update:model-value="load"
      />
      <q-spinner v-if="loading" color="primary" size="1.5em" />
    </div>

    <div v-if="history && !isBinary" class="row q-col-gutter-sm">
      <div v-for="stat in stats" :key="stat.label" class="col-6 col-sm-3">
        <q-card flat bordered class="q-pa-sm text-center">
          <div class="text-caption text-grey-7">{{ stat.label }}</div>
          <div class="text-h6 text-weight-bold">{{ stat.value }}</div>
        </q-card>
      </div>
    </div>

    <div v-if="history && history.points.length === 0" class="text-center text-grey-6 q-py-xl">
      <q-icon name="insights" size="40px" color="grey-5" />
      <div class="q-mt-sm">{{ t('sensors.historyDialog.noData') }}</div>
    </div>
    <v-chart v-else-if="history" :option="chartOption" style="height: 320px" autoresize />
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { date as qdate, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { EChartsOption, LineSeriesOption } from 'echarts';
import FormDialog from 'src/components/FormDialog.vue';
import { useMetricsStore } from 'src/stores/metricsStore';
import { useWaterParameterStore } from 'src/stores/waterParameterStore';
import type { WaterParameter } from 'src/types/waterParameter';
import type { Sensor, SensorHistory, SensorHistoryPeriod } from 'src/types/sensor';
import { apiErrorMessage } from 'src/utils/apiError';
import { axisStyle, chartBase, chartColors, dot, escapeHtml } from 'src/utils/chart';

const props = defineProps<{
  modelValue: boolean;
  sensor: Pick<Sensor, 'id' | 'name' | 'unit' | 'type'> | null;
  // Paramètre saisi à la main (à la place d'un capteur)
  parameter?: Pick<WaterParameter, 'id' | 'name' | 'full_name' | 'unit'> | null | undefined;
  // Période affichée à l'ouverture (celle de la carte du tableau de bord)
  initialPeriod?: string | null | undefined;
  targetMin?: number | null | undefined;
  targetMax?: number | null | undefined;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
type Period = SensorHistoryPeriod | '1y' | 'all';
const SENSOR_PERIODS: Period[] = ['24h', '7d', '30d', '90d'];
// Relevés manuels : espacés de plusieurs jours, on regarde plus loin
const PARAMETER_PERIODS: Period[] = ['30d', '90d', '1y', 'all'];
const PERIOD_DAYS: Record<Exclude<Period, 'all'>, number> = { '24h': 1, '7d': 7, '30d': 30, '90d': 90, '1y': 365 };
const PERIODS = computed(() =>
  (props.parameter ? PARAMETER_PERIODS : SENSOR_PERIODS).map((value) => ({ label: t(`dashboard.detail.periods.${value}`), value })),
);

const $q = useQuasar();
const metricsStore = useMetricsStore();
const waterParameterStore = useWaterParameterStore();
const period = ref<Period>('24h');
const history = ref<SensorHistory | null>(null);
const loading = ref(false);

const isBinary = computed(() => {
  if (props.parameter) return false;
  const unit = (props.sensor?.unit ?? '').toLowerCase();
  return props.sensor?.type === 'binary_sensor' || unit === 'level' || unit === 'niveau';
});
const unitLabel = computed(() => {
  if (props.parameter) return props.parameter.unit ?? '';
  return isBinary.value ? '' : props.sensor?.unit === 'temperature' ? '°C' : props.sensor?.unit ?? '';
});

// Période de départ : celle demandée (carte du tableau de bord), sinon la première proposée
function reset(initial?: string | null) {
  const allowed = PERIODS.value.map((p) => p.value);
  period.value = allowed.find((p) => p === initial) ?? allowed[0]!;
  history.value = null;
  void load();
}

// Relevés manuels mis au même format que l'historique d'un capteur (un point par relevé)
async function parameterHistory(parameterId: number): Promise<SensorHistory> {
  const readings = await waterParameterStore.fetchReadings(parameterId);
  const since = period.value === 'all' ? -Infinity : Date.now() - PERIOD_DAYS[period.value] * 86400_000;
  const kept = readings.filter((r) => new Date(r.timestamp).getTime() >= since);
  const values = kept.map((r) => r.value);
  return {
    sensor_id: 0,
    period: '90d',
    bucket_seconds: 0,
    unit: props.parameter?.unit ?? null,
    start: kept[0]?.timestamp ?? '',
    end: kept.at(-1)?.timestamp ?? '',
    points: kept.map((r) => ({ t: r.timestamp, avg: r.value, min: r.value, max: r.value, last: r.value })),
    stats: {
      count: values.length,
      min: values.length ? Math.min(...values) : null,
      max: values.length ? Math.max(...values) : null,
      avg: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null,
    },
  };
}

async function load() {
  if (!props.sensor && !props.parameter) return;
  loading.value = true;
  try {
    history.value = props.parameter
      ? await parameterHistory(props.parameter.id)
      : await metricsStore.fetchSensorPeriodHistory(props.sensor!.id, period.value as SensorHistoryPeriod);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('sensors.historyDialog.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

function round(value: number | null | undefined): string {
  return value == null ? '—' : `${Number(value).toFixed(1)} ${unitLabel.value}`.trim();
}

const stats = computed(() => {
  const s = history.value?.stats;
  return [
    { label: t('sensors.historyDialog.minimum'), value: round(s?.min) },
    { label: t('sensors.historyDialog.average'), value: round(s?.avg) },
    { label: t('sensors.historyDialog.maximum'), value: round(s?.max) },
    { label: t('sensors.historyDialog.count'), value: String(s?.count ?? 0) },
  ];
});

function formatValue(v: number): string {
  if (isBinary.value) return v >= 0.5 ? t('sensors.historyDialog.high') : t('sensors.historyDialog.low');
  return `${v.toFixed(1)}${unitLabel.value ? ` ${unitLabel.value}` : ''}`;
}

const chartOption = computed<EChartsOption>(() => {
  const dark = $q.dark.isActive;
  const c = chartColors(dark);
  const axis = axisStyle(dark);
  const points = history.value?.points ?? [];
  const at = (t: string) => new Date(t).getTime();

  let series: LineSeriesOption[];
  if (props.parameter) {
    // Relevés ponctuels : une ligne droite de point en point, points visibles
    const hasTarget = props.targetMin != null || props.targetMax != null;
    series = [
      {
        type: 'line', name: props.parameter.name, showSymbol: true, symbolSize: 7, color: c.accent, lineStyle: { width: 2.5 },
        data: points.map((p) => [at(p.t), p.avg]),
        ...(hasTarget
          ? {
              markArea: {
                silent: true,
                itemStyle: { color: c.ok, opacity: 0.08 },
                label: { show: true, position: 'insideTopLeft', color: c.ok, formatter: t('sensors.historyDialog.target') },
                data: [[
                  { yAxis: props.targetMin ?? history.value?.stats.min ?? 0 },
                  { yAxis: props.targetMax ?? history.value?.stats.max ?? 0 },
                ]],
              },
            }
          : {}),
      },
    ];
  } else if (isBinary.value) {
    series = [
      { type: 'line', name: t('sensors.historyDialog.level'), step: 'end', showSymbol: false, color: c.accent, lineStyle: { width: 2 },
        data: points.map((p) => [at(p.t), p.last >= 1 ? 1 : 0]) },
    ];
  } else {
    const hasTarget = props.targetMin != null || props.targetMax != null;
    series = [
      {
        type: 'line', name: t('sensors.historyDialog.average'), showSymbol: false, color: dark ? '#fb7185' : '#e11d48', lineStyle: { width: 2.5 },
        data: points.map((p) => [at(p.t), p.avg]),
        ...(hasTarget
          ? {
              markArea: {
                silent: true,
                itemStyle: { color: c.ok, opacity: 0.08 },
                label: { show: true, position: 'insideTopLeft', color: c.ok, formatter: t('sensors.historyDialog.target') },
                data: [[
                  { yAxis: props.targetMin ?? history.value?.stats.min ?? 0 },
                  { yAxis: props.targetMax ?? history.value?.stats.max ?? 0 },
                ]],
              },
            }
          : {}),
      },
      { type: 'line', name: t('sensors.historyDialog.maximum'), showSymbol: false, color: '#fda4af', lineStyle: { width: 1, type: 'dashed' },
        data: points.map((p) => [at(p.t), p.max]) },
      { type: 'line', name: t('sensors.historyDialog.minimum'), showSymbol: false, color: dark ? '#7dd3fc' : '#38bdf8', lineStyle: { width: 1, type: 'dashed' },
        data: points.map((p) => [at(p.t), p.min]) },
    ];
  }

  const timeFormat = period.value === '24h' ? 'HH:mm' : 'DD/MM HH:mm';
  return {
    ...chartBase(dark),
    grid: { left: 8, right: 16, top: isBinary.value || props.parameter ? 16 : 40, bottom: 44, containLabel: true },
    legend: { ...chartBase(dark).legend, show: !isBinary.value && !props.parameter, top: 0 },
    // Zoom : molette / pincement, ou sélection avec l'outil loupe ; bouton pour revenir
    toolbox: { right: 8, top: 0, iconStyle: { borderColor: c.text }, feature: { dataZoom: { yAxisIndex: 'none', title: { zoom: t('chart.zoom'), back: t('chart.zoomBack') } }, restore: { title: t('chart.reset') } } },
    // Zoom : molette / pincement sur le graphique, ou poignées de la barre du bas
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 6, brushSelect: false, textStyle: { color: c.text } },
    ],
    xAxis: {
      type: 'time',
      ...axis,
      splitLine: { show: false },
      axisLabel: {
        ...axis.axisLabel,
        hideOverlap: true,
        formatter: (v: number) => qdate.formatDate(v, period.value === '24h' ? 'HH:mm' : period.value === '1y' || period.value === 'all' ? 'MM/YY' : 'DD/MM'),
      },
    },
    yAxis: isBinary.value
      ? { type: 'value', min: 0, max: 1, interval: 1, ...axis, axisLabel: { ...axis.axisLabel, formatter: (v: number) => formatValue(v) } }
      : { type: 'value', scale: true, ...axis, axisLabel: { ...axis.axisLabel, formatter: (v: number) => formatValue(v) } },
    tooltip: {
      ...chartBase(dark).tooltip,
      trigger: 'axis',
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        if (!list.length) return '';
        const [ts] = list[0]!.value as [number, number];
        const rows = list.map((p) => `${dot(p.color)}${escapeHtml(p.seriesName)} : <b>${formatValue((p.value as [number, number])[1])}</b>`);
        return [`<b>${qdate.formatDate(ts, timeFormat)}</b>`, ...rows].join('<br>');
      },
    },
    series,
  };
});
</script>
