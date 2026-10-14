<template>
  <div>
    <PageHeader section :title="t('equipments.title')" :subtitle="t('equipments.subtitle')">
      <template #actions>
        <AppInput v-if="equipments.length > 0" v-model="search" icon="search" :placeholder="t('equipments.search')" clearable style="width: 220px" />
        <q-btn v-if="equipments.length > 0" outline color="primary" icon="bolt" :label="t('equipments.usage')" @click="usageOpen = true" />
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('equipments.add')" :disable="!hasController" @click="openDialogAdd" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="!hasController"
      icon="memory"
      :title="t('equipments.noControllerTitle')"
      :message="t('equipments.noControllerMessage')"
    >
      <q-btn v-if="can.manage" unelevated color="primary" icon="memory" :label="t('equipments.addController')" to="/controllers" />
    </EmptyState>

    <EmptyState
      v-else-if="equipments.length === 0"
      icon="settings_input_component"
      :title="t('equipments.emptyTitle')"
      :message="t('equipments.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('equipments.add')" @click="openDialogAdd" />
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
              <q-avatar size="36px" color="blue-1" text-color="primary" :icon="categoryIcon(props.row.category)" class="q-mr-sm" />
              <div>
                <div class="text-weight-bold">{{ props.row.name }}</div>
                <div class="text-caption text-grey-7">
                  {{ categoryLabel(props.row.category) }} · {{ controllerName(props.row.controller_id) }}
                  <template v-if="pinLabel(props.row.pin_number, props.row.module_id, props.row.module_number)"> · {{ pinLabel(props.row.pin_number, props.row.module_id, props.row.module_number) }}</template>
                </div>
              </div>
            </div>
          </q-td>
        </template>

        <template #body-cell-status="props">
          <q-td :props="props">
            <q-chip dense :color="liveState(props.row).color" text-color="white" :icon="liveState(props.row).icon">
              {{ liveState(props.row).label }}
            </q-chip>
          </q-td>
        </template>

        <template #body-cell-mode="props">
          <q-td :props="props">
            <!-- Mode sans effet sans règle : pilotage direct -->
            <span v-if="!isAutomated(props.row.id)" class="text-caption text-grey-6">
              {{ t('equipments.noRules') }}
              <q-tooltip>{{ t('equipments.noRulesHelp') }}</q-tooltip>
            </span>
            <q-btn-toggle
              v-else
              :model-value="isAutoMode(props.row) ? EquipmentMode.AUTO : EquipmentMode.MANUAL"
              dense
              unelevated
              size="sm"
              toggle-color="primary"
              color="grey-2"
              text-color="grey-8"
              :disable="!can.edit || !isControllerOnline(props.row)"
              :options="[
                { label: t('equipments.auto'), value: EquipmentMode.AUTO },
                { label: t('equipments.manual'), value: EquipmentMode.MANUAL },
              ]"
              @update:model-value="(mode: EquipmentMode) => onModeChange(props.row, mode)"
            />
          </q-td>
        </template>

        <template #body-cell-power="props">
          <q-td :props="props">
            <q-toggle
              :model-value="isEquipmentOn(props.row)"
              color="positive"
              dense
              :disable="!can.edit || !isControllerOnline(props.row) || isRuleDriven(props.row)"
              @update:model-value="(isOn: boolean) => onStatusChange(props.row, isOn ? EquipmentStatus.ON : EquipmentStatus.OFF)"
            >
              <q-tooltip v-if="isRuleDriven(props.row)">{{ t('equipments.forceHelp') }}</q-tooltip>
            </q-toggle>
          </q-td>
        </template>

        <template #body-cell-actions="props">
          <q-td :props="props">
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
      icon="settings_input_component"
      :title="edited ? t('equipments.form.editTitle') : t('equipments.add')"
      :subtitle="t('equipments.form.subtitle')"
      width="680px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-7">
          <q-input v-model="name" :label="t('equipments.form.name')" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-12 col-sm-5">
          <AppSelect v-model="category" :options="categoryOptions" :label="t('equipments.form.category')" :error="!!errors.category" :error-message="errors.category">
            <template #option="scope">
              <q-item v-bind="scope.itemProps">
                <q-item-section avatar><q-icon :name="categoryIcon(scope.opt.value)" /></q-item-section>
                <q-item-section>{{ scope.opt.label }}</q-item-section>
              </q-item>
            </template>
          </AppSelect>
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect v-model="controller_id" :options="controllerOptions" :label="t('equipments.form.controller')" :error="!!errors.controller_id" :error-message="errors.controller_id" />
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect
            v-model="pin_id"
            :options="pinOptions"
            :label="t('equipments.form.pin')"
            :disable="!controller_id"
            :error="!!errors.pin_id"
            :error-message="errors.pin_id"
          />
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect
            v-model="physical_contact"
            :options="[
              { label: t('equipments.form.contactNo'), value: PhysicalContact.NO },
              { label: t('equipments.form.contactNc'), value: PhysicalContact.NC },
            ]"
            :label="t('equipments.form.contact')"
            :error="!!errors.physical_contact"
            :error-message="errors.physical_contact"
          />
        </div>
        <div class="col-12 col-sm-6">
          <q-input
            v-model.number="restart_delay"
            type="number"
            :label="t('equipments.form.restartDelay')"
            suffix="s"
            :hint="t('equipments.form.restartDelayHint')"
            outlined
            dense
            :error="!!errors.restart_delay"
            :error-message="errors.restart_delay"
          />
        </div>
        <div v-if="category === EquipmentCategory.OSMOLATOR" class="col-12 col-sm-6">
          <q-input
            v-model.number="max_duration_seconds"
            type="number"
            :label="t('equipments.form.safety')"
            suffix="s"
            placeholder="45"
            :hint="t('equipments.form.safetyHint')"
            clearable
            outlined
            dense
            :error="!!errors.max_duration_seconds"
            :error-message="errors.max_duration_seconds"
          />
        </div>
        <div v-if="!edited" class="col-12 col-sm-6">
          <div class="text-caption text-grey-7 q-mb-xs">{{ t('equipments.form.startMode') }}</div>
          <q-btn-toggle
            v-model="mode"
            spread
            unelevated
            toggle-color="primary"
            color="grey-2"
            text-color="grey-8"
            :options="[
              { label: t('equipments.automatic'), value: EquipmentMode.AUTO },
              { label: t('equipments.manual'), value: EquipmentMode.MANUAL },
            ]"
          />
        </div>
        <div class="col-12">
          <q-card flat bordered class="q-px-md q-py-sm">
            <q-toggle v-model="inverted" color="primary" :label="t('equipments.form.invert')" />
            <div class="text-caption text-grey-7">{{ t('equipments.form.invertHint') }}</div>
          </q-card>
        </div>
      </div>
    </FormDialog>

    <!-- Informations -->
    <BaseInfoDialog
      v-model="dialogInfos"
      :title="t('equipments.form.infoTitle')"
      :subtitle="t('equipments.form.infoSubtitle')"
      :data="infos"
    />
    <EquipmentUsageDialog v-model="usageOpen" :aquarium-id="aquaId" />
  </div>
