<!--
  Sauvegardes : réglages (automatique, contenu, destination locale ou
  externe comme un partage NFS), liste des sauvegardes, création, export,
  import et restauration depuis la liste.
-->
<template>
  <q-page class="app-page">
    <PageHeader icon="backup" :title="t('backup.title')" :subtitle="t('backup.subtitle')">
      <template #actions>
        <q-btn outline color="primary" icon="upload" :label="t('backup.import')" @click="filePicker?.click()" />
        <q-btn-dropdown
          split
          unelevated
          color="primary"
          icon="backup"
          :label="$q.screen.lt.sm ? t('backup.saveShort') : t('backup.saveNow')"
          :loading="creating"
          @click="createNow()"
        >
          <q-list style="min-width: 260px">
            <q-item v-close-popup clickable @click="openCustom('create')">
              <q-item-section avatar><q-icon name="tune" /></q-item-section>
              <q-item-section>
                <q-item-label>{{ t('backup.customCreate') }}</q-item-label>
                <q-item-label caption>{{ t('backup.customCreateCaption') }}</q-item-label>
              </q-item-section>
            </q-item>
            <q-item v-close-popup clickable @click="openCustom('export')">
              <q-item-section avatar><q-icon name="download" /></q-item-section>
              <q-item-section>
                <q-item-label>{{ t('backup.customExport') }}</q-item-label>
                <q-item-label caption>{{ t('backup.customExportCaption') }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-btn-dropdown>
        <input ref="filePicker" type="file" accept=".zip" class="hidden" @change="handleFileSelected" />
      </template>
    </PageHeader>

    <div class="row q-col-gutter-md q-mb-md">
      <!-- Sauvegarde automatique -->
      <div class="col-12 col-md-4">
        <q-card flat bordered class="full-height">
          <q-card-section class="row items-center no-wrap">
            <q-icon name="schedule" color="primary" size="22px" class="q-mr-sm" />
            <div class="text-subtitle1 text-weight-bold col">{{ t('backup.auto') }}</div>
            <q-toggle v-model="form.enabled" color="positive" :aria-label="t('backup.enableAuto')" />
          </q-card-section>
          <q-card-section class="q-pt-none column gap-sm" :class="{ 'section-off': !form.enabled }">
            <div class="row q-col-gutter-sm">
              <div class="col-6">
                <q-select v-model="form.frequency" :options="frequencies" emit-value map-options :label="t('backup.frequency')" outlined dense />
              </div>
              <div class="col-6">
                <q-select v-model="form.hour" :options="hours" emit-value map-options :label="t('backup.hour')" outlined dense />
              </div>
              <div v-if="form.frequency === 'weekly'" class="col-12">
                <q-select v-model="form.weekday" :options="weekdays" emit-value map-options :label="t('backup.weekday')" outlined dense />
              </div>
            </div>
            <q-input
              v-model.number="form.keep_count"
              type="number"
              min="1"
              max="365"
              :label="t('backup.keep')"
              outlined
              dense
              :hint="t('backup.keepHint')"
            />
            <div v-if="settings?.next_run_at && form.enabled" class="text-caption text-grey-7">
              {{ t('backup.next', { date: formatDateTime(settings.next_run_at) }) }}
            </div>
            <div v-if="settings?.last_run_at" class="text-caption">
              <span class="app-tag" :class="settings.last_status === 'ok' ? 'app-tag--ok' : 'app-tag--danger'">
                {{ settings.last_status === 'ok' ? t('backup.ok') : t('backup.failed') }}
              </span>
              {{ t('backup.last', { date: formatDateTime(settings.last_run_at) }) }}
              <div v-if="settings.last_status !== 'ok'" class="text-negative q-mt-xs">{{ settings.last_message }}</div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Contenu -->
      <div class="col-12 col-sm-6 col-md-4">
        <q-card flat bordered class="full-height">
          <q-card-section class="row items-center no-wrap">
            <q-icon name="inventory_2" color="primary" size="22px" class="q-mr-sm" />
            <div class="text-subtitle1 text-weight-bold">{{ t('backup.content') }}</div>
          </q-card-section>
          <q-card-section class="q-pt-none">
            <q-checkbox :model-value="true" disable :label="t('backup.databaseAlways')" />
            <div v-for="part in parts" :key="part">
              <q-checkbox v-model="form[`include_${part}`]" :label="partLabel(part)" />
              <div class="text-caption text-grey-7 part-caption">{{ t(`backup.parts.${part}.caption`) }}</div>
            </div>
          </q-card-section>
        </q-card>
      </div>

      <!-- Destination -->
      <div class="col-12 col-sm-6 col-md-4">
        <q-card flat bordered class="full-height">
          <q-card-section class="row items-center no-wrap">
            <q-icon name="storage" color="primary" size="22px" class="q-mr-sm" />
            <div class="text-subtitle1 text-weight-bold">{{ t('backup.destination') }}</div>
          </q-card-section>
          <q-card-section class="q-pt-none column gap-sm">
            <q-option-group
              v-model="form.destination"
              :options="[
                { label: t('backup.local'), value: 'local' },
                { label: t('backup.external'), value: 'external' },
              ]"
            />
            <q-input
              v-model="form.external_path"
              :label="t('backup.externalPath')"
              :placeholder="NFS_EXAMPLE"
              outlined
              dense
              :disable="form.destination !== 'external' && !form.external_path"
              :hint="t('backup.externalHint')"
            >
              <template #append>
                <q-btn flat dense no-caps size="sm" color="primary" :label="t('backup.test')" :loading="testing" :disable="!form.external_path" @click="testDestination" />
              </template>
            </q-input>
            <a :href="t('backup.nfsDocUrl')" target="_blank" rel="noopener noreferrer" class="text-caption text-primary row items-center no-wrap">
              <q-icon name="menu_book" size="16px" class="q-mr-xs" />{{ t('backup.nfsDoc') }}<q-icon name="open_in_new" size="12px" class="q-ml-xs" />
            </a>
            <div v-if="settings?.external_path && settings.external_ok === false" class="app-callout app-callout--danger text-caption">
              <q-icon name="error" size="18px" />
              <div>{{ settings.external_error }}</div>
            </div>
            <div v-else-if="settings?.external_path && settings.external_ok" class="text-caption text-positive">
              <q-icon name="check_circle" class="q-mr-xs" />{{ t('backup.externalOk') }}
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <div class="row justify-end q-mb-lg">
      <q-btn unelevated color="primary" icon="save" :label="t('backup.saveSettings')" :loading="saving" @click="saveSettings" />
    </div>

    <!-- Liste -->
    <q-card flat bordered>
      <AppTable
        :title="t('backup.list')"
        :rows="backupStore.backups"
        :columns="columns"
        :row-key="(r: BackupInfo) => `${r.location}/${r.filename}`"
        :loading="backupStore.loading"
        :pagination="{ rowsPerPage: 10, sortBy: 'created_at', descending: true }"
        :no-data-label="t('backup.noData')"
      >
        <template #body-cell-created_at="props">
          <q-td :props="props">
            <div class="text-weight-medium">{{ formatDateTime(props.row.created_at) }}</div>
            <div class="text-caption text-grey-7 ellipsis" style="max-width: 280px">{{ props.row.filename }}</div>
          </q-td>
        </template>
        <template #body-cell-label="props">
          <q-td :props="props">
            <span class="app-tag" :class="LABEL_TAGS[props.row.label] ?? ''">{{ labelText(props.row) }}</span>
          </q-td>
        </template>
        <template #body-cell-parts="props">
          <q-td :props="props">
            <div class="row items-center gap-xs no-wrap">
              <q-icon name="database" size="18px"><q-tooltip>{{ t('backup.database') }}</q-tooltip></q-icon>
              <q-icon v-for="p in props.row.parts" :key="p" :name="PART_ICONS[p] ?? 'folder'" size="18px">
                <q-tooltip>{{ partLabel(p) }}</q-tooltip>
              </q-icon>
            </div>
          </q-td>
        </template>
        <template #body-cell-location="props">
          <q-td :props="props">
            <q-icon :name="props.row.location === 'external' ? 'lan' : 'dns'" size="18px" class="q-mr-xs" />
            {{ props.row.location === 'external' ? t('backup.locationExternal') : t('backup.locationServer') }}
          </q-td>
        </template>
        <template #body-cell-size_bytes="props">
          <q-td :props="props">{{ formatSize(props.row.size_bytes) }}</q-td>
        </template>
        <template #body-cell-actions="props">
          <q-td :props="props">
            <div class="row no-wrap justify-end">
              <q-btn flat round dense icon="settings_backup_restore" color="negative" :disable="!props.row.valid" :aria-label="t('backup.restore')" @click="askRestore(props.row)">
                <q-tooltip>{{ t('backup.restore') }}</q-tooltip>
              </q-btn>
              <q-btn flat round dense icon="download" color="grey-7" :aria-label="t('backup.download')" @click="download(props.row)">
                <q-tooltip>{{ t('backup.download') }}</q-tooltip>
              </q-btn>
              <q-btn flat round dense icon="delete" color="grey-7" :aria-label="t('actions.delete')" @click="askDelete(props.row)">
                <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
              </q-btn>
            </div>
          </q-td>
        </template>
      </AppTable>
    </q-card>

    <!-- Sauvegarde / export avec un autre contenu -->
    <FormDialog
      v-model="customDialog"
      :icon="customMode === 'export' ? 'download' : 'backup'"
      :title="customMode === 'export' ? t('backup.customExport') : t('backup.saveNow')"
      :subtitle="t('backup.customSubtitle')"
      width="440px"
      :submit-label="customMode === 'export' ? t('backup.download') : t('backup.saveShort')"
      :loading="creating"
      @submit="runCustom"
    >
      <div v-for="part in parts" :key="part">
        <q-checkbox v-model="customParts" :val="part" :label="partLabel(part)" />
      </div>
      <q-option-group
        v-if="customMode === 'create'"
        v-model="customLocation"
        :options="[
          { label: t('backup.onServer'), value: 'local' },
          { label: t('backup.externalStorage'), value: 'external', disable: !settings?.external_ok },
        ]"
      />
    </FormDialog>

    <!-- Redémarrage après restauration -->
    <q-dialog v-model="restarting" persistent>
      <q-card class="q-pa-lg text-center" style="width: 340px">
        <q-spinner color="primary" size="3em" />
        <div class="text-subtitle1 text-weight-bold q-mt-md">{{ t('backup.restoring') }}</div>
        <div class="text-body2 text-grey-7">{{ t('backup.restartHint') }}</div>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import AppTable from 'src/components/AppTable.vue';
