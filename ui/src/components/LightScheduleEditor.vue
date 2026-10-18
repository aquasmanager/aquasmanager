<template>
  <FormDialog
    :model-value="modelValue"
    icon="timeline"
    :title="light ? t('lights.editor.title', { name: light.name }) : t('lights.editor.titleShort')"
    :subtitle="t('lights.editor.subtitle', { n: MAX_POINTS })"
    width="980px"
    :cancel-label="t('common.close')"
    submit-icon="save"
    :submit-disabled="dirty.size === 0"
    :loading="saving"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="save"
  >
    <template #footer-left>
      <span v-if="dirty.size" class="text-caption text-orange-9">{{ t('lights.editor.dirty', dirty.size) }}</span>
      <span v-else class="text-caption text-grey-7">{{ t('lights.editor.nothingToSave') }}</span>
    </template>
    <template v-if="light">
      <div>
        <LightScheduleChart :channels="editedChannels" :now-minute="currentMinute" :highlight-id="selectedId" :height="240" />
      </div>

      <!-- Profils -->
      <div>
        <q-card flat bordered class="q-pa-sm bg-blue-grey-1">
          <div class="row items-center q-col-gutter-sm">
            <div class="col-12 col-sm-5">
              <q-select v-model="profileKey" :options="profileOptions" emit-value map-options :label="t('lights.editor.profile')" outlined dense bg-color="white">
                <template #option="scope">
                  <q-item v-bind="scope.itemProps">
                    <q-item-section>
                      <q-item-label>{{ scope.opt.label }}</q-item-label>
                      <q-item-label caption>{{ scope.opt.description }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </template>
              </q-select>
            </div>
            <div class="col-auto" style="width: 150px">
              <q-input
                v-model="profileStart"
                mask="##:##"
                :label="t('lights.editor.profileStart')"
                :hint="profileEnd ? t('lights.editor.profileEnd', { time: profileEnd }) : undefined"
                :error="profileStart !== '' && parseTime(profileStart) === null"
                :disable="!profileKey"
                outlined
                dense
                bg-color="white"
              />
            </div>
            <div class="col-auto">
              <q-toggle v-model="profileMoonlight" :label="t('lights.editor.moonlight')" />
            </div>
            <div class="col-auto">
              <q-btn unelevated color="primary" icon="auto_awesome" :label="t('lights.editor.applyProfile')" :disable="!profileKey || parseTime(profileStart) === null" :loading="applying" @click="applyProfile" />
            </div>
          </div>
          <div class="text-caption text-grey-7 q-mt-xs">
            {{ t('lights.editor.profileHelp') }}
          </div>
        </q-card>
      </div>

      <!-- Canal sélectionné -->
      <div>
        <div class="row q-gutter-xs q-mb-sm">
          <q-chip
            v-for="ch in editedChannels"
            :key="ch.id"
            clickable
            :outline="ch.id !== selectedId"
            :style="ch.id === selectedId ? { background: ch.color, color: textOn(ch.color), border: isVeryLight(ch.color) ? '1px solid #8a97a6' : undefined } : { borderColor: visibleColor(ch.color, $q.dark.isActive) }"
            @click="selectedId = ch.id"
          >
            <span class="color-dot q-mr-xs" :style="{ background: ch.color }" />
            {{ ch.name }}
            <q-badge v-if="dirty.has(ch.id)" color="orange" rounded floating />
          </q-chip>
        </div>

        <template v-if="selected">
          <q-list bordered separator class="rounded-borders">
            <q-item v-for="(point, index) in selected.schedule" :key="index" dense>
              <q-item-section style="max-width: 120px">
                <q-input
                  :model-value="formatMinute(point.minute)"
                  mask="##:##"
                  dense
                  outlined
                  @update:model-value="(v: string | number | null) => typedTime(index, String(v ?? ''))"
                  @change="(v: string) => setTime(index, v)"
                />
              </q-item-section>
              <q-item-section>
                <q-slider
                  :model-value="point.intensity"
                  :min="0"
                  :max="100"
                  :step="1"
                  label
                  :label-value="`${point.intensity} %`"
                  :color="'primary'"
                  @update:model-value="(v: number | null) => setIntensity(index, v ?? 0)"
                />
              </q-item-section>
              <q-item-section side style="min-width: 64px" class="text-weight-medium text-right">
                <div>{{ point.intensity }} %</div>
                <div v-if="point.intensity > selected.max_intensity" class="text-caption text-orange-9 text-no-wrap">
                  → {{ selected.max_intensity }} %
                  <q-tooltip>{{ t('lights.editor.cappedPoint', { n: selected.max_intensity }) }}</q-tooltip>
                </div>
              </q-item-section>
              <q-item-section side>
                <q-btn flat round dense icon="delete" color="negative" size="sm" @click="removePoint(index)" />
              </q-item-section>
            </q-item>
            <q-item v-if="selected.schedule.length === 0">
              <q-item-section class="text-grey-6">{{ t('lights.editor.noPoint') }}</q-item-section>
            </q-item>
          </q-list>

          <div class="row items-center q-gutter-sm q-mt-sm">
            <q-btn flat dense icon="add" color="primary" :label="t('lights.editor.addPoint')" :disable="selected.schedule.length >= MAX_POINTS" @click="addPoint" />
            <q-btn flat dense icon="content_copy" color="primary" :label="t('lights.editor.copyTo')">
              <q-menu>
                <q-list dense style="min-width: 200px">
                  <q-item v-for="ch in editedChannels.filter((c) => c.id !== selectedId)" :key="ch.id" clickable v-close-popup @click="copyTo([ch.id])">
                    <q-item-section avatar><span class="color-dot" :style="{ background: ch.color }" /></q-item-section>
                    <q-item-section>{{ ch.name }}</q-item-section>
                  </q-item>
                  <q-separator />
                  <q-item clickable v-close-popup @click="copyTo(editedChannels.filter((c) => c.id !== selectedId).map((c) => c.id))">
                    <q-item-section>{{ t('lights.editor.allOthers') }}</q-item-section>
                  </q-item>
                </q-list>
              </q-menu>
            </q-btn>
            <q-btn flat dense icon="layers_clear" color="grey-8" :label="t('lights.editor.clear')" @click="clearCurve" />
          </div>
        </template>
      </div>

    </template>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import type { AxiosError } from 'axios';
import LightScheduleChart from 'src/components/LightScheduleChart.vue';
import { useLightStore } from 'src/stores/lightStore';
import type { Light, LightChannel } from 'src/types/light';
import { formatMinute, isVeryLight, nowMinute, parseTime, visibleColor } from 'src/utils/lightSchedule';

const MAX_POINTS = 24;

const props = defineProps<{ modelValue: boolean; light: Light | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const store = useLightStore();

// Repère « maintenant » du graphique : avance tant que l'éditeur est ouvert
const currentMinute = ref(nowMinute(store.timezone));
let clock: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  clock = setInterval(() => (currentMinute.value = nowMinute(store.timezone)), 15000);
});
onBeforeUnmount(() => clearInterval(clock));