</template>

<script setup lang="ts">
import { pinLabel, pinOption } from 'src/utils/pins';
import AppTable from 'src/components/AppTable.vue';
import EquipmentUsageDialog from 'src/components/EquipmentUsageDialog.vue';
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref, watch } from 'vue';
import { z } from 'zod';
import { useForm, useField } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import { type QTableColumn, useQuasar } from 'quasar';
import { useEquipmentAutomation } from 'src/composables/useEquipmentAutomation';
import { useI18n } from 'vue-i18n';
import {
  EquipmentCategory,
  EquipmentMode,
  EquipmentStatus,
  PhysicalContact,
  type Equipment,
  type EquipmentCreation,
} from '../types/equipment';
import { useEquipmentStore } from '../stores/equipmentStore';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { pickKeys } from 'src/utils/pick';
import { useControllerStore } from 'src/stores/controllerStore';
import { useControllerPinStore } from 'src/stores/controllerPinStore';
import { useWebSocketStore } from 'src/stores/websocket';
import { useFaultStore } from 'src/stores/faultStore';
import BaseInfoDialog from 'src/components/BaseInfoDialog.vue';
import FormDialog from 'src/components/FormDialog.vue';
import AppInput from 'src/components/AppInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { apiErrorMessage } from 'src/utils/apiError';

