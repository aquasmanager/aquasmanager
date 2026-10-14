<!--
  Mode maintenance d'un aquarium (changement d'eau, nettoyage) : bandeau quand
  il est en cours, fenêtre pour choisir les équipements arrêtés et la durée.
  À la fin (bouton ou échéance), chaque équipement retrouve son mode d'avant.
-->
<template>
  <q-banner v-if="state?.active" rounded class="maintenance-banner q-mb-md">
    <template #avatar><q-icon name="construction" color="orange-9" /></template>
    <div class="text-weight-bold">{{ t('aquariums.maintenance.active') }}</div>
    <div class="text-body2">
      {{ t('aquariums.maintenance.activeDetail', { n: stoppedCount, time: formatTime(state.until) }, stoppedCount) }}
    </div>
    <template v-if="can.care" #action>
      <q-btn flat no-caps color="orange-10" icon="more_time" :label="t('aquariums.maintenance.extend')" :loading="busy" @click="extend" />
      <q-btn flat no-caps color="orange-10" icon="tune" :label="t('aquariums.maintenance.edit')" @click="emit('update:modelValue', true)" />
      <q-btn unelevated no-caps color="orange-9" icon="play_arrow" :label="t('aquariums.maintenance.finish')" :loading="busy" @click="finish" />
    </template>
  </q-banner>

  <q-dialog :model-value="modelValue" @update:model-value="(v: boolean) => emit('update:modelValue', v)" @show="onShow">
    <q-card style="width: 520px; max-width: 95vw">
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar size="40px" color="orange-1" text-color="orange-9" icon="construction" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ t('aquariums.maintenance.title') }}</div>
          <div class="text-body2 text-grey-7">{{ t('aquariums.maintenance.help') }}</div>
        </div>
        <q-btn flat round dense icon="close" color="grey-7" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>

      <q-card-section v-if="!state" class="text-center q-py-lg"><q-spinner color="primary" size="2em" /></q-card-section>

      <q-card-section v-else-if="!state.equipments.length" class="text-grey-7">
        {{ t('aquariums.maintenance.noEquipment') }}
      </q-card-section>

      <template v-else>
        <q-card-section class="q-py-none">
          <div class="row items-center justify-between q-mb-xs">
            <div class="text-subtitle2 text-weight-bold">{{ t('aquariums.maintenance.equipments') }}</div>
            <div>
              <q-btn flat dense no-caps size="sm" color="primary" :label="t('aquariums.maintenance.all')" @click="selected = state.equipments.map((e) => e.id)" />
              <q-btn flat dense no-caps size="sm" color="grey-7" :label="t('aquariums.maintenance.none')" @click="selected = []" />
            </div>
          </div>
          <q-list dense>
            <q-item v-for="eq in state.equipments" :key="eq.id" tag="label" class="q-px-none">
              <q-item-section side><q-checkbox v-model="selected" :val="eq.id" dense /></q-item-section>
              <q-item-section>
                <q-item-label>{{ eq.name }}</q-item-label>
                <q-item-label caption>{{ t(`equipments.categories.${eq.category}`) }}</q-item-label>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>

        <q-card-section>
          <div class="text-subtitle2 text-weight-bold q-mb-xs">
            {{ state.active ? t('aquariums.maintenance.durationFromNow') : t('aquariums.maintenance.duration') }}
          </div>
          <!-- Grille : 6 durées sur une ligne ne tenaient pas sur téléphone (« 15 / min ») -->
          <div class="row q-col-gutter-xs">
            <div v-for="d in durationOptions" :key="d.value" class="col-4 col-sm-2">
              <q-btn
                no-caps
                unelevated
                class="full-width"
                :color="minutes === d.value ? 'primary' : 'grey-2'"
                :text-color="minutes === d.value ? 'white' : 'grey-9'"
                :label="d.label"
                @click="minutes = d.value"
              />
            </div>
          </div>
          <div class="text-caption text-grey-7 q-mt-sm">{{ t('aquariums.maintenance.resumeAt', { time: formatTime(resumeAt) }) }}</div>
        </q-card-section>

        <q-card-actions align="right" class="q-px-md q-pb-md">
          <q-btn v-if="state.active" flat no-caps color="primary" icon="play_arrow" :label="t('aquariums.maintenance.finish')" :loading="busy" @click="finish" />
          <q-btn
            unelevated
            no-caps
            color="orange-9"
            icon="pause_circle"
            :label="state.active ? t('aquariums.maintenance.apply') : t('aquariums.maintenance.start', { n: selected.length }, selected.length)"
            :disable="!selected.length || !can.care"
            :loading="busy"
            @click="start"
          />
        </q-card-actions>
      </template>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import { usePermissions } from 'src/composables/usePermissions';
