<!--
  Fiche d'une commande groupée : selon le rôle, rejoindre (passant), contact de
  l'organisateur et retrait (participant), participants et gestion (organisateur).
-->
<template>
  <q-dialog :model-value="modelValue" @update:model-value="(v: boolean) => emit('update:modelValue', v)" @show="load">
    <q-card style="width: 620px; max-width: 95vw">
      <q-card-section class="row items-start no-wrap q-pb-sm">
        <q-avatar size="40px" color="blue-1" text-color="primary" icon="local_shipping" class="q-mr-md" />
        <div class="col">
          <div class="text-h6 text-weight-bold">{{ order?.title ?? '' }}</div>
          <div v-if="order" class="text-body2 text-grey-7">
            {{ departmentLabel(order.department) }} · {{ order.area }}
          </div>
        </div>
        <q-btn flat round dense icon="close" color="grey-7" :aria-label="t('common.close')" v-close-popup />
      </q-card-section>

      <q-card-section v-if="loading" class="text-center q-py-lg"><q-spinner color="primary" size="2em" /></q-card-section>

      <template v-else-if="order">
        <q-card-section class="q-pt-none column gap-sm">
          <div class="row items-center gap-sm">
            <q-chip dense :color="statusColor" text-color="white" class="q-ml-none">{{ t(`groupOrders.status.${order.status}`) }}</q-chip>
            <q-chip v-if="order.my_role" dense outline color="primary">{{ t(`groupOrders.role.${order.my_role}`) }}</q-chip>
            <span class="text-caption text-grey-7">{{ t('groupOrders.participants', { n: order.participants }, order.participants) }}</span>
          </div>
          <div class="text-body2">
            <q-icon name="storefront" class="q-mr-xs" />
            <a v-if="order.shop_url" :href="order.shop_url" target="_blank" rel="noopener noreferrer">{{ order.shop }}</a>
            <span v-else>{{ order.shop }}</span>
          </div>
          <div class="text-body2"><q-icon name="event" class="q-mr-xs" />{{ t('groupOrders.deadline', { date: formatDate(order.deadline) }) }}</div>
          <div class="text-body2"><q-icon name="person" class="q-mr-xs" />{{ t('groupOrders.organizedBy', { name: order.organizer }) }}</div>
          <div v-if="order.description" class="text-body2 description q-mt-xs">{{ order.description }}</div>
        </q-card-section>

        <!-- Contact de l'organisateur : visible des participants (et de lui-même) -->
        <q-card-section v-if="order.contact" class="q-pt-none">
          <q-banner rounded class="bg-blue-1 text-blue-10">
            <template #avatar><q-icon name="contact_mail" color="primary" /></template>
            <div class="text-weight-bold">{{ t('groupOrders.organizerContact') }}</div>
            <div class="contact">{{ order.contact }}</div>
          </q-banner>
        </q-card-section>

        <!-- Organisateur : participants et leurs contacts -->
        <q-card-section v-if="order.my_role === 'owner'" class="q-pt-none">
          <div class="text-subtitle2 text-weight-bold q-mb-xs">{{ t('groupOrders.members') }}</div>
          <div v-if="!order.members?.length" class="text-grey-6 text-body2">{{ t('groupOrders.noMember') }}</div>
          <q-list v-else bordered separator class="rounded-borders">
            <q-item v-for="m in order.members" :key="m.id">
              <q-item-section>
                <q-item-label class="text-weight-medium">{{ m.name }}</q-item-label>
                <q-item-label caption class="contact">{{ m.contact }}</q-item-label>
                <q-item-label v-if="m.message" caption class="description">{{ m.message }}</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-btn flat round dense icon="person_remove" color="negative" @click="removeMember(m.id, m.name)">
                  <q-tooltip>{{ t('groupOrders.removeMember') }}</q-tooltip>
                </q-btn>
              </q-item-section>
            </q-item>
          </q-list>
        </q-card-section>

        <!-- Participant : sa demande -->
        <q-card-section v-if="order.my_role === 'participant' && order.members?.length" class="q-pt-none">
          <div class="text-subtitle2 text-weight-bold q-mb-xs">{{ t('groupOrders.myRequest') }}</div>
          <div class="text-body2 description">{{ order.members[0]!.message || '—' }}</div>
        </q-card-section>

        <!-- Passant : rejoindre -->
        <q-card-section v-if="!order.my_role && order.status === 'open' && can.edit" class="q-pt-none">
          <div class="text-subtitle2 text-weight-bold q-mb-sm">{{ t('groupOrders.join.title') }}</div>
          <div class="column gap-sm">
            <div class="row q-col-gutter-sm">
              <div class="col-12 col-sm-5"><q-input v-model="join.name" outlined dense maxlength="40" :label="t('groupOrders.join.name')" /></div>
              <div class="col-12 col-sm-7"><q-input v-model="join.contact" outlined dense maxlength="120" :label="t('groupOrders.join.contact')" /></div>
            </div>
            <q-input v-model="join.message" outlined dense type="textarea" autogrow maxlength="1000" :label="t('groupOrders.join.message')" :placeholder="t('groupOrders.join.messagePlaceholder')" />
            <div class="text-caption text-grey-7">{{ t('groupOrders.join.privacy') }}</div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-px-md q-pb-md q-gutter-sm">
          <template v-if="order.my_role === 'owner'">
            <q-btn flat no-caps color="negative" icon="delete" :label="t('groupOrders.actions.delete')" :disable="busy" @click="remove" />
            <q-btn v-if="order.status === 'open'" outline no-caps color="primary" icon="edit" :label="t('groupOrders.actions.edit')" @click="emit('edit', order)" />
            <q-btn v-if="order.status === 'open'" unelevated no-caps color="primary" icon="shopping_cart_checkout" :label="t('groupOrders.actions.close')" :loading="busy" @click="setStatus('closed')" />
            <q-btn v-else unelevated no-caps color="primary" icon="lock_open" :label="t('groupOrders.actions.reopen')" :loading="busy" @click="setStatus('open')" />
          </template>
          <template v-else-if="order.my_role === 'participant'">
            <q-btn flat no-caps color="negative" icon="logout" :label="t('groupOrders.actions.leave')" :loading="busy" @click="leave" />
          </template>
          <template v-else>
            <q-btn flat no-caps color="grey-7" icon="flag" :label="t('groupOrders.actions.report')" :disable="busy" @click="report" />
            <q-btn v-if="order.status === 'open' && can.edit" unelevated no-caps color="primary" icon="group_add" :label="t('groupOrders.actions.join')" :loading="busy" @click="sendJoin" />
          </template>
        </q-card-actions>
      </template>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import type { GroupOrder } from 'src/types/groupOrder';
