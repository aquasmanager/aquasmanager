<template>
  <div>
    <PageHeader section :title="t('sensors.title')" :subtitle="t('sensors.subtitle')">
      <template #actions>
        <AppInput v-if="sensors.length > 0" v-model="search" icon="search" :placeholder="t('equipments.search')" clearable style="width: 220px" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('sensors.add')" :disable="!hasController" @click="openDialogAdd" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="!hasController"
      icon="memory"
      :title="t('equipments.noControllerTitle')"
      :message="t('sensors.noControllerMessage')"
    >
      <q-btn v-if="can.manage" unelevated color="primary" icon="memory" :label="t('equipments.addController')" to="/controllers" />
    </EmptyState>

    <EmptyState
      v-else-if="sensors.length === 0"
      icon="sensors"
      :title="t('sensors.emptyTitle')"
      :message="t('sensors.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('sensors.add')" @click="openDialogAdd" />
    </EmptyState>

    <q-card v-else flat bordered>
      <AppTable
        :rows="filteredRows"
        :columns="columns"
        row-key="id"
        :pagination="{ rowsPerPage: 25 }"
        :rows-per-page-options="[10, 25, 50, 0]"
      >
        <template #body-cell-name="props">
          <q-td :props="props">
            <div class="row items-center no-wrap">
              <q-avatar
                size="36px"
                :color="isTemperatureSensor(props.row) ? 'red-1' : 'blue-1'"
                :text-color="isTemperatureSensor(props.row) ? 'red-7' : 'primary'"
                :icon="isTemperatureSensor(props.row) ? 'thermostat' : 'water'"
                class="q-mr-sm"
              />
              <div>
                <div class="text-weight-bold">{{ props.row.name }}</div>
                <div class="text-caption text-grey-7">
                  {{ isTemperatureSensor(props.row) ? t('sensors.temperature') : t('sensors.level') }} · {{ controllerName(props.row.controller_id) }}
                  <template v-if="pinLabel(props.row.pin_number, props.row.module_id, props.row.module_number)"> · {{ pinLabel(props.row.pin_number, props.row.module_id, props.row.module_number) }}</template>
                </div>
              </div>
            </div>
          </q-td>
        </template>

        <template #body-cell-live_value="props">
          <q-td :props="props">
            <q-chip dense :color="liveState(props.row).color" text-color="white" :icon="liveState(props.row).icon">
              {{ liveState(props.row).label }}
            </q-chip>
          </q-td>
        </template>

        <template #body-cell-actions="props">
          <q-td :props="props">
            <q-btn flat round dense icon="show_chart" color="grey-7" @click="openHistory(props.row)">
              <q-tooltip>{{ t('sensors.history') }}</q-tooltip>
            </q-btn>
            <q-btn flat round dense icon="info" color="grey-7" @click="openDialogInfos(props.row)">
              <q-tooltip>{{ t('equipments.information') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.edit" flat round dense icon="edit" color="grey-7" @click="openDialogEdit(props.row)">
              <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" @click="remove(props.row)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </q-td>
        </template>
      </AppTable>
    </q-card>

    <!-- Création / modification -->
    <FormDialog
      v-model="dialog"
      icon="sensors"
      :title="edited ? t('sensors.form.editTitle') : t('sensors.add')"
      :subtitle="t('sensors.form.subtitle')"
      width="640px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-6">
          <q-input v-model="name" :label="t('sensors.form.name')" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect v-model="unit" :options="unitOptions" :label="t('sensors.form.measure')" :error="!!errors.unit" :error-message="errors.unit" />
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect v-model="controller_id" :options="controllerOptions" :label="t('equipments.form.controller')" :error="!!errors.controller_id" :error-message="errors.controller_id" />
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect v-model="pin_id" :options="pinOptions" :label="t('equipments.form.pin')" :disable="!controller_id" :error="!!errors.pin_id" :error-message="errors.pin_id" />
          <div v-if="inputOnlyPin" class="text-caption text-orange-9 q-mt-xs">
            <q-icon name="warning" size="14px" class="q-mr-xs" />{{ t('sensors.form.inputOnlyPin') }}
          </div>
        </div>

        <template v-if="isTemperature">
          <div class="col-12 col-sm-8">
            <q-input
              v-model="address"
              :label="t('sensors.form.address')"
              placeholder="0x1c0000031edd2a28"
              outlined
              dense
              :error="!!errors.address"
              :error-message="errors.address"
            >
              <template #append>
                <q-btn flat dense icon="search" :label="t('sensors.form.scan')" color="primary" :loading="scanning" :disable="!controller_id" @click="scanOneWire">
                  <q-tooltip>{{ t('sensors.form.scanHelp') }}</q-tooltip>
                </q-btn>
              </template>
            </q-input>
          </div>
          <div class="col-12 col-sm-4">
            <q-input
              v-model.number="interval"
              type="number"
              :label="t('sensors.form.interval')"
              suffix="s"
              placeholder="30"
              outlined
              dense
              clearable
              :error="!!errors.interval"
              :error-message="errors.interval"
            />
          </div>
          <div class="col-12">
            <q-list v-if="scannedDevices.length" bordered separator class="rounded-borders">
              <q-item
                v-for="device in scannedDevices"
                :key="device.address"
                clickable
                :disable="isDeviceTaken(device)"
                :active="device.address === normalizedAddress"
                active-class="bg-blue-1"
                @click="selectDevice(device)"
              >
                <q-item-section avatar><q-icon name="thermostat" color="red-7" /></q-item-section>
                <q-item-section>
                  <q-item-label class="font-mono">{{ device.address }}</q-item-label>
                  <q-item-label caption>
                    {{ device.model }}<span v-if="device.pin_number !== null"> · GPIO {{ device.pin_number }}</span>
                  </q-item-label>
                  <q-item-label v-if="device.sensor_name" caption class="text-grey-8">
                    <q-icon name="link" size="14px" />
                    {{ t('sensors.form.usedBy', { name: device.sensor_name, aquarium: device.aquarium_name ?? '—' }) }}
                    <span v-if="probeValue(device)"> · {{ probeValue(device) }}</span>
                  </q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-badge v-if="isDeviceTaken(device)" color="grey-6" :label="t('sensors.form.taken')" />
                  <q-badge v-else-if="isCurrentDevice(device)" color="primary" :label="t('sensors.form.current')" />
                  <q-badge v-else color="positive" :label="t('sensors.form.free')" />
                </q-item-section>
              </q-item>
            </q-list>
            <div v-else-if="scanDone" class="text-caption text-orange-9">
              {{ noProbeMessage }}
              <q-btn v-if="can.manage && scanResult?.config_received" flat dense no-caps size="sm" color="primary" icon="restart_alt" :label="t('controllers.restart.andSearch')" :loading="restarting" @click="restartAndSearch" />
            </div>
            <div v-else class="text-caption text-grey-7">{{ t('sensors.form.addressHint') }}</div>
          </div>
        </template>

        <div v-else class="col-12">
          <q-card flat bordered class="q-px-md q-py-sm">
            <q-toggle v-model="is_inverted" color="primary" :label="t('sensors.form.invert')" />
            <div class="text-caption text-grey-7">{{ t('sensors.form.invertHint') }}</div>
          </q-card>
        </div>
      </div>
    </FormDialog>

    <!-- Historique -->
    <SensorHistoryDialog v-model="historyOpen" :sensor="historySensor" />

    <!-- Informations -->
    <BaseInfoDialog v-model="dialogInfos" :title="t('sensors.form.infoTitle')" :subtitle="t('equipments.form.infoSubtitle')" :data="infos" />
  </div>
</template>

<script setup lang="ts">
import { pinLabel, pinOption } from 'src/utils/pins';
import AppTable from 'src/components/AppTable.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref, watch } from 'vue';
import { z } from 'zod';
import { useForm, useField } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import { type QTableColumn, useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useSensorStore } from '../stores/sensorStore';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { useControllerStore } from 'src/stores/controllerStore';
import { useControllerPinStore } from 'src/stores/controllerPinStore';
import { useWebSocketStore } from 'src/stores/websocket';
import type { Sensor, SensorCreation } from 'src/types/sensor';
import type { OneWireDevice, OneWireScan } from 'src/types/controller_pin';
import BaseInfoDialog from 'src/components/BaseInfoDialog.vue';
import SensorHistoryDialog from 'src/components/SensorHistoryDialog.vue';
import FormDialog from 'src/components/FormDialog.vue';
import AppInput from 'src/components/AppInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { apiErrorMessage } from 'src/utils/apiError';

const props = defineProps({ aquaId: { type: Number, required: true } });
const { t } = useI18n();

// L'API accepte « temperature » / « niveau » et stocke « °C » / « level »
const unitOptions = computed(() => [
  { label: t('sensors.units.temperature'), value: 'temperature' },
  { label: t('sensors.units.level'), value: 'niveau' },
]);

const columns = computed<QTableColumn<Sensor>[]>(() => [
  { name: 'name', label: t('sensors.columns.name'), field: 'name', sortable: true, align: 'left' },
  { name: 'live_value', label: t('sensors.columns.live'), field: 'id', align: 'center' },
  { name: 'actions', label: '', field: 'id', align: 'right' },
]);

const { confirmRemove } = useConfirmRemove();
const $q = useQuasar();
const can = usePermissions();
const store = useSensorStore();
const controllerStore = useControllerStore();
const pinStore = useControllerPinStore();
const wsStore = useWebSocketStore();

const dialog = ref(false);
const dialogInfos = ref(false);
const infos = ref<Sensor>();
const edited = ref(false);
const editingId = ref<number | null>(null);
const editingPinId = ref<number | null>(null);
const saving = ref(false);
const search = ref<string | null>('');

const hasController = computed(() => controllerStore.controllers.length > 0);

const v = (key: string) => t(`equipments.validation.${key}`);
const buildSchema = () =>
  z.object({
    name: z.string().trim().min(3, v('min3')).max(30, v('max30')),
    unit: z.enum(['temperature', 'niveau'], { errorMap: () => ({ message: t('sensors.validation.measureRequired') }) }),
    controller_id: z.number({ required_error: v('controllerRequired'), invalid_type_error: v('controllerRequired') }),
    pin_id: z.number({ required_error: v('pinRequired'), invalid_type_error: v('pinRequired') }),
    is_inverted: z.boolean(),
    address: z
      .string()
      .trim()
      .regex(/^(0x)?([0-9a-fA-F]{2}[:\s-]?){7}[0-9a-fA-F]{2}$/, t('sensors.validation.addressFormat'))
      .or(z.literal(''))
      .nullish(),
    interval: z.preprocess(
      (value) => (value === '' ? null : value),
      z.number().int().positive(t('sensors.validation.positive')).nullish(),
    ),
  });

// Messages de validation dans la langue courante
const { handleSubmit, errors, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: unit } = useField<string>('unit');
const { value: controller_id } = useField<number | null>('controller_id');
const { value: pin_id } = useField<number | null>('pin_id');
const { value: is_inverted } = useField<boolean>('is_inverted');
const { value: address } = useField<string | null>('address');
const { value: interval } = useField<number | null>('interval');


const isTemperature = computed(() => unit.value === 'temperature');

function isTemperatureSensor(sensor: Sensor): boolean {
  return ['°c', 'temperature'].includes((sensor.unit ?? '').toLowerCase());
}

const controllerOptions = computed(() =>
  controllerStore.controllers.map((c) => ({ label: `${c.name} (${c.type})`, value: c.id })),
);

const pinOptions = computed(() =>
  (pinStore.controllers_availables_pins || [])
    .filter((pin) => {
      if (!isTemperature.value) return true;
      // 1-Wire = broche native bidirectionnelle : GPIO 34-39 sont en entrée seule sur l'ESP32
      const num = Number(pin.pin_number);
      return !pin.module_id && !Number.isNaN(num) && (num < 34 || num > 39);
    })
    .map((pin) => pinOption(pin, { oneWireProbe: isTemperature.value })),
);

function controllerName(controllerId: number): string {
  return controllerStore.controllers.find((c) => c.id === controllerId)?.name ?? t('equipments.unknownController');
}

function liveState(sensor: Sensor) {
  const controller = controllerStore.controllers.find((c) => c.id === sensor.controller_id);
  if (!controller || wsStore.controllersState[controller.technical_name] !== 'ONLINE') {
    return { label: t('equipments.state.offline'), color: 'grey-6', icon: 'cloud_off' };
  }
  // Plus de mesure : sonde muette (nan, ou rien depuis 3 intervalles) — distinct de « jamais mesurée »
  const silent = wsStore.sensorsState[sensor.id] === null || (sensor.last_value == null && !!sensor.last_reading_at && !(sensor.id in wsStore.sensorsState));
  if (silent) {
    return { label: t('sensors.state.noReading'), color: 'negative', icon: 'sensors_off' };
  }
  const liveVal = wsStore.sensorsState[sensor.id] ?? sensor.last_value;
  if (liveVal == null) return { label: t('sensors.state.waiting'), color: 'grey-6', icon: 'hourglass_empty' };
  if (isTemperatureSensor(sensor)) {
    return { label: `${Number(liveVal).toFixed(1)} °C`, color: 'red-7', icon: 'thermostat' };
  }
  const high = liveVal === 1 || liveVal === '1' || liveVal === true || ['HIGH', 'ON', 'TRUE'].includes(String(liveVal).toUpperCase());
  return high
    ? { label: t('sensors.state.high'), color: 'positive', icon: 'check_circle' }
    : { label: t('sensors.state.low'), color: 'orange-8', icon: 'warning' };
}

const sensors = computed(() => store.getByAquariumId(props.aquaId));

const filteredRows = computed(() => {
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return sensors.value;
  return sensors.value.filter((sensor) =>
    [sensor.name, controllerName(sensor.controller_id), sensor.address ?? ''].some((val) => val.toLowerCase().includes(s)),
  );
});

// --- Sondes 1-Wire détectées sur le contrôleur
const scanning = ref(false);
const scanDone = ref(false);
// Flotteur sur GPIO 34 à 39 : pas de résistance de tirage interne sur l'ESP32
const inputOnlyPin = computed(() => {
  if (isTemperature.value || !pin_id.value) return false;
  const pin = pinStore.controllers_availables_pins.find((p) => p.id === pin_id.value);
  const num = Number(pin?.pin_number);
  return !!pin && !pin.module_id && num >= 34 && num <= 39;
});
const scanResult = ref<OneWireScan | null>(null);
// Rien trouvé : pas de réponse, pas de bus 1-Wire dans le firmware, ou bus sans sonde qui réponde
const noProbeMessage = computed(() => {
  const result = scanResult.value;
  if (!result?.config_received) return t('sensors.form.noProbeNoConfig');
  if (!result.buses.length) return t('sensors.form.noProbe');
  const pins = result.buses.map((b) => (b.pin_number === null ? '?' : `GPIO ${b.pin_number}`)).join(', ');
  return t('sensors.form.noProbeWiring', { pins });
});
const scannedDevices = ref<OneWireDevice[]>([]);

const normalizedAddress = computed(() => {
  const hex = (address.value || '').trim().toLowerCase().replace(/^0x/, '').replace(/[:\s-]/g, '');
  return hex ? `0x${hex}` : '';
});

function probeValue(device: OneWireDevice) {
  const value = Number(device.last_value);
  return device.last_value != null && Number.isFinite(value) ? `${value.toFixed(1)} °C` : null;
}

// Sonde du capteur en cours de modification : sélectionnable, mais signalée comme la sienne
function isCurrentDevice(device: OneWireDevice) {
  return edited.value && device.sensor_id !== null && device.sensor_id === editingId.value;
}

function isDeviceTaken(device: OneWireDevice) {
  return device.sensor_id !== null && !(edited.value && device.sensor_id === editingId.value);
}

// ESPHome ne cherche les sondes qu'au démarrage : redémarrage puis nouvelle recherche
const restarting = ref(false);
async function restartAndSearch() {
  const controllerId = controller_id.value;
  if (!controllerId) return;
  restarting.value = true;
  scanning.value = true;
  try {
    const result = await controllerStore.restartAndWait(controllerId, () => pinStore.scanOneWire(controllerId));
    scannedDevices.value = result.devices;
    scanResult.value = result;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.restart.failed')) });
  } finally {
    restarting.value = false;
    scanning.value = false;
  }
}

async function scanOneWire() {
  if (!controller_id.value) return;
  scanning.value = true;
  try {
    const result = await pinStore.scanOneWire(controller_id.value);
    scannedDevices.value = result.devices;
    scanResult.value = result;
    scanDone.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('sensors.notify.scanFailed')) });
  } finally {
    scanning.value = false;
  }
}