import { useAquariumStore } from 'src/stores/aquariumStore';
import { apiErrorMessage } from 'src/utils/apiError';
import { intlLocale } from 'src/i18n/instance';

interface MaintenanceState {
  active: boolean;
  started_at: string | null;
  until: string | null;
  equipment_ids: number[];
  equipments: { id: number; name: string; category: string; mode: string; status: string }[];
}

const props = defineProps<{ aquariumId: number; modelValue: boolean }>();
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const aquariumStore = useAquariumStore();

const state = ref<MaintenanceState | null>(null);
const selected = ref<number[]>([]);
const minutes = ref(60);
const busy = ref(false);
const now = ref(Date.now());

const durationOptions = [15, 30, 60, 120, 240, 480].map((m) => ({
  value: m,
  label: m < 60 ? `${m} min` : `${m / 60} h`,
}));

const stoppedCount = computed(() => state.value?.equipment_ids.length ?? 0);
const resumeAt = computed(() => new Date(now.value + minutes.value * 60000).toISOString());

function formatTime(value: string | null | undefined): string {
  if (!value) return '';
  return new Date(value).toLocaleTimeString(intlLocale(), { hour: '2-digit', minute: '2-digit' });
}

async function load() {
  try {
    state.value = (await axios.get<MaintenanceState>(`/aquariums/${props.aquariumId}/maintenance`)).data;
  } catch {
    state.value = null;
  }
}

function applyState(data: MaintenanceState) {
  state.value = data;
  // Badge « Maintenance » des listes d'aquariums
  void aquariumStore.fetch().catch(() => undefined);
}

async function onShow() {
  now.value = Date.now();
  await load();
  if (state.value) selected.value = [...state.value.equipment_ids];
}

async function post(ids: number[], duration: number) {
  busy.value = true;
  try {
    const { data } = await axios.post<MaintenanceState>(`/aquariums/${props.aquariumId}/maintenance`, {
      equipment_ids: ids,
      minutes: duration,
    });
    applyState(data);
    return true;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('aquariums.maintenance.failed')) });
    return false;
  } finally {
    busy.value = false;
  }
}

async function start() {
  if (await post(selected.value, minutes.value)) {
    emit('update:modelValue', false);
    $q.notify({ type: 'warning', icon: 'construction', message: t('aquariums.maintenance.started', { time: formatTime(state.value?.until) }) });
  }
}

// Prolonger de 30 min à partir de l'échéance prévue
async function extend() {
  if (!state.value?.until) return;
  const remaining = Math.max(0, Math.round((new Date(state.value.until).getTime() - Date.now()) / 60000));
  await post(state.value.equipment_ids, Math.min(remaining + 30, 480));
}

async function finish() {
  busy.value = true;
  try {
    applyState((await axios.delete<MaintenanceState>(`/aquariums/${props.aquariumId}/maintenance`)).data);
    emit('update:modelValue', false);
    $q.notify({ type: 'positive', message: t('aquariums.maintenance.finished') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('aquariums.maintenance.failed')) });
  } finally {
    busy.value = false;
  }
}

// Échéance : le serveur remet les équipements ; le bandeau se met à jour
let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  void load();
  timer = setInterval(() => {
    now.value = Date.now();
    if (state.value?.active && state.value.until && new Date(state.value.until).getTime() <= Date.now()) void load();
  }, 30000);
});
onBeforeUnmount(() => clearInterval(timer));
watch(() => props.aquariumId, () => void load());
</script>

<style scoped>
.maintenance-banner {
  background: #fff3e0;
  color: #5d3a00;
}

.body--dark .maintenance-banner {
  background: rgba(255, 152, 0, 0.16);
  color: #ffcc80;
}
</style>