import FormDialog from 'src/components/FormDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import { useBackupStore } from 'src/stores/backupStore';
import {
  BACKUP_PARTS,
  type BackupInfo,
  type BackupLocation,
  type BackupPart,
  type BackupSettings,
} from 'src/types/backup';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatSize } from 'src/utils/documentFiles';
import { formatDateTime } from 'src/utils/format';
import { intlLocale } from 'src/i18n/instance';
import { usePermissions } from 'src/composables/usePermissions';

const $q = useQuasar();
const i18n = useI18n();
const { t } = i18n;
const backupStore = useBackupStore();

const frequencies = computed(() => [
  { label: t('backup.daily'), value: 'daily' },
  { label: t('backup.weekly'), value: 'weekly' },
]);
const hours = computed(() => Array.from({ length: 24 }, (_, h) => ({ label: t('backup.hourValue', { h: String(h).padStart(2, '0') }), value: h })));
// 0 = lundi (côté API) ; le 1er janvier 2024 était un lundi
const weekdays = computed(() =>
  Array.from({ length: 7 }, (_, value) => {
    const name = new Date(2024, 0, 1 + value).toLocaleDateString(intlLocale(), { weekday: 'long' });
    return { label: name.charAt(0).toUpperCase() + name.slice(1), value };
  }),
);
const PART_ICONS: Record<string, string> = { photos: 'photo_library', icp: 'science', documents: 'folder_shared', certificates: 'description' };
const LABEL_TAGS: Record<string, string> = { auto: 'app-tag--teal', imported: 'app-tag--warn', before_restore: 'app-tag--danger' };
const NFS_EXAMPLE = '/backups-nfs'; // i18n-ignore : exemple de chemin
const can = usePermissions();
const RESTORABLE: BackupPart[] = ['photos', 'icp', 'documents'];
// Certificats de cession : partie pro (bourse), proposés seulement avec la licence
const parts = computed(() => BACKUP_PARTS.filter((p) => p !== 'certificates' || can.bourse));

