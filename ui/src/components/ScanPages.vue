<!--
  Pages photographiées (facture, certificat) avant leur envoi en un seul PDF :
  prise de vue page par page, ou images existantes ; rotation, ordre, suppression.
-->
<template>
  <div class="column gap-sm">
    <div class="row items-center q-gutter-sm">
      <q-btn v-if="hasCamera" unelevated color="primary" icon="document_scanner" no-caps :label="t('documents.scan.takePage')" @click="camera?.click()" />
      <q-btn outline color="primary" icon="add_photo_alternate" no-caps :label="t('documents.scan.addImages')" @click="picker?.click()" />
      <input ref="camera" type="file" accept="image/*" capture="environment" class="hidden" @change="onFiles" />
      <input ref="picker" type="file" accept="image/*" multiple class="hidden" @change="onFiles" />
    </div>
    <template v-if="modelValue.length">
      <div class="row q-col-gutter-sm">
        <div v-for="(page, index) in modelValue" :key="page.id" class="col-6 col-sm-4">
          <q-card flat bordered class="overflow-hidden">
            <div class="scan-thumb">
              <img :src="page.url" :alt="t('documents.scan.page', { n: index + 1 })" :style="{ transform: `rotate(${page.rotation * 90}deg) scale(${page.rotation % 2 ? 0.75 : 1})` }" />
              <q-badge color="primary" class="absolute-top-left q-ma-xs">{{ index + 1 }}</q-badge>
            </div>
            <div class="row justify-center no-wrap q-pa-xs">
              <q-btn flat round dense size="sm" icon="chevron_left" :disable="index === 0" :aria-label="t('documents.scan.moveLeft')" @click="move(index, -1)" />
              <q-btn flat round dense size="sm" icon="rotate_right" :aria-label="t('documents.scan.rotate')" @click="rotate(index)" />
              <q-btn flat round dense size="sm" icon="chevron_right" :disable="index === modelValue.length - 1" :aria-label="t('documents.scan.moveRight')" @click="move(index, 1)" />
              <q-btn flat round dense size="sm" color="negative" icon="delete" :aria-label="t('actions.delete')" @click="remove(index)" />
            </div>
          </q-card>
        </div>
      </div>
      <q-input :model-value="name" :label="t('documents.scan.name')" :placeholder="t('documents.scan.namePlaceholder')" outlined dense maxlength="120" @update:model-value="(v) => emit('update:name', String(v ?? ''))" />
      <div class="text-caption text-grey-7">{{ t('documents.scan.hint', modelValue.length) }}</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';

export interface ScanPage {
  id: string;
  file: File;
  url: string;
  rotation: number;
}

const props = defineProps<{ modelValue: ScanPage[]; name: string }>();
const emit = defineEmits<{ 'update:modelValue': [pages: ScanPage[]]; 'update:name': [name: string] }>();

const { t } = useI18n();
const $q = useQuasar();
const hasCamera = $q.platform.has.touch;
const camera = ref<HTMLInputElement | null>(null);
const picker = ref<HTMLInputElement | null>(null);

function onFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []).filter((f) => f.type.startsWith('image/'));
  input.value = '';
  if (!files.length) return;
  const added = files.map((file) => ({ id: `${Date.now()}-${Math.random()}`, file, url: URL.createObjectURL(file), rotation: 0 }));
  emit('update:modelValue', [...props.modelValue, ...added]);
}

function move(index: number, delta: number) {
  const pages = [...props.modelValue];
  const [page] = pages.splice(index, 1);
  pages.splice(index + delta, 0, page!);
  emit('update:modelValue', pages);
}

function rotate(index: number) {
  emit('update:modelValue', props.modelValue.map((p, i) => (i === index ? { ...p, rotation: (p.rotation + 1) % 4 } : p)));
}

function remove(index: number) {
  URL.revokeObjectURL(props.modelValue[index]!.url);
  emit('update:modelValue', props.modelValue.filter((_, i) => i !== index));
}

onBeforeUnmount(() => props.modelValue.forEach((p) => URL.revokeObjectURL(p.url)));
</script>

<style scoped>
.scan-thumb {
  position: relative;
  aspect-ratio: 3 / 4;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(127, 127, 127, 0.08);
  overflow: hidden;
}
.scan-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.2s ease;
}
</style>
