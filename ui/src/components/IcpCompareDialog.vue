<template>
  <q-dialog :model-value="modelValue" @update:model-value="(v: boolean) => emit('update:modelValue', v)" @show="loadBatches" @hide="reset">
    <q-card style="width: 760px; max-width: 95vw">
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar size="40px" color="blue-1" text-color="primary" icon="compare_arrows" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ t('params.icp.compareTitle') }}</div>
          <div class="text-body2 text-grey-7">{{ t('params.icp.compareSubtitle') }}</div>
        </div>
        <q-btn flat round dense icon="close" color="grey-7" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>
      <q-separator />

      <q-card-section v-if="loadingBatches" class="text-center q-py-lg">
        <q-spinner color="primary" size="2em" />
      </q-card-section>

      <q-card-section v-else-if="batches.length === 0" class="text-center text-grey-6 q-py-lg">
        {{ t('params.icp.noBatch') }}
      </q-card-section>

      <template v-else>
        <q-card-section class="q-gutter-xs">
          <q-item v-for="b in batches" :key="b.id" dense class="q-pa-none">
            <q-item-section side>
              <q-checkbox v-model="selectedIds" :val="b.id" />
            </q-item-section>
            <q-item-section>{{ formatShortDate(b.sample_date) }} — {{ b.lab.toUpperCase() }}</q-item-section>
            <q-item-section side>
              <div class="row no-wrap items-center">
                <q-btn
                  v-if="b.pdf_filename"
                  flat
                  round
                  dense
                  icon="picture_as_pdf"
                  color="red-8"
                  size="sm"
                  @click="openPdf(b)"
                >
                  <q-tooltip>{{ t('params.icp.viewReport', { name: b.pdf_filename }) }}</q-tooltip>
                </q-btn>
                <q-btn
                  v-else
                  flat
                  round
                  dense
                  icon="attach_file"
                  color="grey-6"
                  size="sm"
                  :loading="uploadingBatchId === b.id"
                  @click="pickPdf(b)"
                >
                  <q-tooltip>{{ t('params.icp.attachPdf') }}</q-tooltip>
                </q-btn>
                <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" size="sm" @click="removeBatch(b)" />
              </div>
            </q-item-section>
          </q-item>
          <input ref="pdfInput" type="file" accept="application/pdf,.pdf" class="hidden" @change="onPdfPicked" />
        </q-card-section>

        <q-card-section v-if="comparison.length > 0" style="max-height: 50vh; overflow-y: auto">
          <q-markup-table flat dense separator="cell">
            <thead>
              <tr>
                <th class="text-left">{{ t('params.icp.param') }}</th>
                <th v-for="b in selectedBatches" :key="b.id" class="text-right">{{ formatShortDate(b.sample_date) }}</th>
                <th v-if="selectedBatches.length === 2" class="text-right">{{ t('params.icp.change') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in comparison" :key="row.name">
                <td class="text-left">{{ row.name }} <span class="text-grey-6">{{ row.unit }}</span></td>
                <td v-for="v in row.values" :key="v.batchId" class="text-right">
                  {{ v.value ?? '—' }}
                </td>
                <td v-if="selectedBatches.length === 2" class="text-right">
                  <q-chip
                    v-if="row.delta !== null"
                    dense
                    :color="row.deltaColor"
                    text-color="white"
                    class="text-weight-bold"
                  >
                    <!-- i18n-ignore : expression, pas un texte -->
                    <q-icon :name="row.delta > 0 ? 'arrow_upward' : row.delta < 0 ? 'arrow_downward' : 'remove'" size="xs" class="q-mr-xs" />
                    {{ row.delta > 0 ? '+' : '' }}{{ formatNumber(row.delta) }}
                  </q-chip>
                  <span v-else class="text-grey-5">—</span>
                </td>
              </tr>
            </tbody>
          </q-markup-table>
        </q-card-section>
      </template>

      <q-separator />
      <q-card-actions align="right" class="q-px-md q-py-sm">
        <q-btn flat :label="t('common.close')" color="grey-8" @click="close" />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { formatDate, formatNumber } from 'src/utils/format';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { usePermissions } from 'src/composables/usePermissions';
import { useWaterParameterStore } from 'src/stores/waterParameterStore';
import type { IcpImportBatch, IcpBatchReading } from 'src/types/waterParameter';

const props = defineProps<{
  modelValue: boolean;
  aquaId: number;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const { t } = useI18n();
const store = useWaterParameterStore();

const loadingBatches = ref(false);
const batches = ref<IcpImportBatch[]>([]);
const selectedIds = ref<number[]>([]);
const readingsByBatch = ref<Record<number, IcpBatchReading[]>>({});

const selectedBatches = computed(() =>
  batches.value.filter((b) => selectedIds.value.includes(b.id)).sort((a, b) => a.sample_date.localeCompare(b.sample_date)),
);

interface ComparisonRow {
  name: string;
  unit: string;
  values: { batchId: number; value: number | null }[];
  delta: number | null;
  deltaColor: string;
}

const comparison = computed<ComparisonRow[]>(() => {
  if (selectedBatches.value.length < 2) return [];

  const names = new Set<string>();
  for (const b of selectedBatches.value) {
    for (const r of readingsByBatch.value[b.id] ?? []) names.add(r.name);
  }

  return [...names].sort().map((name) => {
    const values = selectedBatches.value.map((b) => {
      const reading = (readingsByBatch.value[b.id] ?? []).find((r) => r.name === name);
      return { batchId: b.id, value: reading?.value ?? null };
    });
    const unit = selectedBatches.value
      .map((b) => (readingsByBatch.value[b.id] ?? []).find((r) => r.name === name)?.unit)
      .find((u) => !!u) ?? '';

    let delta: number | null = null;
    let deltaColor = 'grey-6';
    if (selectedBatches.value.length === 2) {
      const [first, second] = values;
      if (first?.value != null && second?.value != null) {
        delta = Number((second.value - first.value).toFixed(4));
        const param = store.parameters.find((p) => p.name === name);
        if (param && (param.target_min != null || param.target_max != null)) {
          const min = param.target_min ?? -Infinity;
          const max = param.target_max ?? Infinity;
          const distanceBefore = first.value < min ? min - first.value : first.value > max ? first.value - max : 0;
          const distanceAfter = second.value < min ? min - second.value : second.value > max ? second.value - max : 0;
          deltaColor = distanceAfter < distanceBefore ? 'positive' : distanceAfter > distanceBefore ? 'negative' : 'grey-6';
        }
      }
    }

    return { name, unit: unit ?? '', values, delta, deltaColor };
  });
});

function formatShortDate(dateStr?: string | null): string {
  if (!dateStr) return '';
  return formatDate(dateStr);
}

function close() {
  emit('update:modelValue', false);
}

function reset() {
  selectedIds.value = [];
  readingsByBatch.value = {};
}

async function loadBatches() {
  loadingBatches.value = true;
  try {
    batches.value = await store.fetchIcpBatches(props.aquaId);
    // Par défaut : compare les deux tests les plus récents.
    selectedIds.value = batches.value.slice(-2).map((b) => b.id);
  } finally {
    loadingBatches.value = false;
  }
}

const pdfInput = ref<HTMLInputElement | null>(null);
const pdfTargetBatch = ref<IcpImportBatch | null>(null);
const uploadingBatchId = ref<number | null>(null);

function pickPdf(batch: IcpImportBatch) {
  pdfTargetBatch.value = batch;
  pdfInput.value?.click();
}

async function onPdfPicked(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  const batch = pdfTargetBatch.value;
  input.value = '';
  if (!file || !batch) return;
  uploadingBatchId.value = batch.id;
  try {
    const updated = await store.uploadIcpBatchPdf(batch.id, file);
    batches.value = batches.value.map((b) => (b.id === updated.id ? updated : b));
    $q.notify({ type: 'positive', message: t('params.icp.pdfAttached') });
  } catch (err: unknown) {
    const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
    $q.notify({ type: 'negative', message: detail ?? t('params.icp.pdfUploadFailed') });
  } finally {
    uploadingBatchId.value = null;
  }
}

async function openPdf(batch: IcpImportBatch) {
  // Ouverture synchrone (avant l'await) pour ne pas être bloquée comme popup
  const tab = window.open('', '_blank');
  try {
    const blob = await store.fetchIcpBatchPdf(batch.id);
    const url = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }));
    if (tab) tab.location.href = url;
    else window.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch {
    tab?.close();
    $q.notify({ type: 'negative', message: t('params.icp.pdfOpenFailed') });
  }
}

function removeBatch(batch: IcpImportBatch) {
  confirmRemove(
    t('params.icp.batchItem', { date: formatShortDate(batch.sample_date) }),
    async () => {
      await store.deleteIcpBatch(batch.id);
      batches.value = batches.value.filter((b) => b.id !== batch.id);
      selectedIds.value = selectedIds.value.filter((id) => id !== batch.id);
      delete readingsByBatch.value[batch.id];
    },
    {
      message: t('params.icp.batchDeleteMessage', { date: formatShortDate(batch.sample_date) }),
    },
  );
}

watch(selectedIds, async (ids) => {
  await Promise.all(
    ids
      .filter((id) => !readingsByBatch.value[id])
      .map(async (id) => {
        readingsByBatch.value[id] = await store.fetchIcpBatchReadings(id);
      }),
  );
});
</script>