const columns = computed(() => [
  { name: 'created_at', label: t('backup.columns.date'), field: 'created_at', align: 'left' as const, sortable: true },
  { name: 'label', label: t('backup.columns.type'), field: 'label_text', align: 'left' as const, sortable: true },
  { name: 'parts', label: t('backup.columns.content'), field: 'parts', align: 'left' as const },
  { name: 'location', label: t('backup.columns.location'), field: 'location', align: 'left' as const, sortable: true },
  { name: 'size_bytes', label: t('backup.columns.size'), field: 'size_bytes', align: 'right' as const, sortable: true },
  { name: 'actions', label: '', field: 'actions', align: 'right' as const },
]);

const filePicker = ref<HTMLInputElement | null>(null);
const settings = computed(() => backupStore.settings);
const form = ref<BackupSettings>({
  enabled: false,
  frequency: 'daily',
  hour: 3,
  weekday: 0,
  keep_count: 7,
  include_photos: true,
  include_icp: true,
  include_documents: true,
  include_certificates: true,
  destination: 'local',
  external_path: null,
});
const saving = ref(false);
const testing = ref(false);
const creating = ref(false);
const restarting = ref(false);
const customDialog = ref(false);
const customMode = ref<'create' | 'export'>('create');
const customParts = ref<BackupPart[]>([]);
const customLocation = ref<BackupLocation>('local');

