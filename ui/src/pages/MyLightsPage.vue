<template>
  <div>
    <PageHeader section :title="t('lights.title')" :subtitle="t('lights.subtitle')">
      <template #actions>
        <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('lights.add')" :disable="!hasRtcController" @click="openLightDialog(null)">
          <q-tooltip v-if="hasController && !hasRtcController">{{ t('lights.rtcFirst') }}</q-tooltip>
        </q-btn>
      </template>
    </PageHeader>

    <EmptyState
      v-if="!hasController"
      icon="memory"
      :title="t('equipments.noControllerTitle')"
      :message="t('lights.noControllerMessage')"
    >
      <q-btn v-if="can.manage" unelevated color="primary" icon="memory" :label="t('equipments.addController')" to="/controllers" />
    </EmptyState>

    <EmptyState
      v-else-if="!hasRtcController && store.lights.length === 0"
      icon="schedule"
      :title="t('lights.rtcTitle')"
      :message="t('lights.rtcMessage')"
    >
      <q-btn v-if="can.manage" unelevated color="primary" icon="memory" :label="t('lights.goControllers')" to="/controllers" />
    </EmptyState>

    <EmptyState
      v-else-if="!store.loading && store.lights.length === 0"
      icon="lightbulb"
      :title="t('lights.emptyTitle')"
      :message="t('lights.emptyMessage')"
    >
      <q-btn v-if="can.edit" unelevated color="primary" icon="add" :label="t('lights.add')" @click="openLightDialog(null)" />
    </EmptyState>

    <div class="column q-gutter-md">
      <q-card v-for="light in store.lights" :key="light.id" flat bordered class="light-card overflow-hidden">
        <!-- En-tête -->
        <q-card-section class="row items-center q-col-gutter-md">
          <div class="col-auto">
            <div class="preview" :style="previewStyle(light)">
              <q-tooltip>{{ t('lights.currentHue') }}</q-tooltip>
            </div>
          </div>
          <div class="col">
            <div class="text-subtitle1 text-weight-bold">{{ light.name }}</div>
            <div class="row items-center q-gutter-xs text-caption text-grey-7">
              <span>{{ controllerName(light) }}</span>
              <q-badge :color="isOnline(light) ? 'positive' : 'grey-5'" :label="isOnline(light) ? t('lights.online') : t('lights.offline')" />
              <q-badge v-if="isDemo(light)" color="orange" :label="t('lights.demoAt', { time: formatMinute(currentMinute(light)) })" />
              <q-badge v-else-if="isLive(light)" color="red-6" :label="t('lights.live')" />
              <q-badge v-if="light.acclimation_percent != null" color="purple" :label="t('lights.acclimation', { n: light.acclimation_percent })" />
              <q-badge v-if="light.moonlight.length" color="indigo" :label="t('lights.moonlight', { list: moonlightLabel(light) })" />
              <q-badge v-if="controllerDirty(light)" color="orange-8" :label="t('lights.toFlash')" />
            </div>
          </div>
          <div class="col-12 col-md-auto row q-gutter-sm justify-end">
            <q-btn outline color="primary" icon="timeline" :label="t('lights.schedule')" :disable="light.channels.length === 0" @click="openEditor(light)" />
            <q-btn v-if="can.edit && !isDemo(light)" outline color="orange-8" icon="play_circle" :label="t('lights.demo')" :disable="light.channels.length === 0">
              <q-menu>
                <q-list dense style="min-width: 190px">
                  <q-item-label header>{{ t('lights.fastDay') }}</q-item-label>
                  <q-item v-for="d in demoDurations" :key="d.value" clickable v-close-popup @click="startDemo(light, d.value)">
                    <q-item-section>{{ d.label }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            <q-btn v-else-if="can.edit" unelevated color="orange-8" icon="stop_circle" :label="t('lights.stopDemo')" @click="stopDemo(light)" />
            <q-btn v-if="can.edit" flat round dense icon="more_vert" color="grey-7">
              <q-menu auto-close>
                <q-list style="min-width: 200px">
                  <q-item clickable @click="setAllAuto(light)">
                    <q-item-section avatar><q-icon name="schedule" /></q-item-section>
                    <q-item-section>{{ t('lights.allAuto') }}</q-item-section>
                  </q-item>
                  <q-item clickable @click="openChannelDialog(light, null)">
                    <q-item-section avatar><q-icon name="add" /></q-item-section>
                    <q-item-section>{{ t('lights.addChannel') }}</q-item-section>
                  </q-item>
                  <q-item clickable @click="openLightDialog(light)">
                    <q-item-section avatar><q-icon name="tune" /></q-item-section>
                    <q-item-section>{{ t('lights.lampSettings') }}</q-item-section>
                  </q-item>
                  <q-separator />
                  <q-item v-if="can.manage" clickable class="text-negative" @click="removeLight(light)">
                    <q-item-section avatar><q-icon name="delete" color="negative" /></q-item-section>
                    <q-item-section>{{ t('lights.deleteLamp') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
          </div>
        </q-card-section>

        <template v-if="light.channels.length > 0">
          <q-card-section class="q-pt-none">
            <LightScheduleChart
              :channels="light.channels"
              :now-minute="isDemo(light) ? null : nowMinuteValue"
              :playhead="isDemo(light) ? currentMinute(light) : null"
              :height="190"
            />
          </q-card-section>

          <q-list separator class="q-pb-sm">
            <q-item v-for="ch in light.channels" :key="ch.id" class="channel-item">
              <q-item-section avatar>
                <span
                  class="channel-dot"
                  :class="{ 'channel-dot--light': isVeryLight(ch.color) }"
                  :style="{ background: ch.color, boxShadow: `0 0 ${levels(light)[ch.id]! / 8}px ${visibleColor(ch.color, $q.dark.isActive)}` }"
                />
              </q-item-section>
              <q-item-section style="min-width: 120px; max-width: 180px">
                <q-item-label class="text-weight-medium">{{ ch.name }}</q-item-label>
                <q-item-label caption>{{ t('lights.channelInfo', { pin: ch.pin_number, max: ch.max_intensity }) }}</q-item-label>
              </q-item-section>
              <q-item-section>
                <div class="row items-center no-wrap q-gutter-x-sm">
                  <q-linear-progress
                    :value="(levels(light)[ch.id] ?? 0) / 100"
                    rounded
                    size="10px"
                    track-color="grey-3"
                    :style="{ color: visibleColor(ch.color, $q.dark.isActive) }"
                    class="col"
                  />
                  <span class="text-weight-bold level-value">{{ Math.round(levels(light)[ch.id] ?? 0) }} %</span>
                </div>
                <q-slider
                  v-if="ch.mode === 'MANUAL' && !isDemo(light)"
                  :disable="!can.edit"
                  :model-value="manualDraft[ch.id] ?? ch.current_intensity"
                  :min="0"
                  :max="ch.max_intensity"
                  label
                  class="q-mt-xs"
                  @update:model-value="(v: number | null) => (manualDraft[ch.id] = v ?? 0)"
                  @change="(v: number) => setManual(light, ch.id, v)"
                />
              </q-item-section>
              <q-item-section side class="channel-item__controls">
                <div class="row items-center no-wrap q-gutter-xs">
                  <q-btn-toggle
                    :model-value="ch.mode"
                    dense
                    unelevated
                    toggle-color="primary"
                    color="grey-2"
                    text-color="grey-8"
                    :disable="!can.edit || isDemo(light)"
                    :options="modeOptions"
                    @update:model-value="(mode: ChannelMode) => setMode(light, ch.id, mode)"
                  />
                  <q-btn v-if="can.edit" flat round dense icon="edit" size="sm" color="grey-7" @click="openChannelDialog(light, ch)" />
                  <q-btn v-if="can.edit" flat round dense icon="delete" size="sm" color="negative" @click="removeChannel(ch)" />
                </div>
              </q-item-section>
            </q-item>
          </q-list>
        </template>
        <q-card-section v-else class="text-center text-grey-6">
          {{ t('lights.noChannel') }}
          <q-btn v-if="can.edit" flat color="primary" icon="add" :label="t('lights.addChannel')" @click="openChannelDialog(light, null)" />
        </q-card-section>
      </q-card>
    </div>

    <LightDialog v-model="lightDialog" :light="editedLight" :aqua-id="aquaId" />
    <LightChannelDialog v-model="channelDialog" :light="channelLight" :channel="editedChannel" />
    <LightScheduleEditor v-model="editorDialog" :light="editorLight" />
  </div>
</template>

<script setup lang="ts">
import { usePermissions } from 'src/composables/usePermissions';
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import LightChannelDialog from 'src/components/LightChannelDialog.vue';
import LightDialog from 'src/components/LightDialog.vue';
import PageHeader from 'src/components/PageHeader.vue';
import EmptyState from 'src/components/EmptyState.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import LightScheduleChart from 'src/components/LightScheduleChart.vue';
import LightScheduleEditor from 'src/components/LightScheduleEditor.vue';
import { useControllerStore } from 'src/stores/controllerStore';
import { useLightStore } from 'src/stores/lightStore';
import { useWebSocketStore } from 'src/stores/websocket';
import type { ChannelMode, Light, LightChannel } from 'src/types/light';
import { channelTargetLevel, formatMinute, interpolate, isVeryLight, mixedColor, nowMinute, visibleColor, withThreshold } from 'src/utils/lightSchedule';

const props = defineProps<{ aquaId: number }>();

const { t } = useI18n();
const modeOptions = computed(() => [
  { label: t('lights.modes.auto'), value: 'AUTO' },
  { label: t('lights.modes.manual'), value: 'MANUAL' },
  { label: t('lights.modes.off'), value: 'OFF' },
]);
const demoDurations = computed(() => [
  { label: t('lights.durations.s30'), value: 30 },
  { label: t('lights.durations.m1'), value: 60 },
  { label: t('lights.durations.m2'), value: 120 },
  { label: t('lights.durations.m5'), value: 300 },
]);
const LIVE_FRESHNESS_MS = 30_000;

const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const store = useLightStore();
const controllerStore = useControllerStore();
const wsStore = useWebSocketStore();

const nowMinuteValue = ref(nowMinute());
const clock = ref(Date.now());
const manualDraft = ref<Record<number, number>>({});
// Démo simulée dans le navigateur (aperçu même si la lampe est hors ligne)
const localDemos = ref<Record<number, { start: number; durationMs: number }>>({});
let timer: ReturnType<typeof setInterval> | undefined;

const hasController = computed(() => controllerStore.controllers.length > 0);
const hasRtcController = computed(() => controllerStore.controllers.some((c) => c.rtc_model));

function liveState(light: Light) {
  const state = wsStore.lightsState[light.id];
  return state && clock.value - state.at < LIVE_FRESHNESS_MS ? state : null;
}

function localDemoMinute(light: Light): number | null {
  const demo = localDemos.value[light.id];
  if (!demo) return null;
  const elapsed = clock.value - demo.start;
  return elapsed < demo.durationMs ? (elapsed / demo.durationMs) * 1440 : null;
}

function isDemo(light: Light): boolean {
  return !!liveState(light)?.demo || localDemoMinute(light) != null;
}

function isLive(light: Light): boolean {
  return liveState(light) != null;
}

function currentMinute(light: Light): number {
  const live = liveState(light);
  if (live?.demo && live.minute != null) return live.minute;
  return localDemoMinute(light) ?? nowMinuteValue.value;
}

// Intensités affichées : réelles (ESP) si disponibles, sinon calculées depuis le programme
function levels(light: Light): Record<number, number> {
  const live = liveState(light);
  const result: Record<number, number> = {};
  const demoMinute = isDemo(light) ? currentMinute(light) : null;
  for (const ch of light.channels) {
    if (live && live.channels[ch.id] != null && (demoMinute == null || live.demo)) {
      result[ch.id] = live.channels[ch.id]!;
    } else if (demoMinute != null) {
      result[ch.id] = withThreshold(Math.min(interpolate(ch.schedule, demoMinute), ch.max_intensity), ch);
    } else {
      const factor = (light.acclimation_percent ?? 100) / 100;
      const target = channelTargetLevel(ch, nowMinuteValue.value);
      result[ch.id] = ch.mode === 'AUTO' ? withThreshold(Math.min(target * factor, ch.max_intensity), ch) : target;
    }
  }
  return result;
}

// « Driver 30 %, Bleu 5 % »
function moonlightLabel(light: Light): string {
  return light.channels
    .filter((ch) => ch.moonlight_intensity > 0)
    .map((ch) => `${ch.name} ${ch.moonlight_intensity} %`)
    .join(', ');
}

function previewStyle(light: Light) {
  const { color, brightness } = mixedColor(light.channels, levels(light));
  return {
    background: `radial-gradient(circle at 50% 40%, ${color} 0%, ${color} ${20 + brightness * 40}%, #0b1020 100%)`,
    boxShadow: brightness > 0 ? `0 0 ${8 + brightness * 24}px ${color}` : 'none',
  };
}

function controller(light: Light) {
  return controllerStore.controllers.find((c) => c.id === light.controller_id);
}

function controllerName(light: Light): string {
  return controller(light)?.name ?? t('lights.controllerN', { id: light.controller_id });
}

function controllerDirty(light: Light): boolean {
  return !!controller(light)?.is_dirty;
}

function isOnline(light: Light): boolean {
  const c = controller(light);
  if (!c) return false;
  const status = wsStore.controllersState[`controller_${c.id}`] ?? wsStore.controllersState[c.technical_name] ?? c.status;
  return status === 'ONLINE';
}


async function run(action: () => Promise<unknown>, fallback: string) {
  try {
    await action();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, fallback) });
  }
}

