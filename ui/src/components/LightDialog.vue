<template>
  <FormDialog
    :model-value="modelValue"
    icon="lightbulb"
    :title="light ? t('lights.lampDialog.settingsTitle') : t('lights.lampDialog.newTitle')"
    :subtitle="t('lights.lampDialog.subtitle')"
    width="580px"
    :submit-label="light ? t('common.save') : t('lights.lampDialog.create')"
    :loading="saving"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="save"
  >
        <q-input v-model="form.name" :label="t('lights.lampDialog.name')" outlined dense maxlength="30" />
        <div class="row q-col-gutter-sm">
          <div class="col-12 col-sm-7">
            <q-select
              v-model="form.controller_id"
              :options="controllerOptions"
              emit-value
              map-options
              :label="t('lights.lampDialog.controller')"
              outlined
              dense
              :disable="!!light && light.channels.length > 0"
              :hint="light && light.channels.length > 0 ? t('lights.lampDialog.controllerLocked') : t('lights.lampDialog.controllerRtc')"
            />
          </div>
          <div class="col-12 col-sm-5">
            <q-input
              v-model.number="form.pwm_frequency"
              type="number"
              :label="t('lights.lampDialog.pwmFrequency')"
              suffix="Hz"
              outlined
              dense
              :hint="t('lights.lampDialog.pwmHint')"
            />
          </div>
        </div>

        <template v-if="light && light.channels.length > 0">
          <div>
            <div class="text-subtitle2 text-weight-bold row items-center"><q-icon name="nightlight" class="q-mr-xs" />{{ t('lights.lampDialog.moonlight') }}</div>
            <div class="text-caption text-grey-7 q-mb-sm">
              {{ t('lights.lampDialog.moonlightHelp') }}
            </div>
            <div v-for="ch in light.channels" :key="ch.id" class="row q-col-gutter-sm items-center no-wrap">
              <div class="col-5 col-sm-4 row items-center no-wrap">
                <q-checkbox :model-value="(moon[ch.id] ?? 0) > 0" dense @update:model-value="(on: boolean) => (moon[ch.id] = on ? 2 : 0)" />
                <span class="channel-dot q-mx-xs" :style="{ background: ch.color }" />
                <span class="ellipsis">{{ ch.name }}</span>
              </div>
              <div class="col">
                <q-slider
                  v-if="(moon[ch.id] ?? 0) > 0"
                  v-model="moon[ch.id]"
                  :min="1"
                  :max="100"
                  label
                  :label-value="`${moon[ch.id]} %`"
                  :aria-label="t('lights.lampDialog.moonlight')"
                />
                <span v-else class="text-caption text-grey-6">{{ t('lights.lampDialog.moonlightOff') }}</span>
              </div>
              <div class="col-auto text-caption app-mono" style="width: 44px; text-align: right">
                {{ (moon[ch.id] ?? 0) > 0 ? `${moon[ch.id]} %` : '' }}
              </div>
            </div>
          </div>
        </template>

        <div>
          <div class="text-subtitle2 text-weight-bold row items-center"><q-icon name="trending_up" class="q-mr-xs" />{{ t('lights.lampDialog.acclimation') }}</div>
          <div class="text-caption text-grey-7 q-mb-sm">
            {{ t('lights.lampDialog.acclimationHelp') }}
          </div>
          <q-toggle v-model="acclimation" :label="t('lights.lampDialog.acclimationOn')" />
          <div v-if="acclimation" class="row q-col-gutter-sm q-mt-xs">
            <div class="col-12 col-sm-4">
              <DateInput v-model="form.acclimation_start" :label="t('lights.lampDialog.start')" />
            </div>
            <div class="col-6 col-sm-4">
              <q-input v-model.number="form.acclimation_days" type="number" :label="t('lights.lampDialog.duration')" :suffix="t('lights.lampDialog.days')" outlined dense />
            </div>
            <div class="col-6 col-sm-4">
              <q-input v-model.number="form.acclimation_start_percent" type="number" :label="t('lights.lampDialog.startPercent')" suffix="%" outlined dense />
            </div>
          </div>
        </div>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import DateInput from 'src/components/DateInput.vue';
import { apiErrorMessage } from 'src/utils/apiError';
import { useControllerStore } from 'src/stores/controllerStore';
import { useLightStore } from 'src/stores/lightStore';
import type { Light, LightInput } from 'src/types/light';

const props = defineProps<{ modelValue: boolean; light: Light | null; aquaId: number }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [light: Light] }>();

const { t } = useI18n();
const $q = useQuasar();
const store = useLightStore();
const controllerStore = useControllerStore();
const saving = ref(false);
const acclimation = ref(false);

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function emptyForm(): LightInput {
  return {
    name: '',
    aquarium_id: props.aquaId,
    controller_id: controllerStore.controllers.find((c) => c.rtc_model)?.id ?? 0,
    pwm_frequency: 1000,
    moonlight: [],
    acclimation_start: null,
    acclimation_days: null,
    acclimation_start_percent: 50,
  };
}

const form = ref<LightInput>(emptyForm());

// Le programme horaire tourne sur l'ESP : seuls les contrôleurs équipés d'une horloge RTC sont proposés
const controllerOptions = computed(() =>
  controllerStore.controllers
    .filter((c) => c.rtc_model || c.id === props.light?.controller_id)
    .map((c) => ({
      label: t('lights.lampDialog.controllerOption', { name: c.name, rtc: c.rtc_model ?? t('lights.lampDialog.noRtc') }),
      value: c.id,
    })),
);
// Clair de lune : intensité par canal (0 = éteint la nuit)
const moon = ref<Record<number, number>>({});

function reset() {
  if (controllerStore.controllers.length === 0) void controllerStore.fetch();
  if (props.light) {
    const l = props.light;
    form.value = {
      name: l.name,
      aquarium_id: l.aquarium_id,
      controller_id: l.controller_id,
      pwm_frequency: l.pwm_frequency,
      moonlight: l.moonlight,
      acclimation_start: l.acclimation_start,
      acclimation_days: l.acclimation_days,
      acclimation_start_percent: l.acclimation_start_percent,
    };
    acclimation.value = !!(l.acclimation_start && l.acclimation_days);
    moon.value = Object.fromEntries(l.channels.map((ch) => [ch.id, ch.moonlight_intensity]));
  } else {
    form.value = emptyForm();
    acclimation.value = false;
    moon.value = {};
  }
}

async function save() {
  const f = form.value;
  if (!f.name.trim() || !f.controller_id) {
    $q.notify({ type: 'warning', message: t('lights.lampDialog.required') });
    return;
  }
  const payload: LightInput = {
    ...f,
    name: f.name.trim(),
    acclimation_start: acclimation.value ? f.acclimation_start || today() : null,
    acclimation_days: acclimation.value ? f.acclimation_days || 30 : null,
    moonlight: Object.entries(moon.value)
      .filter(([, intensity]) => intensity > 0)
      .map(([id, intensity]) => ({ channel_id: Number(id), intensity })),
  };
  saving.value = true;
  try {
    const saved = props.light ? await store.update(props.light.id, payload) : await store.create(payload);
    emit('saved', saved);
    emit('update:modelValue', false);
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('lights.lampDialog.saveFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.channel-dot {
  display: inline-block;
  flex: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.2);
}
</style>