function partLabel(part: string) {
  return BACKUP_PARTS.includes(part as BackupPart) ? t(`backup.parts.${part}.label`) : part;
}

// Type de sauvegarde : libellé traduit, sinon celui de l'API
function labelText(b: BackupInfo) {
  return i18n.te(`backup.labels.${b.label}`) ? t(`backup.labels.${b.label}`) : b.label_text;
}

function where(b: BackupInfo) {
  return b.location === 'external' ? t('backup.whereExternal') : t('backup.whereServer');
}

function fromSettings(s: BackupSettings) {
  form.value = { ...s, external_path: s.external_path ?? null };
}

async function load() {
  try {
    const [s] = await Promise.all([backupStore.fetchSettings(), backupStore.fetchBackups()]);
    fromSettings(s);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.loadFailed')) });
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    fromSettings(await backupStore.saveSettings({ ...form.value, external_path: form.value.external_path?.trim() || null }));
    await backupStore.fetchBackups();
    $q.notify({ type: 'positive', message: t('backup.notify.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

async function testDestination() {
  if (!form.value.external_path) return;
  testing.value = true;
  try {
    const result = await backupStore.testDestination(form.value.external_path.trim());
    $q.notify({ type: 'positive', message: result.message });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.unreachable')), timeout: 8000 });
  } finally {
    testing.value = false;
  }
}

async function createNow(parts?: BackupPart[], location?: BackupLocation) {
  creating.value = true;
  try {
    const b = await backupStore.createBackup(parts, location);
    $q.notify({ type: 'positive', message: t('backup.notify.created', { size: formatSize(b.size_bytes), where: where(b) }) });
    return true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.createFailed')), timeout: 8000 });
    return false;
  } finally {
    creating.value = false;
  }
}

function openCustom(mode: 'create' | 'export') {
  customMode.value = mode;
  customParts.value = parts.value.filter((p) => form.value[`include_${p}`]);
  customLocation.value = settings.value?.destination === 'external' && settings.value.external_ok ? 'external' : 'local';
  customDialog.value = true;
}

async function runCustom() {
  if (customMode.value === 'create') {
    if (await createNow(customParts.value, customLocation.value)) customDialog.value = false;
    return;
  }
  creating.value = true;
  try {
    await backupStore.exportBackup(customParts.value);
    customDialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.exportFailed')) });
  } finally {
    creating.value = false;
  }
}

async function download(b: BackupInfo) {
  try {
    await backupStore.downloadBackup(b);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.downloadFailed')) });
  }
}

function askDelete(b: BackupInfo) {
  $q.dialog({
    title: t('backup.deleteTitle'),
    message: t('backup.deleteMessage', { date: formatDateTime(b.created_at), where: where(b) }),
    cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
    ok: { label: t('actions.delete'), color: 'negative', flat: true },
  }).onOk(() => {
    void backupStore.deleteBackup(b).catch((err) => {
      $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.deleteFailed')) });
    });
  });
}

function askRestore(b: BackupInfo) {
  const replaced = [t('backup.restoreDatabase'), ...b.parts.filter((p) => RESTORABLE.includes(p as BackupPart)).map((p) => partLabel(p).toLowerCase())];
  const kept = RESTORABLE.filter((p) => !b.parts.includes(p)).map((p) => partLabel(p).toLowerCase());
  $q.dialog({
    title: t('backup.restoreTitle'),
    message:
      t('backup.restoreReplaced', { date: formatDateTime(b.created_at), list: replaced.join(', ') }) +
      (kept.length ? t('backup.restoreKept', { list: kept.join(', ') }) : '') +
      t('backup.restoreEnd'),
    cancel: { label: t('common.cancel'), flat: true, color: 'grey-8' },
    ok: { label: t('backup.restore'), color: 'negative', unelevated: true },
    persistent: true,
  }).onOk(() => void restore(b));
}

async function restore(b: BackupInfo) {
  try {
    const message = await backupStore.restoreBackup(b);
    $q.notify({ type: 'positive', message, timeout: 6000 });
    restarting.value = true;
    await waitForRestart();
    window.location.reload();
  } catch (err) {
    restarting.value = false;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.restoreFailed')), timeout: 8000 });
  }
}

// Attend le redémarrage du service (arrêt puis réponse de /health)
async function waitForRestart() {
  await new Promise((resolve) => setTimeout(resolve, 3000));
  for (let i = 0; i < 60; i += 1) {
    try {
      await axios.get('/health', { timeout: 2000 });
      return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  }
}

function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) return;
  void (async () => {
    try {
      const b = await backupStore.importBackup(file);
      $q.notify({
        type: 'positive',
        message: t('backup.notify.imported', { name: file.name, size: formatSize(b.size_bytes) }),
        actions: [{ label: t('backup.restore'), color: 'white', handler: () => askRestore(b) }],
        timeout: 10000,
      });
    } catch (err) {
      $q.notify({ type: 'negative', message: apiErrorMessage(err, t('backup.notify.importFailed')), timeout: 8000 });
    }
  })();
}

onMounted(load);
</script>

<style scoped>
.hidden {
  display: none;
}

.section-off {
  opacity: 0.55;
}

.part-caption {
  margin: -6px 0 4px 40px;
}
</style>