const props = defineProps({ aquaId: { type: Number, required: true } });
const { t } = useI18n();
const { isAutomated } = useEquipmentAutomation();
const usageOpen = ref(false);

// Libellés : equipments.categories.*
const CATEGORY_ICONS: Record<EquipmentCategory, string> = {
  [EquipmentCategory.OSMOLATOR]: 'water_drop',
  [EquipmentCategory.OSMOSEUR]: 'filter_alt',
  [EquipmentCategory.PUMP]: 'cyclone',
  [EquipmentCategory.BRASSAGE]: 'waves',
  [EquipmentCategory.ECUMOR]: 'bubble_chart',
  [EquipmentCategory.COOLER]: 'ac_unit',
  [EquipmentCategory.HEATER]: 'local_fire_department',
  [EquipmentCategory.LIGHT]: 'lightbulb',
  [EquipmentCategory.OTHER]: 'power',
};

const categoryOptions = computed(() =>
  (Object.keys(CATEGORY_ICONS) as EquipmentCategory[]).map((value) => ({ label: categoryLabel(value), value })),
);

function categoryLabel(cat?: EquipmentCategory): string {
  return t(`equipments.categories.${cat && cat in CATEGORY_ICONS ? cat : EquipmentCategory.OTHER}`);
}

function categoryIcon(cat?: EquipmentCategory): string {
  return (cat && CATEGORY_ICONS[cat]) || 'power';
}

const columns = computed<QTableColumn<Equipment>[]>(() => [
  { name: 'name', label: t('equipments.columns.name'), field: 'name', sortable: true, align: 'left' },
  { name: 'status', label: t('equipments.columns.status'), field: 'status', align: 'center' },
  { name: 'mode', label: t('equipments.columns.mode'), field: 'mode', align: 'center' },
  { name: 'power', label: t('equipments.columns.power'), field: 'id', align: 'center' },
  { name: 'actions', label: '', field: 'id', align: 'right' },
]);

const { confirmRemove } = useConfirmRemove();
const $q = useQuasar();
const can = usePermissions();
const store = useEquipmentStore();
const controllerStore = useControllerStore();
const pinStore = useControllerPinStore();
const wsStore = useWebSocketStore();
const faultStore = useFaultStore();

const dialog = ref(false);
const dialogInfos = ref(false);
const infos = ref<Equipment>();
const edited = ref(false);
const editingId = ref<number | null>(null);
const editingPinId = ref<number | null>(null);
const saving = ref(false);
const search = ref<string | null>('');

const hasController = computed(() => controllerStore.controllers.length > 0);

const FIELDS = [
  'name',
  'category',
  'controller_id',
  'pin_id',
  'physical_contact',
  'inverted',
  'restart_delay',
  'max_duration_seconds',
  'mode',
] as const;

const v = (key: string) => t(`equipments.validation.${key}`);
const buildSchema = () =>
  z.object({
    name: z.string().trim().min(3, v('min3')).max(30, v('max30')),
    category: z.nativeEnum(EquipmentCategory),
    controller_id: z.number({ required_error: v('controllerRequired'), invalid_type_error: v('controllerRequired') }),
    pin_id: z.number({ required_error: v('pinRequired'), invalid_type_error: v('pinRequired') }),
    physical_contact: z.nativeEnum(PhysicalContact),
    inverted: z.boolean(),
    restart_delay: z.number({ invalid_type_error: v('number') }).int().min(0, v('positive')),
    // Coupure de sécurité de l'osmolateur (45 s côté ESP si vide)
    max_duration_seconds: z.preprocess(
      (value) => (value === '' || value === undefined ? null : value),
      z.number().int().min(5, v('min5s')).max(3600, v('max3600s')).nullable(),
    ),
    mode: z.nativeEnum(EquipmentMode),
  });
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

