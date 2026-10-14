<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="width: 480px; max-width: 90vw; border-radius: 12px; overflow: hidden" v-if="plant">
      <div class="relative-position">
        <q-img :src="mainPhotoUrl(PhotoEntityType.plants, plant.id)" ratio="16/9">
          <div class="absolute-full bg-gradient-overlay flex items-end q-pa-md">
            <div class="full-width">
              <q-badge color="green-7" class="text-weight-bold q-px-sm q-py-xs q-mb-xs" style="border-radius: 4px">
                {{ t('livestock.growingBadge', { speed: growingLabel }) }}
              </q-badge>
              <div class="text-h5 text-weight-bold text-white text-shadow">{{ plant.name }}</div>
              <div class="text-subtitle2 text-italic text-white text-shadow">{{ plant.scientific_name }}</div>
            </div>
          </div>
        </q-img>
        <q-btn icon="close" flat round dense color="white" class="absolute-top-right q-ma-sm" v-close-popup />
      </div>

      <q-card-section>
        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="category" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.familyLabel') }}</div>
                <div class="text-weight-medium">{{ plant.family || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="public" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.originLabel') }}</div>
                <div class="text-weight-medium">{{ plant.origin || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="straighten" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.adultSizeMax') }}</div>
                <div class="text-weight-medium">{{ plant.max_height }} cm</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="grid_view" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.locationInTank') }}</div>
                <div class="text-weight-medium">{{ locationLabel }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="event" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.acquiredOnLabelF') }}</div>
                <div class="text-weight-medium">{{ formattedDate }}</div>
              </div>
            </div>
          </div>
        </div>

        <q-separator class="q-mb-md" />

        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="wb_sunny" color="amber-8" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.light') }}</div>
                <div class="text-weight-medium">{{ plant.light_range.min }} - {{ plant.light_range.max }} / 10</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="thermostat" color="deep-orange-6" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.temperature') }}</div>
                <div class="text-weight-medium">
                  {{ plant.temperature_range.min }} - {{ plant.temperature_range.max }} °C
                </div>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div class="row items-center justify-between text-caption text-grey-7 q-mb-xs">
            <span><q-icon name="shield" size="14px" class="q-mr-xs" />{{ t('livestock.resistance') }}</span>
            <span>{{ plant.resistance_level }}/10</span>
          </div>
          <q-linear-progress :value="plant.resistance_level / 10" color="positive" rounded size="8px" />
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
import type { Plant } from 'src/types/plant';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl } from 'src/stores/photoStore';

const { t } = useI18n();

const props = defineProps<{
  modelValue: boolean;
  plant: Plant | null;
}>();

defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const growingLabel = computed(() => (props.plant ? t(`livestock.growingShort.${props.plant.growing}`) : ''));
const locationLabel = computed(() => (props.plant ? t(`livestock.plantLocationShort.${props.plant.location}`) : '—'));

const formattedDate = computed(() => formatDate(props.plant?.date_acquisition, '—'));
</script>

<style scoped>
.bg-gradient-overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.75) 100%);
}
.text-shadow {
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>
