<template>
  <q-page class="app-page">
    <PageHeader icon="memory" :title="t('controllers.title')" :subtitle="t('controllers.subtitle')">
      <template #actions>
        <AppInput v-if="store.controllers.length > 0" v-model="search" icon="search" :placeholder="t('controllers.search')" clearable debounce="300" style="width: 220px" />
        <q-btn v-if="can.manage" outline color="primary" icon="wifi_find" :label="t('controllers.scan')" :loading="searching" @click="searchController">
          <template #loading>
            <q-spinner-radio class="q-mr-sm" />
            {{ t('controllers.scanning') }}
          </template>
        </q-btn>
        <q-btn v-if="can.manage" unelevated color="primary" icon="add" :label="t('controllers.add')" @click="openDialogAdd()" />
      </template>
    </PageHeader>

    <div v-if="is_loading && store.controllers.length === 0" class="flex flex-center q-pa-xl">
      <q-spinner color="primary" size="3em" />
    </div>

    <EmptyState
      v-else-if="store.controllers.length === 0"
      icon="developer_board"
      :title="t('controllers.emptyTitle')"
      :message="t('controllers.emptyMessage')"
    >
      <q-btn v-if="can.manage" outline color="primary" icon="wifi_find" :label="t('controllers.scan')" :loading="searching" @click="searchController" />
      <q-btn v-if="can.manage" unelevated color="primary" icon="add" :label="t('controllers.add')" @click="openDialogAdd()" />
    </EmptyState>

    <EmptyState v-else-if="filteredRows.length === 0" icon="search_off" :title="t('controllers.noResult', { search })" />

    <!-- Grille des cartes -->
    <div v-else class="row q-col-gutter-md">
      <div v-for="controller in filteredRows" :key="controller.id" class="col-12 col-sm-6 col-md-4 col-lg-3">
        <q-card
          flat
          bordered
          class="controller-card hover-card full-height column no-wrap"
          :class="`status-border-${statusMeta(controller).color}`"
        >
          <q-card-section class="q-pb-sm">
            <div class="row items-center justify-between no-wrap">
              <div class="row items-center no-wrap q-gutter-x-sm">
                <q-avatar size="40px" color="blue-1" text-color="primary" icon="developer_board" />
                <div>
                  <div class="text-subtitle1 text-weight-bold">{{ controller.name }}</div>
                  <div class="text-caption text-grey-7">{{ controller.type }} · {{ controller.zone }}</div>
                </div>
              </div>
              <q-chip dense size="sm" :color="statusMeta(controller).color" text-color="white" class="text-weight-bold">
                {{ statusMeta(controller).label }}
              </q-chip>
            </div>
          </q-card-section>

          <q-separator />

          <q-card-section class="col q-py-sm text-body2">
            <div class="row items-center justify-between q-mb-xs">
              <span class="text-grey-7"><q-icon name="router" size="16px" /> {{ t('controllers.ip') }}</span>
              <span class="font-mono">{{ controller.ip || t('controllers.noIp') }}</span>
            </div>

            <div class="row items-start justify-between q-mb-xs">
              <span class="text-grey-7"><q-icon name="extension" size="16px" /> {{ t('controllers.extensions') }}</span>
              <span class="text-right">
                <span v-if="modulesOf(controller).length === 0 && !controller.rtc_model" class="text-grey-6">{{ t('controllers.none') }}</span>
                <div v-if="controller.rtc_model" class="text-caption text-weight-medium">
                  <q-icon name="schedule" size="14px" /> {{ t('controllers.clock', { model: controller.rtc_model }) }}
                </div>
                <div v-for="m in modulesOf(controller)" :key="m.id" class="text-caption">
                  {{ t('controllers.modules.moduleName', { n: m.number, type: m.type }) }} <span class="text-grey-7">({{ m.address }})</span>
                </div>
              </span>
            </div>

            <div v-if="controller.last_sync" class="row items-center justify-between q-mb-xs">
              <span class="text-grey-7"><q-icon name="sync" size="16px" /> {{ t('controllers.lastFlash') }}</span>
              <span class="text-caption text-grey-8">{{ formatDateTime(controller.last_sync) }}</span>
            </div>

            <div v-if="flashStore.progress[controller.id] && flashStore.progress[controller.id]!.status !== 'success'" class="q-mt-sm">
              <div class="row items-center justify-between text-caption">
                <span :class="flashStore.progress[controller.id]!.status === 'failed' ? 'text-negative text-weight-bold' : 'text-grey-8'">
                  <q-icon name="system_update" size="14px" /> {{ flashStore.progress[controller.id]!.phase }}
                </span>
                <span v-if="flashStore.progress[controller.id]!.status === 'running'">{{ flashStore.progress[controller.id]!.percent }} %</span>
              </div>
              <q-linear-progress
                v-if="flashStore.isFlashing(controller.id)"
                :value="flashStore.progress[controller.id]!.percent / 100"
                :indeterminate="flashStore.progress[controller.id]!.status === 'queued'"
                rounded
                size="6px"
                color="primary"
                class="q-mt-xs"
              />
            </div>

            <div
              v-if="controller.is_dirty"
              class="row items-center justify-between no-wrap q-mt-sm bg-amber-1 text-amber-10 q-px-sm q-py-xs rounded-borders"
            >
              <div class="row items-center no-wrap">
                <q-icon name="warning" size="16px" class="q-mr-xs" />
                <span class="text-caption text-weight-medium">{{ t('controllers.dirty') }}</span>
              </div>
              <q-btn flat dense size="sm" icon="difference" :label="t('controllers.see')" color="amber-10" @click="openConfigDialog(controller)">
                <q-tooltip>{{ t('controllers.seePending') }}</q-tooltip>
              </q-btn>
            </div>
          </q-card-section>

          <q-separator />

          <q-card-actions class="q-px-sm q-py-xs">
            <q-btn v-if="can.manage"
              flat
              dense
              color="primary"
              icon="system_update"
              :label="t('controllers.flash')"
              :loading="flashStore.isFlashing(controller.id)"
              :disable="statusOf(controller) === ControllerStatus.OFFLINE"
              @click="openOtaDialog(controller)"
            >
              <q-tooltip v-if="statusOf(controller) === ControllerStatus.OFFLINE">{{ t('controllers.offline') }}</q-tooltip>
            </q-btn>
            <q-space />
            <q-btn v-if="can.manage" flat round dense size="sm" icon="code" color="grey-7" @click="openConfigDialog(controller)">
              <q-tooltip>{{ t('controllers.configTooltip') }}</q-tooltip>
            </q-btn>
            <q-btn flat round dense size="sm" icon="receipt_long" color="grey-7" :aria-label="t('controllers.logs')" @click="openLogsDialog(controller)">
              <q-tooltip>{{ t('controllers.logs') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense size="sm" icon="extension" color="grey-7" @click="openModulesDialog(controller)">
              <q-tooltip>{{ t('controllers.modulesTooltip') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense size="sm" icon="restart_alt" color="grey-7" @click="restartController(controller)">
              <q-tooltip>{{ t('controllers.restart.action') }}</q-tooltip>
            </q-btn>
            <q-btn flat round dense size="sm" icon="info" color="grey-7" @click="openDialogInfos(controller)">
              <q-tooltip>{{ t('controllers.infos') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense size="sm" icon="edit" color="grey-7" @click="openDialogEdit(controller)">
              <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
            </q-btn>
            <q-btn v-if="can.manage" flat round dense size="sm" icon="delete" color="negative" @click="remove(controller)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </q-card-actions>
        </q-card>
      </div>
    </div>

    <!-- Contrôleurs détectés sur le réseau -->
    <FormDialog
      v-model="dialogDiscovered"
      icon="wifi_find"
      :title="t('controllers.discovered.title')"
      :subtitle="t('controllers.discovered.subtitle')"
      width="480px"
      :cancel-label="t('common.close')"
      hide-submit
    >
      <q-list bordered separator class="rounded-borders">
        <q-item v-for="item in discoveredControllers" :key="item.ip" v-ripple clickable @click="selectDiscoveredController(item)">
          <q-item-section avatar>
            <q-avatar color="blue-1" text-color="primary" icon="developer_board" />
          </q-item-section>
          <q-item-section>
            <q-item-label class="text-weight-bold">{{ item.name }}</q-item-label>
            <q-item-label caption>{{ item.ip }} · {{ item.type }}</q-item-label>
          </q-item-section>
          <q-item-section v-if="item.version" side>
            <q-badge outline color="primary" :label="`v${item.version}`" />
          </q-item-section>
        </q-item>
      </q-list>
    </FormDialog>

    <!-- Configuration déployée / à déployer / différences -->
    <ControllerConfigDialog v-model="configDialog" :controller="selectedController" @flash="flashFromConfig" />

    <!-- Journaux du contrôleur -->
    <q-dialog v-model="dialogLogs" maximized transition-show="slide-up" transition-hide="slide-down">
      <q-card class="column no-wrap full-height logs-card">
        <q-card-section class="row items-center no-wrap q-py-sm bg-white">
          <q-avatar size="40px" color="blue-1" text-color="primary" icon="receipt_long" class="q-mr-md" />
          <div class="col">
            <div class="text-h6 text-weight-bold">{{ t('controllers.logs') }}</div>
            <div v-if="selectedController" class="text-body2 text-grey-7">
              {{ selectedController.name }} ({{ selectedController.ip }})
            </div>
          </div>
          <q-btn v-close-popup flat round dense icon="close" color="grey-7" :aria-label="t('common.close')" />
        </q-card-section>
        <q-separator />

        <q-card-section class="col scroll app-page full-width">
          <div class="row items-center gap-sm q-mb-md">
            <AppInput v-model="logSearch" icon="search" :placeholder="t('controllers.logsDialog.filter')" clearable class="bg-white" style="min-width: 260px" />
            <AppSelect v-model="logLevelFilter" :options="logLevels" :label="t('controllers.logsDialog.level')" class="bg-white" style="width: 160px" />
            <q-space />
            <q-btn outline color="primary" icon="refresh" :label="t('controllers.logsDialog.refresh')" :loading="loadingLogs" @click="loadLogs(selectedController?.id)" />
          </div>

          <div v-if="loadingLogs && controllerLogs.length === 0" class="text-center q-py-xl">
            <q-spinner color="primary" size="40px" />
          </div>
          <EmptyState
            v-else-if="filteredLogs.length === 0"
            icon="receipt_long"
            :title="t('controllers.logsDialog.emptyTitle')"
            :message="t('controllers.logsDialog.emptyMessage')"
          />
          <q-card v-else flat bordered>
            <q-list separator>
              <q-item v-for="log in filteredLogs" :key="log.id" dense class="q-py-xs">
                <q-item-section avatar style="min-width: 64px">
                  <q-badge :color="logLevelColor(log.level)" class="text-weight-bold">{{ logLevelLabel(log.level) }}</q-badge>
                </q-item-section>
                <q-item-section>
                  <q-item-label class="text-caption text-grey-6 font-mono">
                    {{ formatDateTime(log.timestamp) }} · <span class="text-weight-bold text-grey-9">{{ log.component }}</span>
                  </q-item-label>
                  <q-item-label class="text-body2 font-mono text-grey-9" style="white-space: pre-wrap">{{ log.message }}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Confirmation du flash OTA -->
    <FormDialog
      v-model="dialogOta"
      icon="system_update"
      :title="t('controllers.ota.title')"
      :subtitle="selectedController ? `${selectedController.name} (${selectedController.ip})` : undefined"
      width="440px"
      :submit-label="t('controllers.ota.submit')"
      submit-icon="bolt"
      @submit="triggerOtaFlash"
    >
      <div class="text-body2">{{ t('controllers.ota.message') }}</div>
    </FormDialog>

    <!-- Informations -->
    <BaseInfoDialog v-model="dialogInfos" :title="t('controllers.infoTitle')" :subtitle="t('controllers.infoSubtitle')" :data="infos" />

    <!-- Création / modification (formulaire ou YAML) -->
    <FormDialog
      v-model="dialog"
      icon="developer_board"
      :title="edited ? t('controllers.form.editTitle') : t('controllers.form.addTitle')"
      :subtitle="discoveredIp ? t('controllers.form.discovered', { ip: discoveredIp }) : t('controllers.form.subtitle')"
      width="600px"
      :loading="saving"
      @submit="onSubmit"
      @hide="closeDialog"
    >
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-6">
          <q-input v-model="name" :label="t('controllers.form.name')" :placeholder="t('controllers.form.namePlaceholder')" outlined dense :error="!!errors.name" :error-message="errors.name" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="zone" :label="t('controllers.form.zone')" :placeholder="t('controllers.form.zonePlaceholder')" outlined dense :error="!!errors.zone" :error-message="errors.zone" />
        </div>
        <div class="col-12 col-sm-6">
          <!-- i18n-ignore : exemple d'adresse -->
          <q-input v-model="ip" :label="t('controllers.form.ip')" placeholder="192.168.1.xxx" outlined dense :error="!!errors.ip" :error-message="errors.ip">
            <template #prepend><q-icon name="router" /></template>
          </q-input>
        </div>
        <div class="col-12 col-sm-6">
          <AppSelect v-model="type" :options="CONTROLLER_TYPES" :label="t('controllers.form.type')" :error="!!errors.type" :error-message="errors.type" />
        </div>
      </div>
    </FormDialog>

    <ControllerModulesDialog v-model="modulesDialog" :controller="modulesController" />
  </q-page>
</template>

<script setup lang="ts">
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref } from 'vue';
import { z } from 'zod';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { toTypedSchema } from '@vee-validate/zod';
import { useField, useForm } from 'vee-validate';
import { useControllerStore } from '../stores/controllerStore';
import { useWebSocketStore } from '../stores/websocket';
import { useFlashStore } from 'src/stores/flashStore';
import type { Controller, ControllerLog } from '../types/controller';
import { ControllerStatus, ControllerType } from '../types/controller';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { pickKeys } from 'src/utils/pick';
import BaseInfoDialog from 'src/components/BaseInfoDialog.vue';
import FormDialog from 'src/components/FormDialog.vue';
import ControllerModulesDialog from 'src/components/ControllerModulesDialog.vue';
import ControllerConfigDialog from 'src/components/ControllerConfigDialog.vue';
import AppInput from 'src/components/AppInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDateTime } from 'src/utils/format';

interface DiscoveredController {
  name: string;
  ip: string;
  type: ControllerType;
  version?: string;
}

const CONTROLLER_TYPES = [
  { label: 'ESP32', value: ControllerType.ESP32 },
  { label: 'ESP8266', value: ControllerType.ESP8266 },
  { label: 'Raspberry Pi', value: ControllerType.RPI },
  { label: 'Arduino', value: ControllerType.ARDUINO },
];

const $q = useQuasar();
const { t } = useI18n();

const logLevels = computed(() =>
  (['ALL', 'I', 'W', 'E'] as const).map((value) => ({ label: t(`controllers.logsDialog.levels.${value}`), value })),
);
const can = usePermissions();
const store = useControllerStore();
const wsStore = useWebSocketStore();
const flashStore = useFlashStore();
const { confirmRemove } = useConfirmRemove();

const dialog = ref(false);
const dialogInfos = ref(false);
const dialogOta = ref(false);
const dialogDiscovered = ref(false);
const configDialog = ref(false);
const dialogLogs = ref(false);

const loadingLogs = ref(false);
const controllerLogs = ref<ControllerLog[]>([]);
const logSearch = ref<string | null>('');
const logLevelFilter = ref('ALL');

const selectedController = ref<Controller | null>(null);
const discoveredControllers = ref<DiscoveredController[]>([]);
// IP d'un contrôleur détecté sur le réseau : premier flash OTA à l'enregistrement
const discoveredIp = ref<string | null>(null);

const infos = ref<Controller>();
const edited = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const search = ref<string | null>('');
const is_loading = ref(false);
const searching = ref(false);

const FIELDS = ['name', 'type', 'zone', 'ip'] as const;

const buildSchema = () =>
  z.object({
    name: z.string().trim().min(3, t('controllers.errors.nameMin')).max(30, t('controllers.errors.nameMax')),
    type: z.nativeEnum(ControllerType),
    zone: z.string().trim().min(2, t('controllers.errors.zone')),
    ip: z.string().ip({ version: 'v4', message: t('controllers.errors.ip') }),
  });
type FormValues = z.infer<ReturnType<typeof buildSchema>>;

const { handleSubmit, errors, resetForm } = useForm({ validationSchema: computed(() => toTypedSchema(buildSchema())) });

const { value: name } = useField<string>('name');
const { value: type } = useField<ControllerType>('type');
const { value: zone } = useField<string>('zone');
const { value: ip } = useField<string>('ip');


function statusOf(controller: Controller): ControllerStatus {
  const live =
    wsStore.controllersState[`controller_${controller.id}`] ??
    (controller.technical_name ? wsStore.controllersState[controller.technical_name] : undefined);
  return (live as ControllerStatus | undefined) ?? controller.status ?? ControllerStatus.OFFLINE;
}

const STATUS_COLORS: Record<ControllerStatus, string> = {
  [ControllerStatus.ONLINE]: 'teal',
  [ControllerStatus.OFFLINE]: 'red',
  [ControllerStatus.INITIALIZING]: 'blue',
  [ControllerStatus.FLASHING]: 'blue',
  [ControllerStatus.FLASH_FAILED]: 'negative',
  [ControllerStatus.ERROR]: 'negative',
};

function statusMeta(controller: Controller) {
  const status = statusOf(controller);
  const color = STATUS_COLORS[status];
  return color ? { label: t(`controllers.status.${status}`), color } : { label: status, color: 'deep-orange' };
}

const filteredRows = computed(() => {
  const s = (search.value ?? '').trim().toLowerCase();
  if (!s) return store.controllers;
  return store.controllers.filter((c) =>
    [c.name, c.zone, c.ip ?? '', c.type].some((val) => String(val).toLowerCase().includes(s)),
  );
});

// --- Journaux
async function openLogsDialog(controller: Controller) {
  selectedController.value = controller;
  controllerLogs.value = [];
  dialogLogs.value = true;
  await loadLogs(controller.id);
}

async function loadLogs(controllerId?: number) {
  if (!controllerId) return;
  loadingLogs.value = true;
  try {
    controllerLogs.value = await store.fetchControllerLogs(controllerId);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.notify.logsFailed')) });
  } finally {
    loadingLogs.value = false;
  }
}

function normalizedLevel(level: string): 'E' | 'W' | 'I' {
  const upper = (level ?? '').toUpperCase();
  if (upper.startsWith('E')) return 'E';
  if (upper.startsWith('W')) return 'W';
  return 'I';
}

function logLevelColor(level: string): string {
  return { E: 'negative', W: 'orange-8', I: 'primary' }[normalizedLevel(level)];
}

function logLevelLabel(level: string): string {
  return t(`controllers.logsDialog.short.${normalizedLevel(level)}`);
}

const filteredLogs = computed(() => {
  const s = (logSearch.value ?? '').trim().toLowerCase();
  return controllerLogs.value.filter((log) => {
    const matchesLevel = logLevelFilter.value === 'ALL' || normalizedLevel(log.level) === logLevelFilter.value;
    const matchesSearch = !s || log.message.toLowerCase().includes(s) || log.component.toLowerCase().includes(s);
    return matchesLevel && matchesSearch;
  });
});

// --- Configuration (YAML déployé / à déployer)
function openConfigDialog(controller: Controller) {
  selectedController.value = controller;
  configDialog.value = true;
}

function flashFromConfig() {
  configDialog.value = false;
  if (selectedController.value) openOtaDialog(selectedController.value);
}

// --- Flash OTA
function openOtaDialog(controller: Controller) {
  selectedController.value = controller;
  dialogOta.value = true;
}

async function triggerOtaFlash() {
  const controller = selectedController.value;
  if (!controller) return;
  dialogOta.value = false;
  try {
    await flashStore.flash(controller.id, controller.ip);
    $q.notify({ type: 'info', message: t('controllers.notify.flashStarted', { name: controller.name }) });
  } catch {
    // Notification déjà affichée par le store
  }
}

// --- Création / modification
function openDialogAdd(prefill?: DiscoveredController) {
  edited.value = false;
  editingId.value = null;
  discoveredIp.value = prefill?.ip ?? null;
  resetForm({
    values: {
      name: prefill?.name ?? '',
      type: prefill?.type ?? ControllerType.ESP32,
      zone: '',
      ip: prefill?.ip ?? '',
    },
  });
  dialog.value = true;
}

function openDialogEdit(controller: Controller) {
  edited.value = true;
  editingId.value = controller.id;
  discoveredIp.value = null;
  resetForm({ values: pickKeys<FormValues>(controller, FIELDS) });
  dialog.value = true;
}

function closeDialog() {
  dialog.value = false;
  discoveredIp.value = null;
}

function openDialogInfos(controller: Controller) {
  infos.value = controller;
  dialogInfos.value = true;
}

function remove(controller: Controller) {
  confirmRemove(t('controllers.item', { name: controller.name }), () => store.remove(controller.id), {
    message: t('controllers.deleteMessage', { name: controller.name }),
  });
}

async function searchController() {
  searching.value = true;
  try {
    const res = await store.searchController();
    const list = (Array.isArray(res) ? res : [res]).filter(Boolean) as DiscoveredController[];
    if (list.length === 0) {
      $q.notify({ type: 'warning', message: t('controllers.notify.noneFound') });
      return;
    }
    discoveredControllers.value = list;
    dialogDiscovered.value = true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.notify.scanFailed')) });
  } finally {
    searching.value = false;
  }
}

function selectDiscoveredController(controller: DiscoveredController) {
  dialogDiscovered.value = false;
  openDialogAdd(controller);
}

const submitForm = handleSubmit(async (formValues) => {
  saving.value = true;
  try {
    if (edited.value && editingId.value !== null) {
      await store.update(editingId.value, formValues);
      $q.notify({ type: 'positive', message: t('controllers.notify.updated') });
    } else {
      await store.add({ ...formValues, status: ControllerStatus.INITIALIZING }, discoveredIp.value ?? undefined);
      $q.notify({
        type: 'positive',
        message: discoveredIp.value ? t('controllers.notify.addedFlashing') : t('controllers.notify.added'),
      });
    }
    closeDialog();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.notify.saveFailed')) });
  } finally {
    saving.value = false;
  }
});

function onSubmit() {
  void submitForm();
}

// --- Modules d'extension
const modulesDialog = ref(false);
const modulesController = ref<Controller | null>(null);

function modulesOf(controller: Controller) {
  return store.modulesMap[controller.id] ?? [];
}

function restartController(controller: Controller) {
  $q.dialog({
    title: t('controllers.restart.action'),
    message: t('controllers.restart.confirm', { name: controller.name }),
    ok: { label: t('controllers.restart.action'), color: 'primary', unelevated: true },
    cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
  }).onOk(() => {
    void store
      .restart(controller.id)
      .then(() => $q.notify({ type: 'info', icon: 'restart_alt', message: t('controllers.restart.sent', { name: controller.name }) }))
      .catch((err: unknown) => $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.restart.failed')) }));
  });
}

function openModulesDialog(controller: Controller) {
  modulesController.value = controller;
  modulesDialog.value = true;
}

onMounted(async () => {
  is_loading.value = true;
  try {
    await store.fetch();
    await Promise.all(store.controllers.map((c) => store.fetchModules(c.id)));
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('controllers.notify.loadFailed')) });
  } finally {
    is_loading.value = false;
  }
});
</script>

<style scoped>
.logs-card {
  background: var(--app-page-bg);
}

</style>
