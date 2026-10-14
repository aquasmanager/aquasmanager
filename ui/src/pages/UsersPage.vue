<template>
  <q-page class="app-page">
    <PageHeader icon="people" :title="t('users.title')" :subtitle="t('users.subtitle')">
      <template #actions>
        <q-btn unelevated color="primary" icon="person_add" :label="t('users.create')" @click="openCreate" />
      </template>
    </PageHeader>

    <q-card flat bordered>
      <AppTable
        :rows="store.users"
        :columns="columns"
        row-key="id"
        :loading="store.loading"
        :pagination="{ rowsPerPage: 25 }"
      >
        <template #body-cell-username="props">
          <q-td :props="props">
            <div class="row items-center no-wrap">
              <q-avatar size="32px" color="blue-1" text-color="primary" class="q-mr-sm text-weight-bold">
                {{ props.row.username.slice(0, 2).toUpperCase() }}
              </q-avatar>
              <span class="text-weight-medium">{{ props.row.username }}</span>
              <q-badge v-if="props.row.id === authStore.user?.id" outline color="primary" :label="t('users.you')" class="q-ml-sm" />
            </div>
          </q-td>
        </template>

        <template #body-cell-role="props">
          <q-td :props="props">
            <q-chip dense :color="roleColor(props.value as Role)" text-color="white">
              {{ roleLabel(props.value as Role) }}
            </q-chip>
          </q-td>
        </template>

        <template #body-cell-must_change_password="props">
          <q-td :props="props">
            <q-icon v-if="props.value" name="key" color="orange-8" size="20px">
              <q-tooltip>{{ t('users.mustChange') }}</q-tooltip>
            </q-icon>
          </q-td>
        </template>

        <template #body-cell-actions="props">
          <q-td :props="props">
            <q-btn flat round dense icon="edit" color="grey-7" :aria-label="t('actions.edit')" @click="openEdit(props.row as ManagedUser)">
              <q-tooltip>{{ t('actions.edit') }}</q-tooltip>
            </q-btn>
            <q-btn flat round dense icon="lock_reset" color="grey-7" :aria-label="t('users.resetPassword')" @click="openResetPassword(props.row as ManagedUser)">
              <q-tooltip>{{ t('users.resetPassword') }}</q-tooltip>
            </q-btn>
            <q-btn flat round dense icon="delete" color="negative" :aria-label="t('actions.delete')" @click="handleDelete(props.row as ManagedUser)">
              <q-tooltip>{{ t('actions.delete') }}</q-tooltip>
            </q-btn>
          </q-td>
        </template>
      </AppTable>
    </q-card>

    <!-- Création -->
    <FormDialog v-model="createOpen" icon="person_add" :title="t('users.create')" width="460px" :submit-label="t('users.createSubmit')" :loading="creating" @submit="submitCreate">
      <q-input
        v-model="createUsername"
        v-bind="createUsernameProps"
        :label="t('users.username')"
        outlined
        dense
        autofocus
        :error="!!createErrors.username"
        :error-message="createErrors.username"
      />
      <q-input
        v-model="createPassword"
        v-bind="createPasswordProps"
        :type="showCreatePassword ? 'text' : 'password'"
        :label="t('users.password')"
        outlined
        dense
        :error="!!createErrors.password"
        :error-message="createErrors.password"
      >
        <template #append>
          <q-icon :name="showCreatePassword ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showCreatePassword = !showCreatePassword" />
        </template>
      </q-input>
      <q-input
        v-model="createConfirmPassword"
        v-bind="createConfirmPasswordProps"
        :type="showCreatePassword ? 'text' : 'password'"
        :label="t('users.confirmPassword')"
        outlined
        dense
        :error="!!createErrors.confirmPassword"
        :error-message="createErrors.confirmPassword"
      />
      <AppSelect
        v-model="createRole"
        v-bind="createRoleProps"
        :options="roleOptions"
        :label="t('users.role')"
        :error="!!createErrors.role"
        :error-message="createErrors.role"
      />
      <q-toggle v-model="createMustChange" :label="t('users.forceChangeFirst')" />
    </FormDialog>

    <!-- Édition (nom / rôle) -->
    <FormDialog v-model="editOpen" icon="manage_accounts" :title="t('users.editTitle')" :subtitle="editTarget?.username" width="440px" @submit="submitEdit">
      <q-input v-model="editUsername" :label="t('users.username')" outlined dense />
      <AppSelect v-model="editRole" :options="roleOptions" :label="t('users.role')" />
    </FormDialog>

    <!-- Réinitialisation du mot de passe -->
    <FormDialog
      v-model="resetOpen"
      icon="lock_reset"
      icon-bg="red-1"
      icon-color="negative"
      :title="t('users.resetPassword')"
      :subtitle="resetTarget?.username"
      width="440px"
      :submit-label="t('users.reset')"
      submit-color="negative"
      @submit="submitReset"
    >
      <q-input
        v-model="newPassword"
        :type="showPassword ? 'text' : 'password'"
        :label="t('users.newPassword')"
        outlined
        dense
        :rules="[(val: string) => val.length >= 8 || t('users.errors.passwordMin')]"
      >
        <template #append>
          <q-icon :name="showPassword ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showPassword = !showPassword" />
        </template>
      </q-input>
      <q-input
        v-model="confirmNewPassword"
        :type="showPassword ? 'text' : 'password'"
        :label="t('users.confirmPassword')"
        outlined
        dense
        :rules="[(val: string) => val === newPassword || t('users.errors.mismatch')]"
      />
      <q-toggle v-model="resetMustChange" :label="t('users.forceChangeNext')" />
    </FormDialog>
  </q-page>
</template>

