<template>
  <FormDialog
    :model-value="modelValue"
    icon="extension"
    :title="t('controllers.modules.title')"
    :subtitle="controller ? t('controllers.modules.subtitle', { name: controller.name }) : undefined"
    width="580px"
    :cancel-label="t('common.close')"
    hide-submit
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
  >
    <q-card flat bordered class="q-pa-md">
      <div class="text-subtitle2 text-weight-bold row items-center"><q-icon name="schedule" class="q-mr-xs" />{{ t('controllers.modules.rtcTitle') }}</div>
      <div class="text-caption text-grey-7 q-mb-sm">{{ t('controllers.modules.rtcHelp') }}</div>
      <div class="row items-center gap-sm">
        <AppSelect v-model="rtcModel" :options="rtcOptions" :label="t('controllers.modules.clock')" style="min-width: 240px" />
        <q-btn
          unelevated
          color="primary"
          icon="check"
          :label="t('common.save')"
          :disable="rtcModel === (currentController?.rtc_model ?? null)"
          :loading="savingRtc"
          @click="saveRtc"
        />
      </div>
    </q-card>

    <q-card flat bordered class="q-pa-md">
      <div class="text-subtitle2 text-weight-bold row items-center"><q-icon name="cable" class="q-mr-xs" />{{ t('controllers.modules.busTitle') }}</div>
      <div class="text-caption text-grey-7 q-mb-sm">{{ t('controllers.modules.busHelp') }}</div>
      <div class="row items-center gap-sm">
        <AppSelect v-model="i2cFrequency" :options="frequencyOptions" :label="t('controllers.modules.frequency')" style="min-width: 240px" />
        <q-btn
          unelevated
          color="primary"
          icon="check"
          :label="t('common.save')"
          :disable="i2cFrequency === (currentController?.i2c_frequency_khz ?? 50)"
          :loading="savingFrequency"
          @click="saveFrequency"
        />
      </div>
    </q-card>

    <div>
      <div class="text-subtitle2 text-weight-bold q-mb-sm">{{ t('controllers.modules.ioTitle') }}</div>
      <q-list v-if="modules.length > 0" bordered separator class="rounded-borders">
        <q-item v-for="mod in modules" :key="mod.id">
          <q-item-section avatar><q-avatar size="36px" color="blue-1" text-color="primary" class="text-weight-bold">{{ mod.number }}</q-avatar></q-item-section>
          <q-item-section>
            <q-item-label class="text-weight-medium">{{ t('controllers.modules.moduleName', { n: mod.number, type: mod.type }) }}</q-item-label>
            <q-item-label caption>{{ t('controllers.modules.address', { address: mod.address }) }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <div class="row no-wrap">
              <q-btn flat round dense icon="edit" color="grey-7" size="sm" :aria-label="t('actions.edit')" @click="startEdit(mod)">
                <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
              </q-btn>
              <q-btn flat round dense icon="delete" color="negative" size="sm" :aria-label="t('actions.delete')" @click="removeModule(mod)">
                <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
              </q-btn>
            </div>
          </q-item-section>
        </q-item>
      </q-list>
      <div v-else class="text-body2 text-grey-6">{{ t('controllers.modules.none') }}</div>
    </div>

    <!-- Scan du bus I2C : adresses vues par le firmware au démarrage -->
    <q-card flat bordered class="q-pa-md">
      <div class="row items-center no-wrap gap-sm">
        <div class="col">
          <div class="text-subtitle2 text-weight-bold">{{ t('controllers.modules.scanTitle') }}</div>
          <div class="text-caption text-grey-7">{{ t('controllers.modules.scanHelp') }}</div>
        </div>
        <div class="column gap-xs">
          <q-btn outline color="primary" icon="radar" no-caps :label="t('controllers.modules.scan')" :loading="scanning && !restarting" :disable="restarting" @click="scan" />
          <q-btn v-if="can.manage" flat dense color="primary" icon="restart_alt" no-caps size="sm" :label="t('controllers.restart.andScan')" :loading="restarting" :disable="scanning && !restarting" @click="restartAndScan" />
        </div>
      </div>
      <template v-if="scanResult">
        <div v-if="!scanResult.enabled" class="text-body2 text-warning q-mt-sm">{{ t('controllers.modules.scanNoBus') }}</div>
        <template v-else>
          <div v-if="!scanResult.devices.length" class="text-body2 text-negative q-mt-sm">{{ t('controllers.modules.scanEmpty') }}</div>
          <q-list v-else dense class="q-mt-sm">
            <q-item v-for="dev in scanResult.devices" :key="dev.address">
              <q-item-section avatar><q-icon :name="kindIcon(dev.kind)" :color="kindColor(dev.kind)" /></q-item-section>
              <q-item-section>
                <q-item-label><code>{{ dev.address }}</code> · {{ kindLabel(dev) }}</q-item-label>
              </q-item-section>
              <q-item-section v-if="dev.kind === 'io_undeclared' || dev.kind === 'pwm_undeclared'" side>
                <q-btn flat dense no-caps size="sm" color="primary" icon="add" :label="t('controllers.modules.declare')" @click="declare(dev.address, dev.kind === 'pwm_undeclared' ? 'PCA9685' : 'PCF8574')" />
              </q-item-section>
            </q-item>
          </q-list>
          <div v-for="miss in scanResult.missing" :key="miss.address" class="text-body2 text-negative q-mt-xs">
            <q-icon name="error_outline" class="q-mr-xs" />
            {{ miss.rtc ? t('controllers.modules.missingRtc', { model: miss.rtc, address: miss.address }) : t('controllers.modules.missingModule', { n: miss.module_number, address: miss.address }) }}
          </div>
        </template>
      </template>
    </q-card>

    <q-card flat bordered class="q-pa-md">
      <div class="text-subtitle2 text-weight-bold q-mb-sm">{{ editingId ? t('controllers.modules.editTitle') : t('controllers.modules.addTitle') }}</div>
      <div class="row q-col-gutter-sm items-start">
        <div class="col-4 col-sm-2">
          <q-input v-model.number="form.number" type="number" min="1" max="99" :label="t('controllers.modules.number')" outlined dense hide-bottom-space />
        </div>
        <div class="col-8 col-sm-3">
          <AppSelect v-model="form.type" :options="['PCF8574', 'PCF8575', 'PCA9685']" :label="t('controllers.modules.type')" :emit-value="false" :map-options="false" @update:model-value="onTypeChange" />
        </div>
        <div class="col-12 col-sm-3">
          <q-input
            v-model="form.address"
            :label="t('controllers.modules.addressLabel')"
            placeholder="0x20"
            outlined
            dense
            :error="!!addressError"
            :error-message="addressError ?? undefined"
            hide-bottom-space
          />
        </div>
        <div class="col-12 col-sm-4 row gap-xs justify-end">
          <q-btn v-if="editingId" flat :label="t('common.cancel')" color="grey-8" @click="resetForm()" />
          <q-btn
            unelevated
            :icon="editingId ? 'check' : 'add'"
            :label="editingId ? t('common.save') : t('actions.add')"
            color="primary"
            :loading="saving"
            @click="save"
          />
        </div>
      </div>
    </q-card>
    <div class="text-caption text-grey-7">{{ t('controllers.modules.reflash') }}</div>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import AppSelect from 'src/components/AppSelect.vue';
import { apiErrorMessage } from 'src/utils/apiError';
import { usePermissions } from 'src/composables/usePermissions';
import { useControllerStore, type I2cDevice, type I2cScan, type ModuleItem } from 'src/stores/controllerStore';
import type { Controller, RtcModel } from 'src/types/controller';

interface ModuleForm {
  number: number | null;
  type: string;
  address: string;
}

const props = defineProps<{ modelValue: boolean; controller: Controller | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const $q = useQuasar();
const { t } = useI18n();
const store = useControllerStore();
const saving = ref(false);
const editingId = ref<number | null>(null);
const form = ref<ModuleForm>({ number: null, type: 'PCF8574', address: '0x20' });

const modules = computed<ModuleItem[]>(() => (props.controller ? store.modulesMap[props.controller.id] ?? [] : []));

const rtcOptions = computed<{ label: string; value: RtcModel | null }[]>(() => [
  { label: t('controllers.modules.rtcNone'), value: null },
  { label: t('controllers.modules.rtcRecommended', { model: 'DS3231' }), value: 'DS3231' },
  { label: 'DS1307', value: 'DS1307' },
  { label: 'PCF8563', value: 'PCF8563' },
  { label: 'PCF85063', value: 'PCF85063' },
]);
const rtcModel = ref<RtcModel | null>(null);
// Version à jour après enregistrement (la prop pointe sur l'objet d'origine)
const currentController = computed(() => store.controllers.find((c) => c.id === props.controller?.id) ?? props.controller);
const savingRtc = ref(false);

async function saveRtc() {
  if (!props.controller) return;
  savingRtc.value = true;
  try {
    await store.update(props.controller.id, { rtc_model: rtcModel.value });
    markDirty();
    $q.notify({ type: 'positive', message: t('controllers.modules.rtcSaved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.modules.rtcFailed')) });
  } finally {
    savingRtc.value = false;
  }
}

// Fréquence du bus I2C : à baisser pour un câble long entre l'ESP32 et les modules
const i2cFrequency = ref(50);
const savingFrequency = ref(false);
const frequencyOptions = computed(() =>
  [10, 25, 50, 100, 400].map((khz) => ({
    value: khz,
    label: t(`controllers.modules.frequencies.f${khz}`),
  })),
);

async function saveFrequency() {
  if (!props.controller) return;
  savingFrequency.value = true;
  try {
    await store.update(props.controller.id, { i2c_frequency_khz: i2cFrequency.value });
    markDirty();
    $q.notify({ type: 'positive', message: t('controllers.modules.frequencySaved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.modules.rtcFailed')) });
  } finally {
    savingFrequency.value = false;
  }
}

