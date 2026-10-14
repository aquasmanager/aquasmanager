<!--
  Champ « Photo principale » : choisir une image, ou la prendre directement avec
  l'appareil photo arrière (bouton visible sur téléphone et tablette).
-->
<template>
  <q-file
    :model-value="modelValue"
    outlined
    dense
    clearable
    :label="label"
    accept="image/*"
    @update:model-value="(file: File | null) => emit('update:modelValue', file)"
  >
    <template #prepend><q-icon name="photo" /></template>
    <template v-if="hasCamera" #after>
      <q-btn flat round dense color="primary" icon="photo_camera" :aria-label="t('photos.takePhoto')" @click.stop="camera?.click()">
        <q-tooltip>{{ t('photos.takePhoto') }}</q-tooltip>
      </q-btn>
      <input ref="camera" type="file" accept="image/*" capture="environment" class="hidden" @change="onCapture" />
    </template>
  </q-file>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';

defineProps<{ modelValue: File | null; label: string }>();
const emit = defineEmits<{ 'update:modelValue': [value: File | null] }>();

const { t } = useI18n();
const $q = useQuasar();
// L'attribut capture n'ouvre l'appareil photo que sur un appareil tactile
const hasCamera = $q.platform.has.touch;
const camera = ref<HTMLInputElement | null>(null);

function onCapture(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  input.value = '';
  if (file) emit('update:modelValue', file);
}
</script>