function setMode(light: Light, channelId: number, mode: ChannelMode) {
  const ch = light.channels.find((c) => c.id === channelId);
  const value = mode === 'MANUAL' ? Math.round(levels(light)[channelId] ?? ch?.current_intensity ?? 0) : undefined;
  void run(() => store.control(light.id, mode, channelId, value), t('lights.notify.commandFailed'));
}

function setManual(light: Light, channelId: number, value: number) {
  void run(async () => {
    await store.control(light.id, 'MANUAL', channelId, value);
    delete manualDraft.value[channelId];
  }, t('lights.notify.commandFailed'));
}

function setAllAuto(light: Light) {
  void run(() => store.control(light.id, 'AUTO'), t('lights.notify.commandFailed'));
}

function startDemo(light: Light, durationS: number) {
  localDemos.value[light.id] = { start: Date.now(), durationMs: durationS * 1000 };
  void run(() => store.startDemo(light.id, durationS), t('lights.notify.demoFailed'));
  if (!isOnline(light)) {
    $q.notify({ type: 'info', message: t('lights.notify.demoOffline') });
  }
}

function stopDemo(light: Light) {
  delete localDemos.value[light.id];
  void run(() => store.stopDemo(light.id), t('lights.notify.stopFailed'));
}

// --- Dialogues ---
const lightDialog = ref(false);
const editedLight = ref<Light | null>(null);
const channelDialog = ref(false);
const channelLight = ref<Light | null>(null);
const editedChannel = ref<LightChannel | null>(null);
const editorDialog = ref(false);
const editorLight = ref<Light | null>(null);

