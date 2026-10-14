<!-- Carte d'une commande groupée (liste « Près de chez moi » et « Mes commandes ») -->
<template>
  <q-card flat bordered class="full-height column no-wrap cursor-pointer group-order-card" @click="emit('open')">
    <q-card-section class="col q-pb-xs">
      <div class="row items-start no-wrap q-mb-xs">
        <div class="col text-subtitle1 text-weight-bold ellipsis-2-lines">{{ order.title }}</div>
        <q-chip dense :color="statusColor" text-color="white" class="q-mr-none">{{ t(`groupOrders.status.${order.status}`) }}</q-chip>
      </div>
      <div class="text-body2"><q-icon name="storefront" size="16px" class="q-mr-xs" />{{ order.shop }}</div>
      <div class="text-body2 text-grey-8"><q-icon name="place" size="16px" class="q-mr-xs" />{{ departmentLabel(order.department) }} · {{ order.area }}</div>
      <div class="text-body2 text-grey-8"><q-icon name="event" size="16px" class="q-mr-xs" />{{ t('groupOrders.deadline', { date: formatDate(order.deadline) }) }}</div>
    </q-card-section>
    <q-card-section class="row items-center q-pt-xs">
      <span class="text-caption text-grey-7">{{ t('groupOrders.organizedBy', { name: order.organizer }) }}</span>
      <q-space />
      <q-chip v-if="order.my_role" dense outline color="primary">{{ t(`groupOrders.role.${order.my_role}`) }}</q-chip>
      <q-chip dense icon="group" color="grey-2" text-color="grey-9">{{ order.participants }}</q-chip>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { GroupOrder } from 'src/types/groupOrder';
import { departmentLabel } from 'src/utils/departments';
import { formatDate } from 'src/utils/format';

const props = defineProps<{ order: GroupOrder }>();
const emit = defineEmits<{ (e: 'open'): void }>();
const { t } = useI18n();

const statusColor = computed(() =>
  props.order.status === 'open' ? 'positive' : props.order.status === 'closed' ? 'blue-grey-6' : 'grey-6',
);
</script>

<style scoped>
.group-order-card {
  transition: box-shadow 0.2s;
}

.group-order-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}
</style>
