<template>
  <q-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)">
    <q-card style="width: 480px; max-width: 90vw; border-radius: 12px; overflow: hidden" v-if="coral">
      <div class="relative-position">
        <q-img :src="mainPhotoUrl(PhotoEntityType.corals, coral.id)" ratio="16/9">
          <div class="absolute-full bg-gradient-overlay flex items-end q-pa-md">
            <div class="full-width">
              <q-badge color="teal-6" class="text-weight-bold q-px-sm q-py-xs q-mb-xs" style="border-radius: 4px">
                {{ coral.type }}
              </q-badge>
              <div class="text-h5 text-weight-bold text-white text-shadow">{{ coral.name }}</div>
              <div class="text-subtitle2 text-italic text-white text-shadow">{{ coral.scientific_name }}</div>
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
                <div class="text-weight-medium">{{ coral.family || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="public" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.originLabel') }}</div>
                <div class="text-weight-medium">{{ coral.origin || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-12">
            <div class="row items-center text-grey-8">
              <q-icon name="storefront" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.provenanceLabel') }}</div>
                <div class="text-weight-medium">{{ coral.acquired_from || '—' }}</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="gavel" color="primary" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">CITES</div>
                <div class="text-weight-medium">{{ coral.cites || '—' }}</div>
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

        <q-separator class="q-mb-md" />

        <div class="row q-col-gutter-md q-mb-md">
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="wb_sunny" color="amber-8" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.light') }}</div>
                <div class="text-weight-medium">{{ coral.light_range.min }} - {{ coral.light_range.max }} / {{ CORAL_LIGHT_MAX }}</div>
                <div class="text-caption text-grey-7">{{ toPar(coral.light_range.min) }} – {{ toPar(coral.light_range.max) }} PAR</div>
              </div>
            </div>
          </div>
          <div class="col-6">
            <div class="row items-center text-grey-8">
              <q-icon name="air" color="blue-6" size="20px" class="q-mr-sm" />
              <div>
                <div class="text-caption text-grey-6">{{ t('livestock.brewing') }}</div>
                <div class="text-weight-medium">{{ coral.brewing_range.min }} - {{ coral.brewing_range.max }} / 10</div>
              </div>
            </div>
          </div>
        </div>

        <div class="q-gutter-y-sm">
          <div>
            <div class="row items-center justify-between text-caption text-grey-7 q-mb-xs">
              <span><q-icon name="local_fire_department" size="14px" class="q-mr-xs" />{{ t('livestock.aggressiveness') }}</span>
              <span>{{ coral.aggressiveness_level }}/10</span>
            </div>
            <q-linear-progress :value="coral.aggressiveness_level / 10" color="deep-orange-6" rounded size="8px" />
          </div>
          <div>
            <div class="row items-center justify-between text-caption text-grey-7 q-mb-xs">
              <span><q-icon name="shield" size="14px" class="q-mr-xs" />{{ t('livestock.resistance') }}</span>
              <span>{{ coral.resistance_level }}/10</span>
            </div>
            <q-linear-progress :value="coral.resistance_level / 10" color="positive" rounded size="8px" />
          </div>
          <div>
            <div class="row items-center justify-between text-caption text-grey-7 q-mb-xs">
              <span><q-icon name="height" size="14px" class="q-mr-xs" />{{ t('livestock.locationLowHigh') }}</span>
              <span>{{ coral.location_level }}/10</span>
            </div>
            <q-linear-progress :value="coral.location_level / 10" color="primary" rounded size="8px" />
          </div>
        </div>
      </q-card-section>

      <q-separator />
      <q-card-section>
        <SpecimenDocuments entity-type="corals" :entity-id="coral.id" />
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
import { CORAL_LIGHT_MAX, formatDate, toPar } from 'src/utils/format';
import SpecimenDocuments from 'src/components/SpecimenDocuments.vue';
import type { Coral } from 'src/types/coral';
import { PhotoEntityType } from 'src/types/photo';
import { mainPhotoUrl } from 'src/stores/photoStore';

const { t } = useI18n();

const props = defineProps<{
  modelValue: boolean;
  coral: Coral | null;
}>();

defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const formattedDate = computed(() => formatDate(props.coral?.date_acquisition, '—'));
</script>

<style scoped>
.bg-gradient-overlay {
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0) 0%, rgba(0, 0, 0, 0.75) 100%);
}
.text-shadow {
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}
</style>
