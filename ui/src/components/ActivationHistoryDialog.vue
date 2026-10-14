<!--
  Mises en marche d'un équipement (osmolateur, pompe...) sur une période :
  une barre par mise en marche (durée), statistiques et zoom.
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="bar_chart"
    :title="t('dashboard.detail.activations')"
    :subtitle="title"
    width="860px"
    :cancel-label="t('common.close')"
    hide-submit
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
  >
    <div class="row items-center justify-between gap-sm">
      <q-btn-toggle
        v-model="period"
        unelevated
        dense
        toggle-color="primary"
        color="grey-2"
        text-color="grey-8"
        :options="periods"
        @update:model-value="load"
      />
      <q-spinner v-if="loading" color="primary" size="1.5em" />
    </div>

    <div v-if="activations" class="row q-col-gutter-sm">
      <div v-for="stat in stats" :key="stat.label" class="col-6 col-sm-3">
        <q-card flat bordered class="q-pa-sm text-center">
          <div class="text-caption text-grey-7">{{ stat.label }}</div>
          <div class="text-h6 text-weight-bold">{{ stat.value }}</div>
        </q-card>
      </div>
    </div>

    <div v-if="activations && activations.length === 0" class="text-center text-grey-6 q-py-xl">
      <q-icon name="insights" size="40px" color="grey-5" />
      <div class="q-mt-sm">{{ t('dashboard.detail.none') }}</div>
    </div>
    <v-chart v-else-if="activations" :option="chartOption" style="height: 320px" autoresize />
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import axios from 'axios';
import { date as qdate, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { EChartsOption } from 'echarts';
import FormDialog from 'src/components/FormDialog.vue';
import type { EquipmentActivation } from 'src/types/dashboard';
import { apiErrorMessage } from 'src/utils/apiError';
import { axisStyle, chartBase, chartColors, escapeHtml } from 'src/utils/chart';
import { formatDateTime } from 'src/utils/format';

type Period = '24h' | '7d' | '30d' | '90d';
const PERIOD_DAYS: Record<Period, number> = { '24h': 1, '7d': 7, '30d': 30, '90d': 90 };

const props = defineProps<{
  modelValue: boolean;
  equipmentId: number | null;
  title?: string | undefined;
  initialPeriod?: string | null | undefined;
}>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const period = ref<Period>('7d');
const loading = ref(false);
const activations = ref<EquipmentActivation[] | null>(null);

const periods = computed(() =>
  (Object.keys(PERIOD_DAYS) as Period[]).map((value) => ({ label: t(`dashboard.detail.periods.${value}`), value })),
);

function reset() {
  period.value = (Object.keys(PERIOD_DAYS) as Period[]).find((p) => p === props.initialPeriod) ?? '7d';
  activations.value = null;
  void load();
}

async function load() {
  if (!props.equipmentId) return;
  loading.value = true;
  try {
    const since = new Date(Date.now() - PERIOD_DAYS[period.value] * 86400_000).toISOString();
    const { data } = await axios.get<EquipmentActivation[]>(`/equipments/${props.equipmentId}/activations`, {
      params: { since, limit: 5000 },
    });
    activations.value = [...data].reverse();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('dashboard.detail.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

// 45 s, 3 min 20 s, 1 h 05
function formatDuration(seconds: number): string {
  const s = Math.round(seconds);
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min${s % 60 ? ` ${s % 60} s` : ''}`;
  const minutes = Math.round((s % 3600) / 60);
  return `${Math.floor(s / 3600)} h${minutes ? ` ${String(minutes).padStart(2, '0')}` : ''}`;
}

const durations = computed(() => (activations.value ?? []).map((a) => a.duration_seconds ?? 0));

const stats = computed(() => {
  const list = durations.value;
  const total = list.reduce((a, b) => a + b, 0);
  return [
    { label: t('dashboard.detail.count'), value: String(list.length) },
    { label: t('dashboard.detail.total'), value: formatDuration(total) },
    { label: t('dashboard.detail.average'), value: list.length ? formatDuration(total / list.length) : '—' },
    { label: t('dashboard.detail.longest'), value: list.length ? formatDuration(Math.max(...list)) : '—' },
  ];
});

const chartOption = computed<EChartsOption>(() => {
  const dark = $q.dark.isActive;
  const c = chartColors(dark);
  const axis = axisStyle(dark);
  const list = activations.value ?? [];
  return {
    ...chartBase(dark),
    grid: { left: 8, right: 16, top: 16, bottom: 44, containLabel: true },
    toolbox: {
      right: 8,
      top: 0,
      iconStyle: { borderColor: c.text },
      feature: {
        dataZoom: { yAxisIndex: 'none', title: { zoom: t('chart.zoom'), back: t('chart.zoomBack') } },
        restore: { title: t('chart.reset') },
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
      { type: 'slider', xAxisIndex: 0, height: 18, bottom: 6, brushSelect: false, textStyle: { color: c.text } },
    ],
    xAxis: {
      type: 'time',
      ...axis,
      splitLine: { show: false },
      axisLabel: { ...axis.axisLabel, hideOverlap: true, formatter: (v: number) => qdate.formatDate(v, period.value === '24h' ? 'HH:mm' : 'DD/MM') },
    },
    yAxis: { type: 'value', ...axis, axisLabel: { ...axis.axisLabel, formatter: (v: number) => formatDuration(v) } },
    tooltip: {
      ...chartBase(dark).tooltip,
      trigger: 'item',
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params;
        const [ts, seconds] = (p?.value ?? [0, 0]) as [number, number];
        return `<b>${escapeHtml(formatDateTime(new Date(ts)))}</b><br>${escapeHtml(t('dashboard.detail.duration'))} : <b>${formatDuration(seconds)}</b>`;
      },
    },
    series: [
      {
        type: 'bar',
        name: t('dashboard.detail.duration'),
        color: c.accent,
        barMaxWidth: 14,
        data: list.map((a) => [new Date(a.started_at).getTime(), a.duration_seconds ?? 0]),
      },
    ],
  };
});
</script>