const editedChannels = ref<LightChannel[]>([]);
const selectedId = ref<number | null>(null);
const dirty = ref(new Set<number>());
const saving = ref(false);
const applying = ref(false);
const profileKey = ref<string | null>(null);
const profileMoonlight = ref(true);
// Heure de début du profil (HH:MM) : celle du profil par défaut, modifiable ; tout le programme suit
const profileStart = ref('');
const selectedProfile = computed(() => store.profiles.find((p) => p.key === profileKey.value) ?? null);
const profileEnd = computed(() => {
  const start = parseTime(profileStart.value);
  const p = selectedProfile.value;
  if (start === null || !p) return '';
  return formatMinute((start + p.end - p.start + 1440) % 1440);
});
watch(selectedProfile, (p) => {
  profileStart.value = p ? formatMinute(p.start) : '';
});

const selected = computed(() => editedChannels.value.find((c) => c.id === selectedId.value) ?? null);
const profileOptions = computed(() => store.profiles.map((p) => ({ label: p.label, value: p.key, description: p.description })));

function reset() {
  currentMinute.value = nowMinute(store.timezone);
  editedChannels.value = (props.light?.channels ?? []).map((ch) => ({ ...ch, schedule: ch.schedule.map((p) => ({ ...p })) }));
  selectedId.value = editedChannels.value[0]?.id ?? null;
  dirty.value = new Set();
  void store.fetchCatalog();
}