// Messages de validation dans la langue courante
const { handleSubmit, errors, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: category } = useField<EquipmentCategory>('category');
const { value: controller_id } = useField<number | null>('controller_id');
const { value: pin_id } = useField<number | null>('pin_id');
const { value: physical_contact } = useField<PhysicalContact>('physical_contact');
const { value: inverted } = useField<boolean>('inverted');
const { value: restart_delay } = useField<number>('restart_delay');
const { value: max_duration_seconds } = useField<number | null>('max_duration_seconds');
const { value: mode } = useField<EquipmentMode>('mode');


const controllerOptions = computed(() =>
  controllerStore.controllers.map((c) => ({ label: `${c.name} (${c.type})`, value: c.id })),
);

const pinOptions = computed(() =>
  (pinStore.controllers_availables_pins || []).map((pin) => pinOption(pin)),
);

function controllerName(controllerId: number): string {
  return controllerStore.controllers.find((c) => c.id === controllerId)?.name ?? t('equipments.unknownController');
}

function isControllerOnline(equipment: Equipment): boolean {
  const controller = controllerStore.controllers.find((c) => c.id === equipment.controller_id);
  if (!controller?.technical_name) return false;
  return wsStore.controllersState[controller.technical_name] === 'ONLINE';
}

function isAutoMode(equipment: Equipment): boolean {
  return equipment.mode == null || String(equipment.mode).toUpperCase() === String(EquipmentMode.AUTO);
}

// Interrupteur réservé aux règles : équipement piloté par des règles et en AUTO
function isRuleDriven(equipment: Equipment): boolean {
  return isAutomated(equipment.id) && isAutoMode(equipment);
}

function parseIsOn(val: unknown): boolean {
  if (val === true || val === 1 || val === '1') return true;
  const raw = typeof val === 'object' && val !== null && 'status' in val ? val.status : val;
  return typeof raw === 'string' && raw.toUpperCase() === String(EquipmentStatus.ON);
}

function isEquipmentOn(equipment: Equipment): boolean {
  const liveVal = wsStore.equipmentsState[equipment.id];
  return parseIsOn(liveVal ?? equipment.status);
}

function liveState(equipment: Equipment) {
  if (!isControllerOnline(equipment)) return { label: t('equipments.state.offline'), color: 'grey-6', icon: 'cloud_off' };
  if (faultStore.openFaults.some((f) => f.equipment_id === equipment.id)) {
    return { label: t('equipments.state.fault'), color: 'negative', icon: 'report_problem' };
  }
  return isEquipmentOn(equipment)
    ? { label: t('equipments.state.on'), color: 'positive', icon: 'power' }
    : { label: t('equipments.state.off'), color: 'grey-7', icon: 'power_off' };
}

const equipments = computed(() => store.getByAquariumId(props.aquaId));

const filteredRows = computed(() => {
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return equipments.value;
  return equipments.value.filter((eq) =>
    [eq.name, categoryLabel(eq.category), controllerName(eq.controller_id)].some((val) => val.toLowerCase().includes(s)),
  );
});

async function loadPins(controllerId: number | null | undefined, includePinId?: number | null) {
  if (!controllerId) return;
  try {
    await pinStore.getAvailablesPins(controllerId, includePinId, true);
  } catch {
    $q.notify({ type: 'negative', message: t('equipments.notify.pinsFailed') });
  }
}

// Changement de contrôleur dans le formulaire : broches de ce contrôleur.
// shownController évite de réagir au remplissage du formulaire à l'ouverture.
let shownController: number | null = null;
watch(controller_id, (newId) => {
  if (!dialog.value || !newId || newId === shownController) return;
  shownController = newId;
  pin_id.value = null;
  void loadPins(newId, editingPinId.value);
});

