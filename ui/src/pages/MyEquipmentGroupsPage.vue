<template>
  <div>
    <PageHeader section :title="t('equipments.groups.title')" :subtitle="t('equipments.groups.subtitle')">
      <template #actions>
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('equipments.groups.create')" :disable="aquariumEquipments.length === 0" @click="openAddDialog" />
      </template>
    </PageHeader>

    <EmptyState
      v-if="aquariumEquipments.length === 0"
      icon="workspaces"
      :title="t('equipments.groups.noEquipmentTitle')"
      :message="t('equipments.groups.noEquipmentMessage')"
    />

    <EmptyState
      v-else-if="aquariumGroups.length === 0"
      icon="workspaces"
      :title="t('equipments.groups.emptyTitle')"
      :message="t('equipments.groups.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('equipments.groups.create')" @click="openAddDialog" />
    </EmptyState>

    <div v-else class="row q-col-gutter-md">
      <div v-for="group in aquariumGroups" :key="group.id" class="col-12 col-md-6 col-lg-4">
        <q-card flat bordered class="full-height column no-wrap">
          <q-card-section class="row items-center justify-between no-wrap q-pb-sm">
            <div class="row items-center no-wrap">
              <q-avatar size="40px" color="blue-1" text-color="primary" icon="workspaces" class="q-mr-sm" />
              <div>
                <div class="text-subtitle1 text-weight-bold">{{ group.name }}</div>
                <div class="text-caption text-grey-7">
                  {{ t('equipments.groups.count', group.equipments.length) }}
                </div>
              </div>
            </div>
            <div class="row no-wrap">
              <q-btn v-if="can.edit" flat round dense icon="edit" color="grey-7" @click="openEditDialog(group)">
                <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
              </q-btn>
              <q-btn v-if="can.manage" flat round dense icon="delete" color="negative" @click="confirmDelete(group)">
                <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
              </q-btn>
            </div>
          </q-card-section>

          <q-separator />

          <q-card-section class="col q-py-sm">
            <div v-if="group.equipments.length === 0" class="text-grey-6 text-center q-py-md">{{ t('equipments.groups.emptyGroup') }}</div>
            <q-list v-else dense>
              <q-item v-for="eq in group.equipments" :key="eq.id" class="q-px-none">
                <q-item-section avatar style="min-width: 32px">
                  <q-icon name="power" :color="liveStatus(eq) === 'ON' ? 'positive' : 'grey-5'" />
                </q-item-section>
                <q-item-section>
                  <q-item-label class="text-weight-medium">{{ eq.name }}</q-item-label>
                  <q-item-label v-if="!isInAquarium(eq.id)" caption>{{ t('equipments.groups.otherAquarium') }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <div class="row no-wrap gap-xs">
                    <q-badge outline :color="liveMode(eq) === 'AUTO' ? 'primary' : 'orange-8'" :label="liveMode(eq) === 'AUTO' ? t('equipments.auto') : t('equipments.manual')" />
                    <q-badge :color="liveStatus(eq) === 'ON' ? 'positive' : 'grey-6'" :label="liveStatus(eq) === 'ON' ? t('equipments.state.on') : t('equipments.state.off')" />
                  </div>
                </q-item-section>
              </q-item>
            </q-list>
          </q-card-section>

          <q-separator />

          <q-card-section class="q-pt-sm">
            <div class="row q-col-gutter-sm">
              <div class="col-6">
                <q-btn v-if="can.edit" outline dense class="full-width" color="primary" icon="settings_suggest" :label="t('equipments.groups.allAuto')" @click="groupMode(group, EquipmentMode.AUTO)" />
              </div>
              <div class="col-6">
                <q-btn v-if="can.edit" outline dense class="full-width" color="orange-8" icon="pan_tool" :label="t('equipments.groups.allManual')" @click="groupMode(group, EquipmentMode.MANUAL)" />
              </div>
              <div class="col-6">
                <q-btn v-if="can.edit" outline dense class="full-width" color="negative" icon="power_off" :label="t('equipments.groups.allOff')" @click="groupAction(group, 'OFF')" />
              </div>
              <div class="col-6">
                <q-btn v-if="can.edit" unelevated dense class="full-width" color="positive" icon="power" :label="t('equipments.groups.allOn')" @click="groupAction(group, 'ON')" />
              </div>
            </div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <!-- Création / édition -->
    <FormDialog
      v-model="dialog"
      icon="workspaces"
      :title="isEdit ? t('equipments.groups.editTitle') : t('equipments.groups.newTitle')"
      :subtitle="t('equipments.groups.formSubtitle')"
      width="480px"
      :loading="saving"
      @submit="saveGroup"
    >
      <q-input v-model="formName" :label="t('equipments.groups.name')" outlined dense autofocus />
      <div>
        <div class="text-caption text-grey-7 q-mb-xs">{{ t('equipments.groups.equipments') }}</div>
        <q-card flat bordered class="q-pa-sm" style="max-height: 280px; overflow-y: auto">
          <q-option-group v-model="formEquipmentIds" type="checkbox" :options="equipmentOptions" />
        </q-card>
      </div>
    </FormDialog>
  </div>
</template>

<script setup lang="ts">
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useEquipmentGroupStore } from 'src/stores/equipmentGroupStore';
import { useEquipmentStore } from 'src/stores/equipmentStore';
import { useWebSocketStore } from 'src/stores/websocket';
import type { EquipmentGroup, EquipmentInGroup } from 'src/types/equipment_group';
import { EquipmentMode } from 'src/types/equipment';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import FormDialog from 'src/components/FormDialog.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';