function selectDevice(device: OneWireDevice) {
  address.value = device.address;
  if (device.pin_number === null) return;
  const pin = pinStore.controllers_availables_pins.find((p) => !p.module_id && Number(p.pin_number) === device.pin_number);
  if (pin) pin_id.value = pin.id;
}

async function loadPins(controllerId: number | null | undefined, includePinId?: number | null) {
  if (!controllerId) return;
  try {
    await pinStore.getAvailablesPins(controllerId, includePinId, true);
  } catch {
    $q.notify({ type: 'negative', message: t('equipments.notify.pinsFailed') });
  }
}

// Changement de contrôleur dans le formulaire (pas le remplissage à l'ouverture)
let shownController: number | null = null;
watch(controller_id, (newId) => {
  if (!dialog.value || !newId || newId === shownController) return;
  shownController = newId;
  pin_id.value = null;
  scannedDevices.value = [];
  scanDone.value = false;
  void loadPins(newId, editingPinId.value);
});

const historyOpen = ref(false);
const historySensor = ref<Sensor | null>(null);

function openHistory(sensor: Sensor) {
  historySensor.value = sensor;
  historyOpen.value = true;
}

function openDialogInfos(sensor: Sensor) {
  infos.value = { ...sensor };
  dialogInfos.value = true;
}