// Valeur par défaut de l'inversion selon le contact (NC = logique inversée)
watch(physical_contact, (contact) => {
  if (dialog.value && !edited.value) inverted.value = contact === PhysicalContact.NC;
});

function openDialogInfos(equipment: Equipment) {
  infos.value = { ...equipment };
  dialogInfos.value = true;
}

function openDialogAdd() {
  edited.value = false;
  editingId.value = null;
  editingPinId.value = null;
  const firstController = controllerStore.controllers[0]?.id ?? null;
  shownController = firstController;
  resetForm({
    values: {
      name: '',
      category: EquipmentCategory.OTHER,
      physical_contact: PhysicalContact.NO,
      inverted: false,
      restart_delay: 0,
      max_duration_seconds: null,
      mode: EquipmentMode.AUTO,
      ...(firstController ? { controller_id: firstController } : {}),
    },
  });
  dialog.value = true;
  void loadPins(firstController);
}

function openDialogEdit(equipment: Equipment) {
  edited.value = true;
  editingId.value = equipment.id;
  editingPinId.value = equipment.pin_id;
  shownController = equipment.controller_id;
  resetForm({
    values: {
      ...pickKeys<FormValues>(equipment, FIELDS),
      category: equipment.category ?? EquipmentCategory.OTHER,
      inverted: equipment.inverted ?? false,
      max_duration_seconds: equipment.max_duration_seconds ?? null,
      mode: equipment.mode ?? EquipmentMode.AUTO,
    },
  });
  dialog.value = true;
  void loadPins(equipment.controller_id, equipment.pin_id);
}

function closeDialog() {
  dialog.value = false;
}

const submitForm = handleSubmit(async (formValues) => {
  saving.value = true;
  try {
    let previousControllerId: number | undefined;
    if (edited.value && editingId.value !== null) {
      previousControllerId = store.equipments.find((e) => e.id === editingId.value)?.controller_id;
      // Le mode se change depuis le tableau : il doit être envoyé au contrôleur
      const update: Partial<FormValues> = { ...formValues };
      delete update.mode;
      await store.update({ ...update, id: editingId.value });
    } else {
      const payload: EquipmentCreation = { ...formValues, aquarium_id: props.aquaId, status: EquipmentStatus.OFF };
      await store.add(payload);
    }
    controllerStore.markControllerAsDirty(formValues.controller_id);
    if (previousControllerId && previousControllerId !== formValues.controller_id) {
      controllerStore.markControllerAsDirty(previousControllerId);
    }
    $q.notify({ type: 'positive', message: edited.value ? t('equipments.notify.updated') : t('equipments.notify.added') });
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.notify.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

function remove(equipment: Equipment) {
  confirmRemove(t('equipments.item', { name: equipment.name }), async () => {
    await store.remove(equipment.id);
    controllerStore.markControllerAsDirty(equipment.controller_id);
  });
}

async function onModeChange(equipment: Equipment, newMode: EquipmentMode) {
  const previousMode = equipment.mode;
  equipment.mode = newMode;
  try {
    await store.mode({ id: equipment.id, mode: newMode });
  } catch (err) {
    equipment.mode = previousMode;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.notify.modeFailed')) });
  }
}

async function onStatusChange(equipment: Equipment, newStatus: EquipmentStatus) {
  const previousStatus = equipment.status;
  equipment.status = newStatus;
  wsStore.equipmentsState[equipment.id] = newStatus;
  try {
    await store.status({ id: equipment.id, status: newStatus });
  } catch (err) {
    equipment.status = previousStatus;
    wsStore.equipmentsState[equipment.id] = previousStatus;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.notify.commandFailed')) });
  }
}

onMounted(() => {
  void Promise.all([store.fetch(), controllerStore.fetch(), faultStore.fetchOpen()]).catch(() =>
    $q.notify({ type: 'negative', message: t('equipments.notify.loadFailed') }),
  );
});
</script>