const props = defineProps({ aquaId: { type: Number, required: true } });

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const groupStore = useEquipmentGroupStore();
const equipmentStore = useEquipmentStore();
const wsStore = useWebSocketStore();

const dialog = ref(false);
const isEdit = ref(false);
const saving = ref(false);
const editingGroupId = ref<number | null>(null);
const formName = ref('');
const formEquipmentIds = ref<number[]>([]);

const aquariumEquipments = computed(() => equipmentStore.getByAquariumId(props.aquaId));
const aquariumEquipmentIds = computed(() => new Set(aquariumEquipments.value.map((e) => e.id)));

function isInAquarium(equipmentId: number): boolean {
  return aquariumEquipmentIds.value.has(equipmentId);
}

// Les groupes sont communs à tous les aquariums : on montre ceux qui pilotent
// au moins un équipement de cet aquarium, plus les groupes encore vides.
const aquariumGroups = computed(() =>
  groupStore.groups.filter((g) => g.equipments.length === 0 || g.equipments.some((e) => isInAquarium(e.id))),
);

// Équipements de l'aquarium, plus ceux d'autres aquariums déjà dans le groupe édité
const equipmentOptions = computed(() => {
  const selected = new Set(formEquipmentIds.value);
  return equipmentStore.equipments
    .filter((e) => isInAquarium(e.id) || selected.has(e.id))
    .map((e) => ({ label: isInAquarium(e.id) ? e.name : t('equipments.groups.otherAquariumSuffix', { name: e.name }), value: e.id }));
});

function liveStatus(eq: EquipmentInGroup): 'ON' | 'OFF' {
  const live = wsStore.equipmentsState[eq.id] ?? equipmentStore.getById(eq.id)?.status ?? eq.status;
  return live === true || live === 1 || String(live).toUpperCase() === 'ON' ? 'ON' : 'OFF';
}

function liveMode(eq: EquipmentInGroup): string {
  return String(equipmentStore.getById(eq.id)?.mode ?? eq.mode ?? '').toUpperCase();
}

function openAddDialog() {
  isEdit.value = false;
  editingGroupId.value = null;
  formName.value = '';
  formEquipmentIds.value = [];
  dialog.value = true;
}

function openEditDialog(group: EquipmentGroup) {
  isEdit.value = true;
  editingGroupId.value = group.id;
  formName.value = group.name;
  formEquipmentIds.value = group.equipments.map((eq) => eq.id);
  dialog.value = true;
}

async function saveGroup() {
  if (!formName.value.trim()) {
    $q.notify({ type: 'warning', message: t('equipments.groups.nameRequired') });
    return;
  }
  saving.value = true;
  try {
    const payload = { name: formName.value.trim(), equipment_ids: formEquipmentIds.value };
    if (isEdit.value && editingGroupId.value !== null) {
      await groupStore.update(editingGroupId.value, payload);
    } else {
      await groupStore.create(payload);
    }
    $q.notify({ type: 'positive', message: isEdit.value ? t('equipments.groups.updated') : t('equipments.groups.created') });
    dialog.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.groups.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

async function groupAction(group: EquipmentGroup, action: 'ON' | 'OFF') {
  try {
    await groupStore.control(group.id, action);
    $q.notify({
      type: 'positive',
      message: t(action === 'ON' ? 'equipments.groups.allOnDone' : 'equipments.groups.allOffDone', { name: group.name }),
    });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.groups.commandFailed')) });
  }
}

async function groupMode(group: EquipmentGroup, mode: EquipmentMode) {
  try {
    await groupStore.controlMode(group.id, mode);
    $q.notify({
      type: 'positive',
      message: t(mode === EquipmentMode.AUTO ? 'equipments.groups.autoRequested' : 'equipments.groups.manualRequested', {
        name: group.name,
      }),
    });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('equipments.notify.modeFailed')) });
  }
}

function confirmDelete(group: EquipmentGroup) {
  confirmRemove(t('equipments.groups.item', { name: group.name }), () => groupStore.remove(group.id), {
    message: t('equipments.groups.deleteMessage', { name: group.name }),
  });
}

onMounted(() => {
  void Promise.all([groupStore.fetch(), equipmentStore.fetch()]).catch(() =>
    $q.notify({ type: 'negative', message: t('equipments.groups.loadFailed') }),
  );
});
</script>