function resetScan() {
  scannedDevices.value = [];
  scanDone.value = false;
}

function openDialogAdd() {
  edited.value = false;
  editingId.value = null;
  editingPinId.value = null;
  resetScan();
  const firstController = controllerStore.controllers[0]?.id ?? null;
  shownController = firstController;
  resetForm({
    values: {
      name: '',
      unit: 'temperature',
      is_inverted: false,
      address: '',
      interval: null,
      ...(firstController ? { controller_id: firstController } : {}),
    },
  });
  dialog.value = true;
  void loadPins(firstController);
}

function openDialogEdit(sensor: Sensor) {
  edited.value = true;
  editingId.value = sensor.id;
  editingPinId.value = sensor.pin_id;
  shownController = sensor.controller_id;
  resetScan();
  resetForm({
    values: {
      name: sensor.name,
      unit: isTemperatureSensor(sensor) ? 'temperature' : 'niveau',
      controller_id: sensor.controller_id,
      pin_id: sensor.pin_id,
      is_inverted: sensor.is_inverted ?? false,
      address: sensor.address ?? '',
      interval: sensor.interval ?? null,
    },
  });
  dialog.value = true;
  void loadPins(sensor.controller_id, sensor.pin_id);
}

function closeDialog() {
  dialog.value = false;
}

