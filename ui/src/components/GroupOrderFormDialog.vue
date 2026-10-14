<!-- Organiser (ou modifier) une commande groupée : annonce visible des passionnés du département -->
<template>
  <FormDialog
    :model-value="modelValue"
    :title="order ? t('groupOrders.form.editTitle') : t('groupOrders.form.newTitle')"
    :subtitle="t('groupOrders.form.subtitle')"
    icon="local_shipping"
    width="600px"
    :loading="saving"
    :submit-label="order ? t('common.save') : t('groupOrders.form.publish')"
    @update:model-value="(v: boolean) => emit('update:modelValue', v)"
    @show="reset"
    @submit="save"
  >
    <div class="column gap-md">
      <q-input v-model="form.title" outlined dense maxlength="80" :label="t('groupOrders.form.title')" :placeholder="t('groupOrders.form.titlePlaceholder')" />
      <div class="row q-col-gutter-sm">
        <div class="col-12 col-sm-6">
          <q-input v-model="form.shop" outlined dense maxlength="80" :label="t('groupOrders.form.shop')" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="form.shop_url" outlined dense maxlength="300" type="url" :label="t('groupOrders.form.shopUrl')" placeholder="https://" />
        </div>
      </div>
      <div class="row q-col-gutter-sm">
        <div class="col-12 col-sm-6">
          <q-select
            v-model="form.department"
            outlined
            dense
            :disable="!!order"
            :options="departmentOptions"
            emit-value
            map-options
            use-input
            input-debounce="0"
            :label="t('groupOrders.form.department')"
            @filter="filterDepartments"
          />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="form.area" outlined dense maxlength="80" :label="t('groupOrders.form.area')" :hint="t('groupOrders.form.areaHint')" />
        </div>
      </div>
      <div class="row q-col-gutter-sm">
        <div class="col-12 col-sm-6">
          <DateInput v-model="form.deadline" :label="t('groupOrders.form.deadline')" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input v-model="form.organizer" outlined dense maxlength="40" :disable="!!order" :label="t('groupOrders.form.organizer')" />
        </div>
      </div>
      <q-input v-model="form.contact" outlined dense maxlength="120" :label="t('groupOrders.form.contact')" :hint="t('groupOrders.form.contactHint')" />
      <q-input
        v-model="form.description"
        outlined
        type="textarea"
        autogrow
        maxlength="2000"
        :label="t('groupOrders.form.description')"
        :placeholder="t('groupOrders.form.descriptionPlaceholder')"
      />
      <div class="text-caption text-grey-7">{{ t('groupOrders.form.privacy') }}</div>
    </div>
  </FormDialog>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import axios from 'axios';
import FormDialog from 'src/components/FormDialog.vue';
import DateInput from 'src/components/DateInput.vue';
import type { GroupOrder, GroupOrderInput } from 'src/types/groupOrder';
import { DEPARTMENTS } from 'src/utils/departments';
import { apiErrorMessage } from 'src/utils/apiError';
import { isoDate } from 'src/utils/format';

const props = defineProps<{ modelValue: boolean; order?: GroupOrder | null; defaultDepartment?: string | null }>();
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void; (e: 'saved', order: GroupOrder): void }>();

const { t } = useI18n();
const $q = useQuasar();
const saving = ref(false);

const allDepartments = DEPARTMENTS.map((d) => ({ value: d.code, label: `${d.code} · ${d.name}` }));
const departmentOptions = ref(allDepartments);

function filterDepartments(value: string, update: (fn: () => void) => void) {
  update(() => {
    const q = value.trim().toLowerCase();
    departmentOptions.value = q ? allDepartments.filter((d) => d.label.toLowerCase().includes(q)) : allDepartments;
  });
}

function emptyForm(): GroupOrderInput {
  const deadline = new Date();
  deadline.setDate(deadline.getDate() + 10);
  return {
    title: '',
    shop: '',
    shop_url: null,
    department: props.defaultDepartment ?? '',
    area: '',
    deadline: isoDate(deadline),
    organizer: '',
    contact: '',
    description: null,
  };
}

const form = ref<GroupOrderInput>(emptyForm());

function reset() {
  const o = props.order;
  form.value = o
    ? {
        title: o.title,
        shop: o.shop,
        shop_url: o.shop_url ?? null,
        department: o.department,
        area: o.area,
        deadline: o.deadline,
        organizer: o.organizer,
        contact: o.contact ?? '',
        description: o.description ?? null,
      }
    : emptyForm();
}

async function save() {
  const f = form.value;
  if (!f.title.trim() || !f.shop.trim() || !f.department || !f.area.trim() || !f.deadline || !f.organizer.trim() || !f.contact.trim()) {
    $q.notify({ type: 'warning', message: t('groupOrders.form.required') });
    return;
  }
  const payload = { ...f, shop_url: f.shop_url?.trim() || null, description: f.description?.trim() || null };
  saving.value = true;
  try {
    const { data } = props.order
      ? await axios.patch<GroupOrder>(`/group-orders/${props.order.id}`, {
          title: payload.title,
          shop: payload.shop,
          shop_url: payload.shop_url,
          area: payload.area,
          deadline: payload.deadline,
          contact: payload.contact,
          description: payload.description,
        })
      : await axios.post<GroupOrder>('/group-orders/', payload);
    emit('saved', data);
    emit('update:modelValue', false);
    $q.notify({ type: 'positive', message: props.order ? t('groupOrders.form.saved') : t('groupOrders.form.published') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('groupOrders.form.failed')) });
  } finally {
    saving.value = false;
  }
}
</script>
