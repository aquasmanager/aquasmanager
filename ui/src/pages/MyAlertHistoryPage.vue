<template>
  <div>
    <PageHeader section :title="t('alerts.historyTitle')" :subtitle="t('alerts.historySubtitle')">
      <template v-if="items.length > 0" #actions>
        <q-btn-toggle
          v-model="filter"
          dense
          unelevated
          toggle-color="primary"
          color="grey-2"
          text-color="grey-8"
          :options="[
            { label: t('alerts.filterAll'), value: 'all' },
            { label: t('alerts.filterOpen'), value: 'open' },
            { label: t('alerts.filterResolved'), value: 'resolved' },
          ]"
        />
      </template>
    </PageHeader>

    <div v-if="loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="visibleItems.length === 0"
      icon="history"
      :title="items.length === 0 ? t('alerts.noHistory') : t('alerts.noFilterMatch')"
      :message="t('alerts.historyMessage')"
    />

    <q-card v-else flat bordered>
      <q-list separator>
      <q-item v-for="item in visibleItems" :key="`${item.kind}-${item.id}`">
        <q-item-section avatar>
          <q-icon :name="item.icon" :color="item.resolved ? 'grey-5' : item.color" />
        </q-item-section>
        <q-item-section>
          <q-item-label>
            <span class="text-weight-bold">{{ item.title }}</span>
            <q-badge v-if="!item.resolved" color="negative" rounded class="q-ml-sm">{{ t('alerts.open') }}</q-badge>
            <q-badge v-else-if="item.acknowledged" color="grey-6" rounded class="q-ml-sm">{{ t('alerts.acknowledged') }}</q-badge>
          </q-item-label>
          <q-item-label caption>{{ item.message }}</q-item-label>
          <q-item-label caption class="text-grey-7">
            {{ formatDateTime(item.created_at) }}
            <template v-if="item.resolved_at"> {{ t('alerts.resolvedOn', { date: formatDateTime(item.resolved_at) }) }}</template>
          </q-item-label>
        </q-item-section>
      </q-item>
      </q-list>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useEquipmentStore } from 'src/stores/equipmentStore';
import { useFaultStore, faultTitle, type EquipmentFault } from 'src/stores/faultStore';
import { useMetricAlertStore } from 'src/stores/metricAlertStore';
import { METRIC_ALERT_ICONS, metricAlertMessage, type MetricAlert, type MetricAlertSource } from 'src/types/metricAlert';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { formatDateTime } from 'src/utils/format';

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const { t } = useI18n();
const equipmentStore = useEquipmentStore();
const faultStore = useFaultStore();
const metricAlertStore = useMetricAlertStore();

const loading = ref(true);
const faults = ref<EquipmentFault[]>([]);
const metricAlerts = ref<MetricAlert[]>([]);

onMounted(async () => {
  loading.value = true;
  try {
    await Promise.all([
      equipmentStore.fetch(),
      faultStore.fetchAll().then((data) => {
        faults.value = data;
      }),
      metricAlertStore.fetchAll(props.aquaId).then((data) => {
        metricAlerts.value = data;
      }),
    ]);
  } finally {
    loading.value = false;
  }
});

const scopedFaults = computed(() => {
  const equipmentIds = new Set(equipmentStore.getByAquariumId(props.aquaId).map((e) => e.id));
  return faults.value.filter((f) => f.equipment_id != null && equipmentIds.has(f.equipment_id));
});

interface HistoryItem {
  kind: 'equipment' | MetricAlertSource;
  id: number;
  icon: string;
  color: string;
  title: string;
  message: string;
  created_at: string;
  resolved_at?: string | null;
  resolved: boolean;
  acknowledged?: boolean;
}

const items = computed<HistoryItem[]>(() => {
  const fromFaults: HistoryItem[] = scopedFaults.value.map((f) => ({
    kind: 'equipment',
    id: f.id,
    icon: 'report_problem',
    color: 'negative',
    title: faultTitle(f),
    message: f.message,
    created_at: f.created_at,
    resolved_at: f.resolved_at,
    resolved: f.resolved_at != null,
  }));

  const fromMetrics: HistoryItem[] = metricAlerts.value.map((a) => ({
    kind: a.source,
    id: a.id,
    icon: METRIC_ALERT_ICONS[a.source],
    color: 'warning',
    title: a.label,
    message: metricAlertMessage(a),
    created_at: a.created_at,
    resolved_at: a.resolved_at ?? null,
    resolved: a.resolved_at != null,
    acknowledged: a.acknowledged,
  }));

  return [...fromFaults, ...fromMetrics].sort((a, b) => b.created_at.localeCompare(a.created_at));
});

const filter = ref<'all' | 'open' | 'resolved'>('all');

const visibleItems = computed(() => {
  if (filter.value === 'open') return items.value.filter((item) => !item.resolved);
  if (filter.value === 'resolved') return items.value.filter((item) => item.resolved);
  return items.value;
});
</script>
