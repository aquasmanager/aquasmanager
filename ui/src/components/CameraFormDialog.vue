<!--
  Ajout / modification d'une caméra : marque (chemins des flux préremplis),
  adresse, identifiants (mot de passe jamais réaffiché) et test du flux.
-->
<template>
  <FormDialog
    v-model="open"
    icon="videocam"
    :title="camera ? t('cameras.form.editTitle') : t('cameras.add')"
    :subtitle="t('cameras.form.subtitle')"
    width="560px"
    :loading="saving"
    @submit="save"
    @show="reset"
  >
    <div class="column gap-sm">
      <q-input
        v-model="form.name"
        :label="t('cameras.form.name')"
        outlined
        dense
        maxlength="60"
        :placeholder="t('cameras.form.namePlaceholder')"
        :rules="[(v) => !!v?.trim() || t('cameras.form.nameRequired')]"
      />
      <q-select v-model="form.brand" :options="brandOptions" emit-value map-options :label="t('cameras.form.brand')" outlined dense @update:model-value="applyPreset" />
      <div class="app-callout text-caption">
        <q-icon name="info" size="18px" />
        <div>{{ brandHint }}</div>
      </div>
      <div class="row q-col-gutter-sm">
        <div class="col-8">
          <q-input
            v-model="form.host"
            :label="t('cameras.form.host')"
            outlined
            dense
            placeholder="192.168.1.50"
            :rules="[(v) => !!v?.trim() || t('cameras.form.hostRequired')]"
          />
        </div>
        <div class="col-4">
          <q-input v-model.number="form.port" type="number" :label="t('cameras.form.port')" outlined dense min="1" max="65535" />
        </div>
      </div>
      <div class="row q-col-gutter-sm">
        <div class="col-12 col-sm-6">
          <q-input v-model="form.username" :label="t('cameras.form.username')" outlined dense autocomplete="off" />
        </div>
        <div class="col-12 col-sm-6">
          <q-input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            :label="t('cameras.form.password')"
            outlined
            dense
            autocomplete="new-password"
            :hint="camera?.has_password && !form.clear_password ? t('cameras.form.passwordKept') : undefined"
          >
            <template #append>
              <q-icon :name="showPassword ? 'visibility_off' : 'visibility'" class="cursor-pointer" @click="showPassword = !showPassword" />
            </template>
          </q-input>
        </div>
      </div>
      <q-checkbox v-if="camera?.has_password" v-model="form.clear_password" dense :label="t('cameras.form.clearPassword')" />
      <q-expansion-item v-model="pathsOpen" dense icon="tune" :label="t('cameras.form.paths')" header-class="q-px-none text-grey-8">
        <div class="column gap-sm q-pt-sm">
          <q-input v-model="form.main_path" :label="t('cameras.form.mainPath')" outlined dense prefix="/" />
          <q-input v-model="form.sub_path" :label="t('cameras.form.subPath')" outlined dense prefix="/" :hint="t('cameras.form.subPathHint')" />
        </div>
      </q-expansion-item>
      <div class="row items-center gap-sm">
        <q-btn outline color="primary" icon="network_check" :label="t('cameras.form.test')" :loading="testing" :disable="!form.host.trim()" @click="test" />
        <span v-if="testResult" class="text-caption" :class="testOk ? 'text-positive' : 'text-negative'">{{ testResult }}</span>
      </div>
    </div>
  </FormDialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';
import FormDialog from 'src/components/FormDialog.vue';
import { useCameraStore } from 'src/stores/cameraStore';
import {
  CAMERA_BRANDS,
  cameraBrandHint,
  cameraBrandLabel,
  type Camera,
  type CameraBrand,
  type CameraForm,
} from 'src/types/camera';
import { apiErrorMessage } from 'src/utils/apiError';

const props = defineProps<{ modelValue: boolean; aquariumId: number; camera: Camera | null }>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [camera: Camera] }>();

const { t } = useI18n();
const $q = useQuasar();
const store = useCameraStore();
const saving = ref(false);
const testing = ref(false);
const testResult = ref('');
const testOk = ref(false);
const showPassword = ref(false);
// Chemins à saisir pour une caméra générique : section dépliée
const pathsOpen = ref(false);

const open = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

const empty = (): CameraForm => ({
  name: '',
  brand: 'tapo',
  host: '',
  port: 554,
  username: '',
  password: '',
  clear_password: false,
  main_path: '',
  sub_path: '',
  sort_order: 0,
});
const form = reactive<CameraForm>(empty());

const brandOptions = computed(() => CAMERA_BRANDS.map((value) => ({ value, label: cameraBrandLabel(value) })));
const brandHint = computed(() => cameraBrandHint(form.brand));

function applyPreset(brand: CameraBrand) {
  const presets = store.status?.presets ?? {};
  if (brand === 'rtsp') {
    // Chemins d'une autre marque laissés par le choix précédent : à ressaisir
    pathsOpen.value = true;
    const known = Object.values(presets).flatMap((p) => [p.main, p.sub]);
    if (known.includes(form.main_path)) form.main_path = '';
    if (known.includes(form.sub_path)) form.sub_path = '';
    return;
  }
  const preset = presets[brand];
  if (preset) {
    form.main_path = preset.main;
    form.sub_path = preset.sub;
  }
}

function reset() {
  testResult.value = '';
  showPassword.value = false;
  const c = props.camera;
  pathsOpen.value = c?.brand === 'rtsp';
  Object.assign(
    form,
    c
      ? {
          name: c.name,
          brand: c.brand,
          host: c.host,
          port: c.port,
          username: c.username,
          password: '',
          clear_password: false,
          main_path: c.main_path,
          sub_path: c.sub_path,
          sort_order: c.sort_order,
        }
      : empty(),
  );
  if (!c) applyPreset(form.brand);
}

async function test() {
  testing.value = true;
  testResult.value = '';
  try {
    testResult.value = await store.testCamera({
      camera_id: props.camera && !form.clear_password ? props.camera.id : null,
      host: form.host.trim(),
      port: form.port,
      username: form.username.trim(),
      password: form.password,
      path: form.main_path.trim() || form.sub_path.trim(),
    });
    testOk.value = true;
  } catch (err) {
    testResult.value = apiErrorMessage(err, t('cameras.form.testFailed'));
    testOk.value = false;
  } finally {
    testing.value = false;
  }
}

async function save() {
  if (!form.name.trim() || !form.host.trim()) return;
  saving.value = true;
  try {
    const saved = props.camera
      ? await store.updateCamera(props.camera.id, form)
      : await store.createCamera(props.aquariumId, form);
    $q.notify({ type: 'positive', message: props.camera ? t('cameras.form.updated') : t('cameras.form.added') });
    emit('saved', saved);
    open.value = false;
  } catch (err) {
    $q.notify({ type: 'negative', message: apiErrorMessage(err, t('cameras.form.saveFailed')) });
  } finally {
    saving.value = false;
  }
}
</script>