const addressError = computed(() =>
  /^0x[0-9a-fA-F]{2}$/.test(form.value.address.trim()) ? null : t('controllers.modules.addressFormat'),
);

// Plage d'adresses du type : PCF8574 0x20-0x27, PCA9685 0x40-0x4F
function firstFreeAddress(type: string) {
  const used = new Set(modules.value.map((m) => m.address.toLowerCase()));
  const [start, count] = type === 'PCA9685' ? [0x40, 16] : [0x20, 8];
  return Array.from({ length: count }, (_, i) => `0x${(start + i).toString(16)}`).find((a) => !used.has(a)) ?? `0x${start.toString(16)}`;
}

function onTypeChange(type: string) {
  if (!editingId.value) form.value.address = firstFreeAddress(type);
}

function firstFreeNumber() {
  const used = new Set(modules.value.map((m) => m.number));
  let n = 1;
  while (used.has(n)) n++;
  return n;
}

function resetForm(address?: string) {
  editingId.value = null;
  form.value = { number: firstFreeNumber(), type: 'PCF8574', address: address ?? firstFreeAddress('PCF8574') };
}

function startEdit(mod: ModuleItem) {
  editingId.value = mod.id;
  form.value = { number: mod.number, type: mod.type, address: mod.address };
}

function markDirty() {
  if (props.controller) store.markControllerAsDirty(props.controller.id);
}


