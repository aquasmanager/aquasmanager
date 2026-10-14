<!--
  Comparer deux photos d'un même sujet (croissance, couleur d'un corail selon
  l'éclairage) : côte à côte, ou superposées avec un curseur avant / après.
-->
<template>
  <q-dialog :model-value="modelValue" maximized transition-show="fade" transition-hide="fade" @update:model-value="(v: boolean) => emit('update:modelValue', v)" @show="init">
    <q-card class="bg-black text-white column no-wrap">
      <q-bar class="bg-black text-white q-py-lg">
        <q-icon name="compare" class="q-mr-sm" />
        <div class="ellipsis">{{ t('photos.compare.title', { name: entityLabel }) }}</div>
        <q-space />
        <q-btn-toggle
          v-model="mode"
          dense
          no-caps
          unelevated
          toggle-color="primary"
          color="grey-9"
          text-color="white"
          :options="[
            { value: 'slider', icon: 'compare', label: $q.screen.gt.xs ? t('photos.compare.slider') : '' },
            { value: 'side', icon: 'view_column', label: $q.screen.gt.xs ? t('photos.compare.side') : '' },
          ]"
          class="q-mr-sm"
        />
        <q-btn flat dense round icon="close" :aria-label="t('common.close')" v-close-popup />
      </q-bar>

      <div class="row q-col-gutter-sm q-px-md q-pt-sm">
        <div class="col-6">
          <q-select v-model="beforeId" dark dense outlined emit-value map-options options-dark :options="options" :label="t('photos.compare.before')" />
        </div>
        <div class="col-6">
          <q-select v-model="afterId" dark dense outlined emit-value map-options options-dark :options="options" :label="t('photos.compare.after')" />
        </div>
      </div>
      <div v-if="gap" class="text-center text-caption text-grey-5 q-pt-xs">{{ gap }}</div>

      <div class="col q-pa-md row items-center justify-center">
        <!-- Côte à côte -->
        <div v-if="mode === 'side'" class="row no-wrap q-gutter-sm full-width full-height">
          <div v-for="photo in [before, after]" :key="photo?.id ?? 'none'" class="col column items-center justify-center">
            <img v-if="photo" :src="url(photo.id)" class="side-image" alt="" />
            <div v-if="photo" class="text-caption q-mt-xs">{{ formatDate(photo.created_at) }}</div>
          </div>
        </div>

        <!-- Curseur : la photo « après » recouvre « avant » jusqu'au curseur -->
        <div v-else-if="before && after" class="slider-frame">
          <img :src="url(before.id)" class="slider-image" alt="" />
          <img :src="url(after.id)" class="slider-image slider-image--top" :style="{ clipPath: `inset(0 0 0 ${position}%)` }" alt="" />
          <div class="slider-line" :style="{ left: `${position}%` }" />
          <div class="slider-label slider-label--left">{{ formatDate(before.created_at) }}</div>
          <div class="slider-label slider-label--right">{{ formatDate(after.created_at) }}</div>
        </div>
      </div>

      <div v-if="mode === 'slider'" class="q-px-xl q-pb-lg">
        <q-slider v-model="position" :min="0" :max="100" dark color="white" :aria-label="t('photos.compare.slider')" />
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import type { PhotoEntityType, PhotoInfo } from 'src/types/photo';
import { photoFileUrl } from 'src/stores/photoStore';
import { formatDate } from 'src/utils/format';

const props = defineProps<{
  modelValue: boolean;
  photos: PhotoInfo[];
  entityType: PhotoEntityType;
  entityId: number;
  entityLabel?: string | undefined;
}>();
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void }>();

const { t } = useI18n();
const $q = useQuasar();

const mode = ref<'slider' | 'side'>('slider');
const position = ref(50);
const beforeId = ref<number | null>(null);
const afterId = ref<number | null>(null);

const sorted = computed(() => [...props.photos].sort((a, b) => a.created_at.localeCompare(b.created_at)));
const options = computed(() => sorted.value.map((p, i) => ({ value: p.id, label: `${formatDate(p.created_at)} · ${t('photos.compare.photo', { n: i + 1 })}` })));
const before = computed(() => props.photos.find((p) => p.id === beforeId.value) ?? null);
const after = computed(() => props.photos.find((p) => p.id === afterId.value) ?? null);

// « 3 mois d'écart »
const gap = computed(() => {
  if (!before.value || !after.value) return '';
  const days = Math.round(Math.abs(new Date(after.value.created_at).getTime() - new Date(before.value.created_at).getTime()) / 86400000);
  if (days < 1) return t('photos.compare.sameDay');
  if (days < 60) return t('photos.compare.days', { n: days }, days);
  return t('photos.compare.months', { n: Math.round(days / 30.4) });
});

function url(photoId: number): string {
  return photoFileUrl(props.entityType, props.entityId, photoId);
}

// Par défaut : la plus ancienne et la plus récente
function init() {
  beforeId.value = sorted.value[0]?.id ?? null;
  afterId.value = sorted.value[sorted.value.length - 1]?.id ?? null;
  position.value = 50;
}
</script>

<style scoped>
.side-image {
  max-width: 100%;
  max-height: calc(100vh - 220px);
  object-fit: contain;
}

.slider-frame {
  position: relative;
  width: min(100%, 1100px);
  aspect-ratio: 4 / 3;
  max-height: calc(100vh - 240px);
}

.slider-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.slider-image--top {
  background: #000;
}

.slider-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: white;
  box-shadow: 0 0 6px rgba(0, 0, 0, 0.8);
  transform: translateX(-1px);
  pointer-events: none;
}

.slider-label {
  position: absolute;
  bottom: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.6);
  font-size: 12px;
}

.slider-label--left {
  left: 8px;
}

.slider-label--right {
  right: 8px;
}
</style>
