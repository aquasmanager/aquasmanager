<template>
  <q-dialog :model-value="modelValue" @update:model-value="onDialogUpdate" @hide="reset">
    <q-card style="width: 640px; max-width: 95vw">
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar size="40px" color="blue-1" text-color="primary" icon="upload_file" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ t('params.icp.importTitle') }}</div>
          <div class="text-body2 text-grey-7">{{ t('params.icp.importSubtitle') }}</div>
        </div>
        <q-btn flat round dense icon="close" color="grey-7" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>
      <q-separator />

      <!-- Étape 1 : choix du labo + fichier -->
      <q-card-section v-if="step === 'pick'" class="q-gutter-md">
        <q-select
          v-model="lab"
          :options="labOptions"
          :label="t('params.icp.lab')"
          outlined
          dense
          emit-value
          map-options
        />
        <div v-if="lab !== 'ati'" class="text-caption text-warning">{{ t('params.icp.labUnsupported') }}</div>
        <q-file
          v-model="file"
          outlined
          dense
          :label="t('params.icp.pdf')"
          accept="application/pdf"
          :disable="lab !== 'ati'"
        >
          <template #prepend><q-icon name="attach_file" /></template>
        </q-file>
        <q-input v-model="sampleDate" type="date" :label="t('params.icp.sampleDate')" outlined dense />
      </q-card-section>

      <!-- Étape 2 : relecture / correction avant import -->
      <q-card-section v-else-if="step === 'review'" class="q-gutter-sm" style="max-height: 60vh; overflow-y: auto">
        <div class="text-caption text-grey-7 q-mb-sm">
          {{ t('params.icp.selected', { n: selectedCount, total: rows.length }) }}
        </div>
        <q-list separator>
          <q-item v-for="(row, index) in rows" :key="index">
            <q-item-section side top>
              <q-checkbox v-model="row.include" />
            </q-item-section>
            <q-item-section>
              <div class="row q-col-gutter-sm items-center">
                <div class="col-3">
                  <q-input v-model="row.name" dense outlined :label="t('params.icp.param')" :disable="!row.include" />
                </div>
                <div class="col-4">
                  <q-input
                    v-model.number="row.value"
                    type="number"
                    step="0.01"
                    dense
                    outlined
                    :label="t('params.icp.value')"
                    :disable="!row.include"
                  />
                </div>
                <div class="col-3">
                  <q-input v-model="row.unit" dense outlined :label="t('params.icp.unit')" :disable="!row.include" />
                </div>
                <div class="col-2 text-caption">
                  <div class="text-grey-6">{{ row.label }}</div>
                  <div v-if="row.status" :class="statusColorClass(row.status)" class="text-weight-bold">
                    {{ row.status }}
                  </div>
                </div>
              </div>
            </q-item-section>
          </q-item>
        </q-list>
      </q-card-section>

      <q-separator />
      <q-card-actions align="right" class="q-px-md q-py-sm">
        <q-btn flat :label="t('common.cancel')" color="grey-8" @click="close" />
        <q-btn
          v-if="step === 'pick'"
          unelevated
          :label="t('params.icp.analyze')"
          color="primary"
          :loading="analyzing"
          :disable="lab !== 'ati' || !file || !sampleDate"
          @click="analyze"
        />
        <template v-else-if="step === 'review'">
          <q-btn flat :label="t('common.back')" color="grey-8" @click="step = 'pick'" />
          <q-btn
            unelevated
            :label="t('params.icp.confirm')"
            color="primary"
            :loading="importing"
            :disable="selectedCount === 0"
            @click="confirmImport"
          />
        </template>
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useWaterParameterStore } from 'src/stores/waterParameterStore';
import type { IcpLab } from 'src/types/waterParameter';

const props = defineProps<{
  modelValue: boolean;
  aquaId: number;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  imported: [];
}>();

const { t } = useI18n();
const $q = useQuasar();
const store = useWaterParameterStore();

const labOptions = computed<{ label: string; value: IcpLab }[]>(() => [
  { label: 'ATI', value: 'ati' },
  { label: t('params.icp.labSoon', { name: 'Fauna Marin' }), value: 'fauna_marin' },
  { label: t('params.icp.labSoon', { name: t('params.icp.other') }), value: 'other' },
]);