<script setup lang="ts">
import AppTable from 'src/components/AppTable.vue';
import { computed, ref, onMounted } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { QTableColumn } from 'quasar';
import { z } from 'zod';
import { toTypedSchema } from '@vee-validate/zod';
import { useForm } from 'vee-validate';
import { useUserManagementStore } from 'src/stores/userManagementStore';
import { useAuthStore } from 'src/stores/authStore';
import { Role, type ManagedUser, type RegisterForm } from 'src/types/auth';
import PageHeader from 'src/components/PageHeader.vue';
import FormDialog from 'src/components/FormDialog.vue';
import AppSelect from 'src/components/AppSelect.vue';
import { useConfirmRemove } from 'src/composables/useConfirmDialog';
import { apiErrorMessage } from 'src/utils/apiError';

const $q = useQuasar();
const { t } = useI18n();
const store = useUserManagementStore();
const authStore = useAuthStore();
const { confirmRemove } = useConfirmRemove();

const columns = computed<QTableColumn[]>(() => [
  { name: 'username', label: t('users.columns.username'), field: 'username', align: 'left', sortable: true },
  { name: 'role', label: t('users.columns.role'), field: 'role', align: 'left', sortable: true },
  {
    name: 'must_change_password',
    label: '',
    field: 'must_change_password',
    align: 'center',
  },
  { name: 'actions', label: '', field: 'actions', align: 'right' },
]);

const ROLES = [Role.consult, Role.seller, Role.caretaker, Role.user, Role.manager, Role.admin];
const roleOptions = computed(() => ROLES.map((value) => ({ label: t(`roles.${value}`), value })));

const createOpen = ref(false);
const creating = ref(false);
const showCreatePassword = ref(false);

const createSchema = computed(() =>
  toTypedSchema(
    z
      .object({
        username: z.string().trim().min(4, t('users.errors.usernameMin')),
        password: z.string().min(8, t('users.errors.passwordMin')),
        confirmPassword: z.string().min(8, t('users.errors.confirm')),
        role: z.nativeEnum(Role, { message: t('users.errors.role') }),
        mustChangePassword: z.boolean(),
      })
      .refine((data) => data.password === data.confirmPassword, {
        message: t('users.errors.mismatch'),
        path: ['confirmPassword'],
      }),
  ),
);

const {
  handleSubmit: handleCreateSubmit,
  errors: createErrors,
  defineField: defineCreateField,
  resetForm: resetCreateForm,
} = useForm<RegisterForm>({
  validationSchema: createSchema,
  validateOnMount: false,
  initialValues: { role: Role.consult, mustChangePassword: true },
});

const [createUsername, createUsernameProps] = defineCreateField('username');
const [createPassword, createPasswordProps] = defineCreateField('password');
const [createConfirmPassword, createConfirmPasswordProps] = defineCreateField('confirmPassword');
const [createRole, createRoleProps] = defineCreateField('role');
const [createMustChange] = defineCreateField('mustChangePassword');

function openCreate() {
  resetCreateForm({
    values: { username: '', password: '', confirmPassword: '', role: Role.consult, mustChangePassword: true },
  });
  createOpen.value = true;
}

const submitCreate = handleCreateSubmit(async (values) => {
  creating.value = true;
  try {
    await authStore.register(values);
    createOpen.value = false;
    $q.notify({ type: 'positive', message: t('users.notify.created', { name: values.username }) });
    await store.fetchUsers();
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('users.notify.createFailed')) });
  } finally {
    creating.value = false;
  }
});

function roleLabel(role: Role): string {
  return ROLES.includes(role) ? t(`roles.${role}`) : role;
}

function roleColor(role: Role): string {
  switch (role) {
    case Role.admin:
      return 'red-8';
    case Role.manager:
      return 'orange-8';
    case Role.user:
      return 'primary';
    case Role.seller:
      return 'teal-7';
    case Role.caretaker:
      return 'purple-6';
    default:
      return 'grey-7';
  }
}

const editOpen = ref(false);
const editTarget = ref<ManagedUser | null>(null);
const editUsername = ref('');
const editRole = ref<Role>(Role.consult);

function openEdit(user: ManagedUser) {
  editTarget.value = user;
  editUsername.value = user.username;
  editRole.value = user.role;
  editOpen.value = true;
}

async function submitEdit() {
  if (!editTarget.value) return;
  try {
    await store.updateUser(editTarget.value.id, {
      username: editUsername.value,
      role: editRole.value,
    });
    editOpen.value = false;
    $q.notify({ type: 'positive', message: t('users.notify.updated') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('users.notify.updateFailed')) });
  }
}

const resetOpen = ref(false);
const resetTarget = ref<ManagedUser | null>(null);
const newPassword = ref('');
const confirmNewPassword = ref('');
const resetMustChange = ref(true);
const showPassword = ref(false);

function openResetPassword(user: ManagedUser) {
  resetTarget.value = user;
  newPassword.value = '';
  confirmNewPassword.value = '';
  resetMustChange.value = true;
  resetOpen.value = true;
}

async function submitReset() {
  if (!resetTarget.value) return;
  if (newPassword.value.length < 8 || newPassword.value !== confirmNewPassword.value) {
    $q.notify({ type: 'warning', message: t('users.notify.checkPassword') });
    return;
  }
  try {
    await store.resetPassword(resetTarget.value.id, newPassword.value, resetMustChange.value);
    resetOpen.value = false;
    $q.notify({ type: 'positive', message: t('users.notify.reset') });
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('users.notify.resetFailed')) });
  }
}

function handleDelete(user: ManagedUser) {
  confirmRemove(t('users.item', { name: user.username }), () => store.deleteUser(user.id), {
    message: t('users.deleteMessage', { name: user.username }),
  });
}

onMounted(() => {
  void store.fetchUsers();
});
</script>
