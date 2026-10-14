<template>
  <q-page class="app-page">
    <PageHeader icon="manage_search" :title="t('audit.title')" :subtitle="t('audit.subtitle')">
      <template #actions>
        <q-btn flat round dense icon="refresh" color="grey-7" :loading="loading" :aria-label="t('audit.refresh')" @click="load(true)">
          <q-tooltip>{{ t('audit.refresh') }}</q-tooltip>
        </q-btn>
      </template>
    </PageHeader>

    <div class="row items-center gap-sm q-mb-md">
      <AppInput v-model="search" icon="search" :placeholder="t('audit.search')" clearable debounce="400" class="app-search" style="width: 280px; max-width: 100%" />
      <AppSelect v-model="username" :options="userOptions" :label="t('audit.user')" clearable style="min-width: 180px" />
      <AppSelect v-model="entityType" :options="entityOptions" :label="t('audit.entityType')" clearable style="min-width: 200px" />
    </div>

    <EmptyState
      v-if="!loading && items.length === 0"
      icon="manage_search"
      :title="t('audit.emptyTitle')"
      :message="hasFilter ? t('audit.emptyFiltered') : t('audit.emptyMessage')"
    />

    <q-card v-else flat bordered>
      <q-list separator>
        <q-item v-for="item in items" :key="item.id">
          <q-item-section avatar>
            <q-avatar size="36px" :color="meta(item).bg" :text-color="meta(item).color" :icon="meta(item).icon" />
          </q-item-section>
          <q-item-section>
            <q-item-label>
              <span class="text-weight-bold">{{ item.action }}</span>
              <span v-if="item.entity_label"> « {{ item.entity_label }} »</span>
            </q-item-label>
            <q-item-label caption>
              {{ item.username ?? t('audit.unknown') }} · {{ formatDateTime(item.created_at) }}
              <span v-if="item.client_ip"> · {{ item.client_ip }}</span>
            </q-item-label>
            <q-item-label v-if="detailsText(item)" caption class="font-mono ellipsis-2-lines">{{ detailsText(item) }}</q-item-label>
          </q-item-section>
          <q-item-section side>
            <q-badge outline :color="item.method === 'DELETE' ? 'negative' : 'grey-7'" :label="methodLabel(item.method)" />
          </q-item-section>
        </q-item>
      </q-list>
      <q-card-actions v-if="items.length < total" align="center">
        <q-btn flat color="primary" icon="expand_more" :label="t('audit.more', total - items.length)" :loading="loading" @click="load(false)" />
      </q-card-actions>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import AppInput from 'src/components/AppInput.vue';
import AppSelect from 'src/components/AppSelect.vue';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDateTime } from 'src/utils/format';

interface AuditItem {
  id: number;
  created_at: string;
  username: string | null;
  method: string;
  path: string;
  action: string;
  entity_type: string | null;
  entity_label: string | null;
  details: string | null;
  client_ip: string | null;
}

const PAGE_SIZE = 50;
const METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'];
const ENTITIES = [
  'aquarium', 'equipment', 'sensor', 'controller', 'rule', 'light', 'equipment_group', 'water_parameter',
  'task', 'inventory_item', 'fish', 'coral', 'plant', 'invertebrate', 'user', 'backup',
] as const;

const $q = useQuasar();
const { t } = useI18n();
const entityOptions = computed(() => ENTITIES.map((value) => ({ label: t(`audit.entities.${value}`), value })));

function methodLabel(method: string) {
  return METHODS.includes(method) ? t(`audit.methods.${method}`) : method;
}
const items = ref<AuditItem[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref<string | null>('');
const username = ref<string | null>(null);
const entityType = ref<string | null>(null);
const userOptions = ref<string[]>([]);

const hasFilter = computed(() => !!(search.value || username.value || entityType.value));

function meta(item: AuditItem) {
  if (item.action.startsWith('Échec')) return { icon: 'gpp_bad', color: 'negative', bg: 'red-1' }; // i18n-ignore : actions écrites par l'API
  if (item.action === 'Connexion' || item.action === 'Déconnexion') return { icon: 'login', color: 'grey-8', bg: 'grey-2' }; // i18n-ignore : actions écrites par l'API
  if (item.method === 'DELETE') return { icon: 'delete', color: 'negative', bg: 'red-1' };
  if (item.action.startsWith('Flash')) return { icon: 'system_update', color: 'orange-9', bg: 'orange-1' };
  if (item.action.startsWith('Création')) return { icon: 'add', color: 'positive', bg: 'green-1' }; // i18n-ignore : actions écrites par l'API
  if (item.method === 'POST') return { icon: 'bolt', color: 'primary', bg: 'blue-1' };
  return { icon: 'edit', color: 'primary', bg: 'blue-1' };
}

// Résumé lisible des champs envoyés (clé : valeur)
function detailsText(item: AuditItem): string {
  if (!item.details) return '';
  try {
    const data = JSON.parse(item.details) as Record<string, unknown>;
    return Object.entries(data)
      .filter(([, value]) => value !== null && value !== '' && typeof value !== 'object')
      .map(([key, value]) => `${key} : ${String(value as string | number | boolean)}`)
      .join(' · ');
  } catch {
    return '';
  }
}

async function load(reset: boolean) {
  loading.value = true;
  try {
    const { data } = await axios.get<{ total: number; items: AuditItem[] }>('/audit/', {
      params: {
        limit: PAGE_SIZE,
        offset: reset ? 0 : items.value.length,
        search: search.value || undefined,
        username: username.value || undefined,
        entity_type: entityType.value || undefined,
      },
    });
    items.value = reset ? data.items : [...items.value, ...data.items];
    total.value = data.total;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('audit.loadFailed')) });
  } finally {
    loading.value = false;
  }
}

watch([search, username, entityType], () => void load(true));

onMounted(async () => {
  await load(true);
  try {
    userOptions.value = (await axios.get<string[]>('/audit/users')).data;
  } catch {
    userOptions.value = [];
  }
});
</script>