function todayDateStr(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const step = ref<'pick' | 'review'>('pick');
const lab = ref<IcpLab>('ati');
const file = ref<File | null>(null);
const sampleDate = ref(todayDateStr());
const analyzing = ref(false);
const importing = ref(false);

interface ReviewRow {
  include: boolean;
  name: string;
  label: string;
  value: number;
  unit: string;
  status: string | null;
  target: number | null;
}

// Couleur indicative reprenant le jugement du labo (TOP/Proche de la
// nature = bon ; EXCESSIF/INSUFFISANT/TROP ÉLEVÉ/CRITIQUE = à surveiller),
// purement informative — la donnée importée reste la valeur brute.
function statusColorClass(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized.includes('TOP')) return 'text-positive';
  // i18n-ignore : statuts écrits par le labo dans son rapport
  if (normalized.includes('INSUFFISANT') || normalized.includes('EXCESSIF') || normalized.includes('ÉLEVÉ')) {
    return 'text-warning';
  }
  return 'text-grey-7';
}

const rows = ref<ReviewRow[]>([]);
const selectedCount = computed(() => rows.value.filter((r) => r.include).length);

function onDialogUpdate(value: boolean) {
  emit('update:modelValue', value);
}

function close() {
  emit('update:modelValue', false);
}

function reset() {
  step.value = 'pick';
  lab.value = 'ati';
  file.value = null;
  sampleDate.value = todayDateStr();
  rows.value = [];
}

async function analyze() {
  if (!file.value) return;
  analyzing.value = true;
  try {
    const parsed = await store.parseIcpReport(lab.value, file.value);
    rows.value = parsed.map((r) => ({
      include: true,
      name: r.name,
      label: r.label,
      value: r.value,
      unit: r.unit ?? '',
      status: r.status ?? null,
      target: r.target ?? null,
    }));
    if (rows.value.length === 0) {
      $q.notify({ type: 'warning', message: t('params.icp.noValue') });
      return;
    }
    step.value = 'review';
  } catch (err) {
    const message =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      t('params.icp.analyzeFailed');
    $q.notify({ type: 'negative', message });
  } finally {
    analyzing.value = false;
  }
}

async function confirmImport() {
  importing.value = true;
  const timestamp = `${sampleDate.value}T12:00:00`;
  const labLabel = lab.value === 'ati' ? 'ATI' : lab.value;
  let successCount = 0;
  let errorCount = 0;
  let targetsFilled = 0;

  try {
    await store.fetchTargetDefaults();
    const batch = await store.createIcpBatch({
      aquarium_id: props.aquaId,
      lab: lab.value,
      sample_date: timestamp,
    });

    if (file.value) {
      try {
        await store.uploadIcpBatchPdf(batch.id, file.value);
      } catch {
        $q.notify({ type: 'warning', message: t('params.icp.pdfNotKept') });
      }
    }

    for (const row of rows.value) {
      if (!row.include || !row.name.trim()) continue;
      try {
        let param = store.parameters.find((p) => p.name.toLowerCase() === row.name.trim().toLowerCase());
        if (!param) {
          param = await store.create({
            aquarium_id: props.aquaId,
            name: row.name.trim(),
            unit: row.unit || null,
          });
        } else if (param.target_min == null && param.target_max == null) {
          // Paramètre existant sans cible : cible par défaut de l'API si l'unité correspond
          const preset = store.defaultTargetFor(param.name, param.unit);
          if (preset) {
            param = await store.update(param.id, { target_min: preset.target_min, target_max: preset.target_max });
            targetsFilled += 1;
          }
        }
        await store.addReading(param.id, {
          value: row.value,
          note: t('params.icp.note', { lab: labLabel }),
          timestamp,
          icp_batch_id: batch.id,
        }, false);
        successCount += 1;
      } catch {
        errorCount += 1;
      }
    }
  } catch {
    $q.notify({ type: 'negative', message: t('params.icp.batchFailed') });
    importing.value = false;
    return;
  }

  importing.value = false;

  if (successCount > 0) {
    const targetsMsg = targetsFilled > 0 ? t('params.icp.targetsAdded', { n: targetsFilled }) : '';
    $q.notify({ type: 'positive', message: t('params.icp.imported', { n: successCount, extra: targetsMsg }) });
    emit('imported');
  }
  if (errorCount > 0) {
    $q.notify({ type: 'negative', message: t('params.icp.importErrors', { n: errorCount }) });
  }
  if (errorCount === 0) {
    close();
  }
}
</script>
