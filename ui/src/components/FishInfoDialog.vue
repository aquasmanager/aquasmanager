<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="width: 480px; max-width: 90vw; border-radius: 12px; overflow: hidden" v-if="fish">
      <div class="relative-position">
        <q-img :src="mainPhotoUrl(PhotoEntityType.fishes, fish.id)" ratio="16/9">
          <div class="absolute-full bg-gradient-overlay flex items-end q-pa-md">
            <div class="full-width">
              <div class="row items-center q-gutter-x-sm q-mb-xs">
                <q-badge
                  :color="fish.reef_safe ? 'teal-6' : 'deep-orange-7'"
                  class="text-weight-bold q-px-sm q-py-xs"
                  style="border-radius: 4px"
                >
                  {{ fish.reef_safe ? t('livestock.reefSafe') : t('livestock.notReefSafe') }}
                </q-badge>
              </div>
              <div class="text-h5 text-weight-bold text-white text-shadow">{{ fish.name }}</div>
              <div class="text-subtitle2 text-italic text-white text-shadow">{{ fish.scientific_name }}</div>
            </div>
          </div>
        </q-img>
        <q-btn icon="close" flat round dense color="white" class="absolute-top-right q-ma-sm" v-close-popup />
      </div>

      <q-card-section>
        <div class="row q-col-gutter-md">
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="category" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.familyLabel') }}</div>
                <div class="text-weight-medium">{{ fish.family || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="public" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.originLabel') }}</div>
                <div class="text-weight-medium">{{ fish.origin || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="straighten" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.adultSizeMax') }}</div>
                <div class="text-weight-medium">{{ fish.max_height }} cm</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="water_drop" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.minVolumeShort') }}</div>
                <div class="text-weight-medium">{{ fish.min_volume }} L</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="event" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.acquiredOnLabel') }}</div>
                <div class="text-weight-medium">{{ formattedDate }}</div>
              </div>
            </div>
          </div>
        </div>
      </q-card-section>

      <q-separator />

      <q-card-actions align="right">
        <q-btn flat :label="t('common.close')" color="grey-8" v-close-popup />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { computed } from 'vue';
import { formatDate } from 'src/utils/format';
import type { Fish } from 'src/types/fish';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl } from 'src/stores/photoStore';

const { t } = useI18n();

const props = defineProps<{
  modelValue: boolean;
  fish: Fish | null;
}>();

defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const formattedDate = computed(() => formatDate(props.fish?.date_acquisition, '—'));
</script>

<style scoped>
.bg-gradient-overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.75) 100%);
}
.text-shadow {
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>
