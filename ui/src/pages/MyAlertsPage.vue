<template>
  <div>
    <PageHeader section :title="t('alerts.title')" :subtitle="t('alerts.subtitle')" />

    <div v-if="loading" class="text-center q-py-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="items.length === 0"
      icon="check_circle"
      icon-color="positive"
      :title="t('alerts.allGood')"
      :message="t('alerts.allGoodMessage')"
    />

    <div v-else class="row q-col-gutter-md">
      <div v-for="item in items" :key="`${item.kind}-${item.id}`" class="col-12 col-sm-6 col-md-4">
        <q-card flat bordered class="full-height q-pa-sm column">
          <q-card-section class="row items-center no-wrap q-pb-xs">
            <q-avatar size="36px" :color="item.color === 'negative' ? 'red-1' : 'orange-1'" :text-color="item.color" :icon="item.icon" class="q-mr-sm" />
            <div class="text-subtitle1 text-weight-bold">{{ item.title }}</div>
          </q-card-section>
          <q-card-section class="q-pt-none col">
            <div class="text-body2">{{ item.message }}</div>
            <div class="text-caption text-grey-7 q-mt-xs">{{ t('alerts.since', { date: formatDateTime(item.created_at) }) }}</div>
          </q-card-section>
          <q-card-actions v-if="can.edit" align="right">
            <q-btn
              v-if="item.kind === 'equipment' && item.latched"
              unelevated
              dense
              class="q-px-sm"
              color="negative"
              :label="t('alerts.reset')"
              icon="restart_alt"
              @click="clearFault(item)"
            />
            <q-btn
              v-else
              flat
              dense
              class="q-px-sm"
              color="grey-8"
              :label="t('alerts.acknowledge')"
              icon="done"
              @click="acknowledgeItem(item)"
            >
              <q-tooltip>{{ t('alerts.acknowledgeHelp') }}</q-tooltip>
            </q-btn>
          </q-card-actions>
        </q-card>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { usePermissions } from 'src/composables/usePermissions';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useEquipmentStore } from 'src/stores/equipmentStore';
import { useFaultStore, faultTitle, type EquipmentFault } from 'src/stores/faultStore';
import { useMetricAlertStore } from 'src/stores/metricAlertStore';
import { METRIC_ALERT_ICONS, metricAlertMessage, type MetricAlertSource } from 'src/types/metricAlert';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { formatDateTime } from 'src/utils/format';

const props = defineProps({
  aquaId: { type: Number, required: true },
});

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const equipmentStore = useEquipmentStore();
const faultStore = useFaultStore();
const metricAlertStore = useMetricAlertStore();

const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    await Promise.all([equipmentStore.fetch(), faultStore.fetchOpen(), metricAlertStore.fetchOpen(props.aquaId)]);
  } finally {
    loading.value = false;
  }
}

onMounted(load);

const scopedFaults = computed(() => {
  const equipmentIds = new Set(equipmentStore.getByAquariumId(props.aquaId).map((e) => e.id));
  return faultStore.openFaults.filter((f) => f.equipment_id != null && equipmentIds.has(f.equipment_id));
});

interface AlertItem {
  kind: 'equipment' | MetricAlertSource;
  id: number;
  icon: string;
  color: string;
  title: string;
  message: string;
  created_at: string;
  latched?: boolean;
  fault?: EquipmentFault;
}

const items = computed<AlertItem[]>(() => {
  const fromFaults: AlertItem[] = scopedFaults.value.map((f) => ({
    kind: 'equipment',
    id: f.id,
    icon: 'report_problem',
    color: 'negative',
    title: faultTitle(f),
    message: f.message,
    created_at: f.created_at,
    latched: f.latched,
    fault: f,
  }));

  const fromMetrics: AlertItem[] = metricAlertStore.openAlerts.map((a) => ({
    kind: a.source,
    id: a.id,
    icon: METRIC_ALERT_ICONS[a.source],
    color: 'warning',
    title: a.label,
    message: metricAlertMessage(a),
    created_at: a.created_at,
  }));

  return [...fromFaults, ...fromMetrics].sort((a, b) => b.created_at.localeCompare(a.created_at));
});

async function clearFault(item: AlertItem) {
  if (!item.fault?.equipment_id) return;
  try {
    await faultStore.clearEquipmentFault(item.fault.equipment_id);
    $q.notify({ type: 'positive', message: t('layout.faultResetSent') });
  } catch {
    $q.notify({ type: 'negative', message: t('layout.faultResetFailed') });
  }
}

async function acknowledgeItem(item: AlertItem) {
  try {
    if (item.kind === 'equipment') {
      if (!item.fault) return;
      await faultStore.acknowledge(item.fault.id);
    } else {
      // metricAlertStore.acknowledge() retire l'alerte de l'état partagé :
      // le badge de l'onglet (AquariumPage) se met à jour au même moment.
      await metricAlertStore.acknowledge(item.id);
    }
  } catch {
    $q.notify({ type: 'negative', message: t('layout.faultAckFailed') });
  }
}

</script>