import { departmentLabel } from 'src/utils/departments';
import { usePermissions } from 'src/composables/usePermissions';
import { useConfirm, useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';
import { formatDate } from 'src/utils/format';

const props = defineProps<{ modelValue: boolean; orderId: string | null }>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'changed'): void;
  (e: 'edit', order: GroupOrder): void;
}>();

const { t } = useI18n();
const $q = useQuasar();
const can = usePermissions();
const { confirmRemove } = useConfirmRemove();
const { confirmAction } = useConfirm();

const order = ref<GroupOrder | null>(null);
const loading = ref(false);
const busy = ref(false);
const join = ref({ name: '', contact: '', message: '' });

const statusColor = computed(() =>
  order.value?.status === 'open' ? 'positive' : order.value?.status === 'closed' ? 'blue-grey-6' : 'grey-6',
);

async function load() {
  if (!props.orderId) return;
  loading.value = true;
  try {
    order.value = (await axios.get<GroupOrder>(`/group-orders/${props.orderId}`)).data;
  } catch (err) {
    order.value = null;
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('groupOrders.loadFailed')) });
    emit('update:modelValue', false);
  } finally {
    loading.value = false;
  }
}

async function run(action: () => Promise<GroupOrder | null | void>, message?: string) {
  busy.value = true;
  try {
    const result = await action();
    if (result) order.value = result;
    emit('changed');
    if (message) $q.notify({ type: 'positive', message });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('groupOrders.actionFailed')) });
  } finally {
    busy.value = false;
  }
}

async function sendJoin() {
  if (join.value.name.trim().length < 2 || join.value.contact.trim().length < 3) {
    $q.notify({ type: 'warning', message: t('groupOrders.join.required') });
    return;
  }
  await run(
    async () =>
      (
        await axios.post<GroupOrder>(`/group-orders/${props.orderId}/join`, {
          name: join.value.name.trim(),
          contact: join.value.contact.trim(),
          message: join.value.message.trim() || null,
        })
      ).data,
    t('groupOrders.join.done'),
  );
}

function leave() {
  confirmAction({
    title: t('groupOrders.actions.leave'),
    message: t('groupOrders.leaveMessage'),
    okLabel: t('groupOrders.actions.leave'),
    okColor: 'negative',
    onOk: () =>
      run(async () => {
        await axios.delete(`/group-orders/${props.orderId}/join`);
        emit('update:modelValue', false);
      }, t('groupOrders.left')),
  });
}

async function setStatus(status: 'open' | 'closed') {
  await run(async () => (await axios.patch<GroupOrder>(`/group-orders/${props.orderId}`, { status })).data);
}

function removeMember(id: string, name: string) {
  confirmRemove(name, async () => {
    await axios.delete(`/group-orders/${props.orderId}/members/${id}`);
    await load();
    emit('changed');
  });
}

function remove() {
  if (!order.value) return;
  confirmRemove(order.value.title, async () => {
    await axios.delete(`/group-orders/${props.orderId}`);
    emit('changed');
    emit('update:modelValue', false);
  }, { message: t('groupOrders.deleteMessage') });
}

function report() {
  confirmAction({
    title: t('groupOrders.actions.report'),
    message: t('groupOrders.reportMessage'),
    okLabel: t('groupOrders.actions.report'),
    onOk: () => run(async () => {
      await axios.post(`/group-orders/${props.orderId}/report`);
    }, t('groupOrders.reported')),
  });
}
</script>

<style scoped>
.description {
  white-space: pre-line;
}

.contact {
  user-select: all;
  word-break: break-word;
}
</style>