function openLightDialog(light: Light | null) {
  editedLight.value = light;
  lightDialog.value = true;
}

function openChannelDialog(light: Light, channel: LightChannel | null) {
  channelLight.value = light;
  editedChannel.value = channel;
  channelDialog.value = true;
}

function openEditor(light: Light) {
  editorLight.value = light;
  editorDialog.value = true;
}

function removeLight(light: Light) {
  confirmRemove(t('lights.item', { name: light.name }), () => store.remove(light.id), {
    message: t('lights.deleteMessage', { name: light.name }),
  });
}

function removeChannel(channel: LightChannel) {
  confirmRemove(t('lights.channelItem', { name: channel.name }), () => store.removeChannel(channel.id), {
    message: t('lights.channelDeleteMessage', { name: channel.name }),
  });
}

onMounted(async () => {
  await Promise.all([
    store.fetch(props.aquaId),
    store.fetchCatalog(),
    controllerStore.controllers.length ? Promise.resolve() : controllerStore.fetch(),
  ]);
  timer = setInterval(() => {
    clock.value = Date.now();
    nowMinuteValue.value = nowMinute();
    for (const [id, demo] of Object.entries(localDemos.value)) {
      if (clock.value - demo.start >= demo.durationMs) delete localDemos.value[Number(id)];
    }
  }, 250);
});

onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
.light-card {
  border-radius: 12px;
}

.preview {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 2px solid rgba(0, 0, 0, 0.1);
  transition: background 0.25s linear, box-shadow 0.25s linear;
}

.channel-dot {
  display: inline-block;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.15);
  transition: box-shadow 0.25s linear;
}

.channel-dot--light {
  border: 1px solid rgba(0, 0, 0, 0.45);
}

/* Téléphone : les réglages du canal passent sous son niveau */
@media (max-width: 599.98px) {
  .channel-item {
    flex-wrap: wrap;
  }

  .channel-item__controls {
    flex: 1 1 100%;
    align-items: flex-end;
    padding-left: 56px;
    margin-top: 6px;
  }

  .preview {
    width: 48px;
    height: 48px;
  }
}

.level-value {
  width: 44px;
  text-align: right;
}
</style>