async function save() {
  if (!props.controller || addressError.value) return;
  const controllerId = props.controller.id;
  const address = form.value.address.trim().toLowerCase();
  saving.value = true;
  try {
    const payload = { type: form.value.type, address, ...(form.value.number ? { number: form.value.number } : {}) };
    // Modification sur place : les broches et ce qui y est branché sont gardés
    if (editingId.value) await store.updateModule(controllerId, editingId.value, payload);
    else await store.addModule(controllerId, payload);
    markDirty();
    $q.notify({ type: 'positive', message: editingId.value ? t('controllers.modules.edited') : t('controllers.modules.added') });
    resetForm();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.modules.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

function removeModule(mod: ModuleItem) {
  if (!props.controller) return;
  const controllerId = props.controller.id;
  $q.dialog({
    title: t('confirm.deleteTitle'),
    message: t('controllers.modules.deleteMessage', { n: mod.number, type: mod.type, address: mod.address }),
    ok: { label: t('actions.delete'), color: 'negative', unelevated: true },
    cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
    persistent: true,
  }).onOk(() => {
    void (async () => {
      try {
        await store.deleteModule(controllerId, mod.id);
        markDirty();
        if (editingId.value === mod.id) resetForm();
      } catch (err) {
        $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.modules.deleteFailed')) });
      }
    })();
  });
}

// --- Scan du bus I2C
const scanning = ref(false);
const scanResult = ref<I2cScan | null>(null);

// Le contrôleur ne scanne qu'au démarrage : redémarrage puis nouveau scan
const can = usePermissions();
const restarting = ref(false);

async function restartAndScan() {
  if (!props.controller) return;
  const controllerId = props.controller.id;
  restarting.value = true;
  scanning.value = true;
  try {
    scanResult.value = await store.restartAndWait(controllerId, () => store.scanI2c(controllerId));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.restart.failed')) });
  } finally {
    restarting.value = false;
    scanning.value = false;
  }
}

async function scan() {
  if (!props.controller) return;
  scanning.value = true;
  try {
    scanResult.value = await store.scanI2c(props.controller.id);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.modules.scanFailed')) });
  } finally {
    scanning.value = false;
  }
}

const KIND_ICON: Record<I2cDevice['kind'], [string, string]> = {
  module: ['check_circle', 'positive'],
  rtc: ['schedule', 'positive'],
  rtc_undeclared: ['schedule', 'warning'],
  eeprom: ['memory', 'grey-6'],
  io_undeclared: ['help_outline', 'warning'],
  pwm_undeclared: ['help_outline', 'warning'],
  pca_allcall: ['hub', 'grey-6'],
  unknown: ['help_outline', 'grey-6'],
};
const kindIcon = (kind: I2cDevice['kind']) => KIND_ICON[kind][0];
const kindColor = (kind: I2cDevice['kind']) => KIND_ICON[kind][1];
function kindLabel(dev: I2cDevice) {
  if (dev.kind === 'module') return t('controllers.modules.moduleName', { n: dev.module_number, type: dev.module_type });
  return t(`controllers.modules.kinds.${dev.kind}`);
}

function declare(address: string, type = 'PCF8574') {
  resetForm(address);
  form.value.type = type;
}

watch(
  () => props.modelValue,
  (open) => {
    if (open && props.controller) {
      rtcModel.value = currentController.value?.rtc_model ?? null;
      i2cFrequency.value = currentController.value?.i2c_frequency_khz ?? 50;
      scanResult.value = null;
      void store.fetchModules(props.controller.id).then(() => resetForm());
    }
  },
);
</script>