const submitForm = handleSubmit(async (formValues) => {
  saving.value = true;
  const payload = {
    ...formValues,
    type: formValues.unit === 'temperature' ? 'sensor' : 'binary_sensor',
    address: formValues.unit === 'temperature' ? formValues.address || null : null,
    interval: formValues.unit === 'temperature' ? formValues.interval ?? null : null,
  };
  try {
    let previousControllerId: number | undefined;
    if (edited.value && editingId.value !== null) {
      previousControllerId = store.sensors.find((s) => s.id === editingId.value)?.controller_id;
      await store.update({ ...payload, id: editingId.value });
    } else {
      const creation: SensorCreation = { ...payload, aquarium_id: props.aquaId };
      await store.add(creation);
    }
    // Recharge la liste (numéro de broche à jour)
    await store.fetch();
    controllerStore.markControllerAsDirty(formValues.controller_id);
    if (previousControllerId && previousControllerId !== formValues.controller_id) {
      controllerStore.markControllerAsDirty(previousControllerId);
    }
    $q.notify({ type: 'positive', message: edited.value ? t('sensors.notify.updated') : t('sensors.notify.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('sensors.notify.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(sensor: Sensor) {
  confirmRemove(t('sensors.item', { name: sensor.name }), async () => {
    await store.remove(sensor.id);
    controllerStore.markControllerAsDirty(sensor.controller_id);
  }, { message: t('sensors.deleteMessage', { name: sensor.name }) });
}

onMounted(() => {
  void Promise.all([store.fetch(), controllerStore.fetch()]).catch(() =>
    $q.notify({ type: 'negative', message: t('sensors.notify.loadFailed') }),
  );
});
</script>