function markDirty(id: number) {
  dirty.value = new Set(dirty.value).add(id);
}

function sortSelected() {
  selected.value?.schedule.sort((a, b) => a.minute - b.minute);
}

function setTime(index: number, value: string) {
  const minute = parseTime(value);
  if (!selected.value || minute == null) return;
  if (selected.value.schedule.some((p, i) => i !== index && p.minute === minute)) {
    $q.notify({ type: 'warning', message: t('lights.editor.duplicate') });
    return;
  }
  selected.value.schedule[index]!.minute = minute;
  sortSelected();
  markDirty(selected.value.id);
}

// Heure saisie au clavier : prise en compte dès qu'elle est complète (le bouton Enregistrer
// s'active sans attendre la sortie du champ)
function typedTime(index: number, value: string) {
  if (/^\d{2}:\d{2}$/.test(value) && parseTime(value) !== selected.value?.schedule[index]?.minute) setTime(index, value);
}

function setIntensity(index: number, value: number) {
  if (!selected.value) return;
  selected.value.schedule[index]!.intensity = value;
  markDirty(selected.value.id);
}

function addPoint() {
  if (!selected.value) return;
  const used = new Set(selected.value.schedule.map((p) => p.minute));
  const last = selected.value.schedule.at(-1)?.minute ?? 8 * 60;
  let minute = (last + 60) % 1440;
  while (used.has(minute)) minute = (minute + 15) % 1440;
  selected.value.schedule.push({ minute, intensity: 50 });
  sortSelected();
  markDirty(selected.value.id);
}

function removePoint(index: number) {
  if (!selected.value) return;
  selected.value.schedule.splice(index, 1);
  markDirty(selected.value.id);
}

function clearCurve() {
  if (!selected.value) return;
  selected.value.schedule = [];
  markDirty(selected.value.id);
}

function copyTo(targetIds: number[]) {
  if (!selected.value) return;
  for (const ch of editedChannels.value) {
    if (targetIds.includes(ch.id)) {
      ch.schedule = selected.value.schedule.map((p) => ({ ...p }));
      markDirty(ch.id);
    }
  }
  $q.notify({ type: 'info', message: t('lights.editor.copied', targetIds.length) });
}

function errorDetail(err: unknown, fallback: string): string {
  const detail = (err as AxiosError<{ detail?: unknown }>).response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
}

async function save() {
  saving.value = true;
  try {
    for (const id of dirty.value) {
      const ch = editedChannels.value.find((c) => c.id === id);
      if (ch) await store.setSchedule(id, ch.schedule);
    }
    dirty.value = new Set();
    $q.notify({ type: 'positive', message: t('lights.editor.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: errorDetail(err, t('lights.editor.saveFailed')) });
  } finally {
    saving.value = false;
  }
}

function applyProfile() {
  if (!props.light || !profileKey.value) return;
  const lightId = props.light.id;
  const profile = store.profiles.find((p) => p.key === profileKey.value);
  $q.dialog({
    title: t('lights.editor.profileTitle'),
    message: t('lights.editor.profileMessage', { name: profile?.label ?? '' }),
    cancel: true,
    persistent: true,
  }).onOk(() => {
    void (async () => {
      applying.value = true;
      try {
        const updated = await store.applyProfile(lightId, profileKey.value!, profileMoonlight.value, parseTime(profileStart.value) ?? undefined);
        editedChannels.value = updated.channels.map((ch) => ({ ...ch, schedule: ch.schedule.map((p) => ({ ...p })) }));
        dirty.value = new Set();
        $q.notify({ type: 'positive', message: t('lights.editor.profileApplied') });
      } catch (err) {
        $q.notify({ type: 'negative', message: errorDetail(err, t('lights.editor.profileFailed')) });
      } finally {
        applying.value = false;
      }
    })();
  });
}

function textOn(hex: string): string {
  const v = parseInt(hex.replace('#', ''), 16);
  const luminance = (0.299 * ((v >> 16) & 255) + 0.587 * ((v >> 8) & 255) + 0.114 * (v & 255)) / 255;
  return luminance > 0.6 ? '#000' : '#fff';
}
</script>

<style scoped>
.color-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.4);
}
</style>
