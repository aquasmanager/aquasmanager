<template>
  <FormDialog
    :model-value="modelValue"
    icon="palette"
    :title="channel ? t('lights.channelDialog.editTitle') : t('lights.channelDialog.newTitle')"
    :subtitle="light?.name"
    width="540px"
    :submit-label="channel ? t('common.save') : t('lights.channelDialog.add')"
    :loading="saving"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="save"
  >
        <div>
          <div class="text-caption text-grey-8 q-mb-xs">{{ t('lights.channelDialog.spectrum') }}</div>
          <div class="row q-gutter-xs">
            <q-chip
              v-for="s in store.spectra"
              :key="s.key"
              clickable
              :outline="form.spectrum !== s.key"
              :color="form.spectrum === s.key ? 'primary' : undefined"
              :text-color="form.spectrum === s.key ? 'white' : undefined"
              @click="chooseSpectrum(s.key)"
            >
              <span class="color-dot q-mr-xs" :style="{ background: s.color }" />{{ s.label }}
            </q-chip>
          </div>
        </div>

        <div class="row q-col-gutter-sm">
          <div class="col-12 col-sm-7">
            <q-input v-model="form.name" :label="t('lights.channelDialog.name')" outlined dense maxlength="30" />
          </div>
          <div class="col-12 col-sm-5">
            <q-input v-model="form.color" :label="t('lights.channelDialog.color')" outlined dense>
              <template #prepend><span class="color-dot" :style="{ background: form.color }" /></template>
              <template #append>
                <q-icon name="colorize" class="cursor-pointer">
                  <q-popup-proxy cover transition-show="scale" transition-hide="scale">
                    <q-color v-model="form.color" no-header default-view="palette" format-model="hex" />
                  </q-popup-proxy>
                </q-icon>
              </template>
            </q-input>
          </div>
        </div>

        <q-select
          v-model="form.pin_id"
          :options="pinOptions"
          emit-value
          map-options
          :label="t('lights.channelDialog.pin')"
          outlined
          dense
          :hint="t('lights.channelDialog.pinHint')"
        />

        <div>
          <div class="text-caption text-grey-8">{{ t('lights.channelDialog.maxIntensity', { n: form.max_intensity }) }}</div>
          <q-slider v-model="form.max_intensity" :min="0" :max="100" :step="5" markers />
          <div class="text-caption text-grey-6">{{ t('lights.channelDialog.maxHelp') }}</div>
        </div>

        <div>
          <div class="text-caption text-grey-8">{{ t('lights.channelDialog.minIntensity', { n: form.min_intensity }) }}</div>
          <q-slider v-model="form.min_intensity" :min="0" :max="Math.min(30, form.max_intensity)" :step="1" label />
          <div class="text-caption text-grey-6">{{ t('lights.channelDialog.minHelp') }}</div>
        </div>

        <q-toggle v-model="form.inverted" :label="t('lights.channelDialog.inverted')" />
  </FormDialog>
</template>

<script setup lang="ts">
import { pinLabel } from 'src/utils/pins';
import { computed, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import { apiErrorMessage } from 'src/utils/apiError';
import { useControllerPinStore } from 'src/stores/controllerPinStore';
import { useLightStore } from 'src/stores/lightStore';
import type { Light, LightChannel, LightChannelInput } from 'src/types/light';

const props = defineProps<{ modelValue: boolean; light: Light | null; channel: LightChannel | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

const { t } = useI18n();
const $q = useQuasar();
const store = useLightStore();
const pinStore = useControllerPinStore();
const saving = ref(false);
const form = ref<LightChannelInput>({ name: '', pin_id: 0, color: '#ffffff', spectrum: 'white', max_intensity: 100, min_intensity: 0, inverted: false });

const pinOptions = computed(() => {
  const options = pinStore.controllers_availables_pins
    .filter((p) => {
      const n = Number(p.pin_number);
      if (String(p.mode) !== 'FREE' || Number.isNaN(n)) return false;
      // Canaux d'un module PCA9685 (PWM), ou GPIO de l'ESP32 capable de PWM (pas 34 à 39)
      return p.module_id ? p.module_type === 'PCA9685' : n < 34 || n > 39;
    })
    .map((p) => ({ label: pinLabel(p.pin_number, p.module_id, p.module_number) ?? '', value: p.id }));
  if (props.channel && !options.some((o) => o.value === props.channel!.pin_id)) {
    options.unshift({ label: t('lights.channelDialog.pinCurrent', { pin: props.channel.pin_number ?? '?' }), value: props.channel.pin_id });
  }
  return options;
});

function chooseSpectrum(key: string) {
  const spectrum = store.spectra.find((s) => s.key === key);
  const previous = store.spectra.find((s) => s.key === form.value.spectrum);
  // Nom et couleur suivent le spectre tant qu'ils n'ont pas été personnalisés
  if (spectrum) {
    if (!form.value.name || form.value.name === previous?.label) form.value.name = spectrum.label;
    if (!previous || form.value.color === previous.color) form.value.color = spectrum.color;
  }
  form.value.spectrum = key;
}

function reset() {
  void store.fetchCatalog();
  if (props.light) void pinStore.getAvailablesPins(props.light.controller_id);
  form.value = props.channel
    ? {
        name: props.channel.name,
        pin_id: props.channel.pin_id,
        color: props.channel.color,
        spectrum: props.channel.spectrum,
        max_intensity: props.channel.max_intensity,
        min_intensity: props.channel.min_intensity ?? 0,
        inverted: props.channel.inverted,
      }
    : { name: '', pin_id: 0, color: '#f5f5f0', spectrum: 'white', max_intensity: 100, min_intensity: 0, inverted: false };
}

async function save() {
  if (!props.light) return;
  if (!form.value.name.trim() || !form.value.pin_id) {
    $q.notify({ type: 'warning', message: t('lights.channelDialog.required') });
    return;
  }
  saving.value = true;
  try {
    const payload = { ...form.value, name: form.value.name.trim(), color: form.value.color.toLowerCase() };
    if (props.channel) await store.updateChannel(props.channel.id, payload);
    else await store.addChannel(props.light.id, payload);
    emit('update:modelValue', false);
    $q.notify({ type: 'positive', message: t('lights.channelDialog.saved') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('lights.channelDialog.saveFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.4);
}
</style>
