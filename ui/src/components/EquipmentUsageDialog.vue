<!--
  Usure et consommation des équipements d'un bac : heures de fonctionnement,
  électricité sur 30 jours (puissance × durée d'allumage) et entretien
  périodique (ex : ampoule UV toutes les 9000 h, tâche créée à l'échéance).
-->
<template>
  <FormDialog
    :model-value="modelValue"
    icon="bolt"
    :title="t('equipments.usageDialog.title')"
    :subtitle="t('equipments.usageDialog.subtitle')"
    width="720px"
    :cancel-label="t('common.close')"
    hide-submit
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="load"
  >
    <div v-if="loading" class="text-center q-py-lg"><q-spinner color="primary" size="2em" /></div>
    <template v-else>
      <div class="row q-col-gutter-sm">
        <div class="col-6 col-sm-4">
          <q-card flat bordered class="q-pa-sm text-center">
            <div class="text-h6 text-weight-bold">{{ totalKwh.toFixed(1) }} kWh</div>
            <div class="text-caption text-grey-7">{{ t('equipments.usageDialog.last30') }}</div>
          </q-card>
        </div>
        <div class="col-6 col-sm-4">
          <q-card flat bordered class="q-pa-sm text-center">
            <div class="text-h6 text-weight-bold">{{ formatPrice(totalCost) }}</div>
            <div class="text-caption text-grey-7">{{ t('equipments.usageDialog.perYear', { price: formatPrice(totalCost * 12.17) }) }}</div>
          </q-card>
        </div>
        <div class="col-12 col-sm-4">
          <q-input
            v-model.number="price"
            type="number"
            step="0.01"
            min="0"
            :label="t('equipments.usageDialog.kwhPrice')"
            suffix="€"
            outlined
            dense
            :readonly="!can.manage"
            @change="savePrice"
          />
        </div>
      </div>
      <div v-if="missingPower" class="text-caption text-orange-9">
        {{ t('equipments.usageDialog.missingPower', missingPower) }}
      </div>

      <q-list bordered separator class="rounded-borders">
        <q-expansion-item v-for="row in rows" :key="row.equipment_id" group="usage" expand-separator>
          <template #header>
            <q-item-section avatar>
              <q-icon name="circle" size="12px" :color="row.running ? 'positive' : 'grey-5'" />
            </q-item-section>
            <q-item-section>
              <q-item-label class="text-weight-bold">{{ row.name }}</q-item-label>
              <q-item-label caption>
                {{ t('equipments.usageDialog.total', { hours: formatHours(row.hours_total) }) }}
                <template v-if="row.power_watts">
                  · {{ t('equipments.usageDialog.perMonth', { watts: row.power_watts, kwh: row.kwh_30d, cost: formatPrice(row.cost_30d) }) }}
                </template>
              </q-item-label>
              <div v-if="row.service_interval_hours" class="q-mt-xs">
                <q-linear-progress
                  :value="Math.min(row.service_progress ?? 0, 1)"
                  :color="progressColor(row.service_progress)"
                  rounded
                  size="6px"
                />
                <div class="text-caption" :class="(row.service_progress ?? 0) >= 1 ? 'text-negative text-weight-bold' : 'text-grey-7'">
                  {{
                    t('equipments.usageDialog.serviceProgress', {
                      label: row.service_label || t('equipments.usageDialog.service'),
                      hours: formatHours(row.hours_since_service),
                      interval: row.service_interval_hours,
                    })
                  }}
                </div>
              </div>
            </q-item-section>
          </template>

          <q-card-section class="column gap-sm">
            <div class="row q-col-gutter-sm">
              <div class="col-12 col-sm-3">
                <q-input v-model.number="forms[row.equipment_id]!.power_watts" type="number" min="0" :label="t('equipments.usageDialog.power')" suffix="W" outlined dense :readonly="!can.edit" />
              </div>
              <div class="col-12 col-sm-4">
                <q-input v-model="forms[row.equipment_id]!.service_label" :label="t('equipments.usageDialog.serviceLabel')" outlined dense maxlength="80" :readonly="!can.edit" />
              </div>
              <div class="col-12 col-sm-5">
                <q-input
                  v-model.number="forms[row.equipment_id]!.service_interval_hours"
                  type="number"
                  min="1"
                  :label="t('equipments.usageDialog.every')"
                  :suffix="t('equipments.usageDialog.everySuffix')"
                  outlined
                  dense
                  clearable
                  :readonly="!can.edit"
                />
              </div>
            </div>
            <div class="text-caption text-grey-7">
              {{ t('equipments.usageDialog.running30', { hours: formatHours(row.hours_30d) }) }}
              <template v-if="row.serviced_at">{{ t('equipments.usageDialog.lastService', { date: formatDate(row.serviced_at) }) }}</template>
              {{ t('equipments.usageDialog.taskInfo') }}
            </div>
            <div v-if="can.edit" class="row justify-end gap-sm">
              <q-btn v-if="row.service_interval_hours" flat color="positive" icon="build_circle" :label="t('equipments.usageDialog.serviced')" @click="serviced(row)" />
              <q-btn unelevated color="primary" icon="check" :label="t('common.save')" @click="save(row)" />
            </div>
          </q-card-section>
        </q-expansion-item>
      </q-list>
      <div v-if="!rows.length" class="text-grey-6 text-center q-pa-md">{{ t('equipments.usageDialog.none') }}</div>
    </template>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { intlLocale } from 'src/i18n/instance';
import FormDialog from 'src/components/FormDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate, formatPrice } from 'src/utils/format';

interface UsageRow {
  equipment_id: number;
  name: string;
  running: boolean;
  power_watts: number | null;
  hours_total: number;
  hours_30d: number;
  kwh_30d: number | null;
  cost_30d: number | null;
  service_label: string | null;
  service_interval_hours: number | null;
  hours_since_service: number;
  service_progress: number | null;
  serviced_at: string | null;
}

interface UsageForm {
  power_watts: number | null;
  service_interval_hours: number | null;
  service_label: string;
}

const props = defineProps<{ modelValue: boolean; aquariumId: number }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const loading = ref(false);
const rows = ref<UsageRow[]>([]);
const forms = ref<Record<number, UsageForm>>({});
const price = ref(0.25);

const totalKwh = computed(() => rows.value.reduce((sum, r) => sum + (r.kwh_30d ?? 0), 0));
const totalCost = computed(() => rows.value.reduce((sum, r) => sum + (r.cost_30d ?? 0), 0));
const missingPower = computed(() => rows.value.filter((r) => !r.power_watts).length);

function formatHours(hours: number): string {
  return hours >= 100 ? `${Math.round(hours).toLocaleString(intlLocale())} h` : `${hours.toLocaleString(intlLocale())} h`;
}

function progressColor(progress: number | null): string {
  if ((progress ?? 0) >= 1) return 'negative';
  if ((progress ?? 0) >= 0.9) return 'orange-8';
  return 'primary';
}

function setRows(data: UsageRow[]) {
  rows.value = data;
  forms.value = Object.fromEntries(
    data.map((r) => [
      r.equipment_id,
      { power_watts: r.power_watts, service_interval_hours: r.service_interval_hours, service_label: r.service_label ?? '' },
    ]),
  );
}

async function load() {
  loading.value = true;
  try {
    const [usage, settings] = await Promise.all([
      axios.get<UsageRow[]>('/equipment-usage/', { params: { aquarium_id: props.aquariumId } }),
      axios.get<{ price_per_kwh: number }>('/equipment-usage/settings'),
    ]);
    setRows(usage.data);
    price.value = settings.data.price_per_kwh;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.usageDialog.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

function replace(row: UsageRow) {
  setRows(rows.value.map((r) => (r.equipment_id === row.equipment_id ? row : r)));
}

async function save(row: UsageRow) {
  const form = forms.value[row.equipment_id]!;
  try {
    const { data } = await axios.put<UsageRow>(`/equipment-usage/${row.equipment_id}`, {
      power_watts: typeof form.power_watts === 'number' ? form.power_watts : null,
      service_interval_hours: typeof form.service_interval_hours === 'number' ? form.service_interval_hours : null,
      service_label: form.service_label.trim() || null,
    });
    replace(data);
    $q.notify({ type: 'positive', message: t('equipments.usageDialog.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.usageDialog.saveFailed')) });
  }
}

async function serviced(row: UsageRow) {
  try {
    replace((await axios.post<UsageRow>(`/equipment-usage/${row.equipment_id}/serviced`)).data);
    $q.notify({ type: 'positive', message: t('equipments.usageDialog.servicedDone') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.usageDialog.failed')) });
  }
}

async function savePrice() {
  if (!can.manage) return;
  try {
    await axios.put('/equipment-usage/settings', { price_per_kwh: Number(price.value) || 0 });
    await load();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.usageDialog.priceFailed')) });
  }
}
</script>
