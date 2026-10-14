<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="width: 480px; max-width: 90vw; border-radius: 12px; overflow: hidden" v-if="aquarium">
      <div class="relative-position">
        <q-img :src="mainPhotoUrl(PhotoEntityType.aquariums, aquarium.id)" ratio="16/9">
          <div class="absolute-full bg-gradient-overlay flex items-end q-pa-md">
            <div class="full-width">
              <q-badge
                :color="aquarium.water_type === WaterType.sea ? 'teal-6' : 'primary'"
                class="text-weight-bold q-px-sm q-py-xs q-mb-xs"
                style="border-radius: 4px"
              >
                {{ aquarium.water_type === WaterType.sea ? t('aquariumInfo.sea') : t('aquariumInfo.fresh') }}
              </q-badge>
              <div class="text-h5 text-weight-bold text-white text-shadow">{{ aquarium.name }}</div>
              <div v-if="aquarium.biotope" class="text-subtitle2 text-white text-shadow">
                <q-icon name="eco" size="16px" class="q-mr-xs" />{{ aquarium.biotope }}
              </div>
            </div>
          </div>
        </q-img>
        <q-btn icon="close" flat round dense color="white" class="absolute-top-right q-ma-sm" :aria-label="t('common.close')" v-close-popup />
      </div>

      <q-card-section>
        <div class="row q-col-gutter-md">
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="water_drop" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('aquariumInfo.volume') }}</div>
                <div class="text-weight-medium">{{ aquarium.volume }} L</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="event" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('aquariumInfo.filledOn') }}</div>
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
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatDate } from 'src/utils/format';
import { WaterType, type Aquarium } from 'src/types/Aquarium';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl } from 'src/stores/photoStore';

const props = defineProps<{
  modelValue: boolean;
  aquarium: Aquarium | null;
}>();

defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const { t } = useI18n();
const formattedDate = computed(() => formatDate(props.aquarium?.date_creation, '—'));
</script>

<style scoped>
.bg-gradient-overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.75) 100%);
}
.text-shadow {
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>
