<!--
  Commandes groupées (VPC) entre passionnés d'un même secteur : annonces des
  départements suivis, commandes organisées ou rejointes, notifications.
  Les annonces vivent sur le hub de l'éditeur ; les contacts ne sont visibles
  que des personnes concernées.
-->
<template>
  <q-page class="app-page">
    <PageHeader :title="t('groupOrders.title')" :subtitle="t('groupOrders.subtitle')" icon="local_shipping">
      <template #actions>
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('groupOrders.organize')" @click="openForm(null)" />
      </template>
    </PageHeader>

    <q-banner v-if="unavailable" rounded class="bg-orange-1 text-orange-10 q-mb-md">
      <template #avatar><q-icon name="cloud_off" color="orange-9" /></template>
      {{ unavailable }}
    </q-banner>

    <q-card flat bordered class="q-mb-md">
      <q-card-section class="row items-center q-col-gutter-sm">
        <div class="col-12 col-md">
          <q-select
            v-model="settingsForm.departments"
            outlined
            dense
            multiple
            use-chips
            use-input
            input-debounce="0"
            emit-value
            map-options
            :options="departmentOptions"
            :max-values="10"
            :label="t('groupOrders.myDepartments')"
            :hint="t('groupOrders.myDepartmentsHint')"
            :disable="!can.edit"
            @filter="filterDepartments"
            @update:model-value="saveSettings"
          />
        </div>
        <div class="col-12 col-md-auto">
          <q-toggle v-model="settingsForm.notify" :disable="!can.edit" :label="t('groupOrders.notify')" @update:model-value="saveSettings" />
        </div>
      </q-card-section>
    </q-card>

    <q-tabs v-model="tab" dense align="left" active-color="primary" indicator-color="primary" class="text-grey-7 q-mb-md" narrow-indicator>
      <q-tab name="nearby" icon="near_me" :label="t('groupOrders.tabs.nearby')" />
      <q-tab name="mine" icon="inventory" :label="t('groupOrders.tabs.mine', { n: mine.length })" />
    </q-tabs>

    <div v-if="loading" class="text-center q-py-xl"><q-spinner color="primary" size="3em" /></div>

    <template v-else-if="tab === 'nearby'">
      <EmptyState
        v-if="!settingsForm.departments.length"
        icon="travel_explore"
        :title="t('groupOrders.chooseDepartments')"
        :message="t('groupOrders.chooseDepartmentsMessage')"
      />
      <EmptyState v-else-if="!nearby.length" icon="local_shipping" :title="t('groupOrders.emptyNearby')" :message="t('groupOrders.emptyNearbyMessage')">
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('groupOrders.organize')" @click="openForm(null)" />
      </EmptyState>
      <div v-else class="row q-col-gutter-md">
        <div v-for="order in nearby" :key="order.id" class="col-12 col-sm-6 col-lg-4">
          <GroupOrderCard :order="order" @open="openDetail(order.id)" />
        </div>
      </div>
    </template>

    <template v-else>
      <EmptyState v-if="!mine.length" icon="inventory" :title="t('groupOrders.emptyMine')" :message="t('groupOrders.emptyMineMessage')" />
      <div v-else class="row q-col-gutter-md">
        <div v-for="order in mine" :key="order.id" class="col-12 col-sm-6 col-lg-4">
          <GroupOrderCard :order="order" @open="openDetail(order.id)" />
        </div>
      </div>
    </template>

    <GroupOrderFormDialog v-model="formOpen" :order="editing" :default-department="settingsForm.departments[0] ?? null" @saved="onSaved" />
    <GroupOrderDetailDialog v-model="detailOpen" :order-id="detailId" @changed="loadAll" @edit="(o) => openForm(o)" />
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import GroupOrderCard from 'src/components/GroupOrderCard.vue';
import GroupOrderFormDialog from 'src/components/GroupOrderFormDialog.vue';
import GroupOrderDetailDialog from 'src/components/GroupOrderDetailDialog.vue';
import type { GroupOrder, GroupOrderSettings } from 'src/types/groupOrder';
import { DEPARTMENTS } from 'src/utils/departments';
import { usePermissions } from 'src/composables/usePermissions';
import { apiErrorMessage } from 'src/utils/apiError';

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();

const tab = ref<'nearby' | 'mine'>('nearby');
const loading = ref(true);
const unavailable = ref<string | null>(null);
const nearby = ref<GroupOrder[]>([]);
const mine = ref<GroupOrder[]>([]);
const settingsForm = ref<GroupOrderSettings>({ departments: [], notify: true });

const allDepartments = DEPARTMENTS.map((d) => ({ value: d.code, label: `${d.code} · ${d.name}` }));
const departmentOptions = ref(allDepartments);

function filterDepartments(value: string, update: (fn: () => void) => void) {
  update(() => {
    const q = value.trim().toLowerCase();
    departmentOptions.value = q ? allDepartments.filter((d) => d.label.toLowerCase().includes(q)) : allDepartments;
  });
}

async function loadAll() {
  try {
    const [near, own] = await Promise.all([
      axios.get<GroupOrder[]>('/group-orders/'),
      axios.get<GroupOrder[]>('/group-orders/mine'),
    ]);
    nearby.value = near.data;
    mine.value = own.data;
    unavailable.value = null;
  } catch (err) {
    unavailable.value = apiErrorMessage(err, t('groupOrders.unavailable'));
  }
}

async function saveSettings() {
  try {
    settingsForm.value = (await axios.put<GroupOrderSettings>('/group-orders/settings', settingsForm.value)).data;
    await loadAll();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('groupOrders.settingsFailed')) });
  }
}

// --- Fenêtres ---
const formOpen = ref(false);
const editing = ref<GroupOrder | null>(null);
const detailOpen = ref(false);
const detailId = ref<string | null>(null);

function openForm(order: GroupOrder | null) {
  editing.value = order;
  detailOpen.value = false;
  formOpen.value = true;
}

function openDetail(id: string) {
  detailId.value = id;
  detailOpen.value = true;
}

async function onSaved(order: GroupOrder) {
  await loadAll();
  if (!editing.value) tab.value = 'mine';
  openDetail(order.id);
}

onMounted(async () => {
  try {
    settingsForm.value = (await axios.get<GroupOrderSettings>('/group-orders/settings')).data;
  } catch {
    // réglages par défaut
  }
  await loadAll();
  loading.value = false;
});
</script>
