import { ref } from 'vue';
import { defineStore } from 'pinia';
import axios from 'axios';
import type { BackupInfo, BackupLocation, BackupPart, BackupSettings } from 'src/types/backup';

function triggerDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function filenameFromContentDisposition(header: string | undefined, fallback: string): string {
  const match = header?.match(/filename="?([^";]+)"?/);
  return match?.[1] ?? fallback;
}

function backupUrl(b: Pick<BackupInfo, 'location' | 'filename'>): string {
  return `/backup/${b.location}/${encodeURIComponent(b.filename)}`;
}

export const useBackupStore = defineStore('backup', () => {
  const backups = ref<BackupInfo[]>([]);
  const settings = ref<BackupSettings | null>(null);
  const loading = ref(false);

  async function fetchBackups() {
    loading.value = true;
    try {
      backups.value = (await axios.get<BackupInfo[]>('/backup/')).data;
    } finally {
      loading.value = false;
    }
  }

  async function fetchSettings() {
    settings.value = (await axios.get<BackupSettings>('/backup/settings')).data;
    return settings.value;
  }

  async function saveSettings(values: BackupSettings) {
    settings.value = (await axios.put<BackupSettings>('/backup/settings', values)).data;
    return settings.value;
  }

  async function testDestination(path: string) {
    return (await axios.post<{ ok: boolean; message: string }>('/backup/test-destination', { path })).data;
  }

  // Sauvegarde rangée sur le serveur (contenu / destination des réglages si absents)
  async function createBackup(parts?: BackupPart[], location?: BackupLocation) {
    const { data } = await axios.post<BackupInfo>('/backup/create', { parts, location });
    await fetchBackups();
    return data;
  }

  // Archive téléchargée directement, non conservée sur le serveur
  async function exportBackup(parts?: BackupPart[]) {
    const res = await axios.post('/backup/export', parts ? { parts } : {}, { responseType: 'blob' });
    triggerDownload(res.data as Blob, filenameFromContentDisposition(res.headers['content-disposition'] as string | undefined, 'aquarium_export.zip'));
  }

  async function downloadBackup(b: BackupInfo) {
    const res = await axios.get(backupUrl(b), { responseType: 'blob' });
    triggerDownload(res.data as Blob, b.filename);
  }

  async function deleteBackup(b: BackupInfo) {
    await axios.delete(backupUrl(b));
    backups.value = backups.value.filter((x) => !(x.filename === b.filename && x.location === b.location));
  }

  // Archive envoyée : vérifiée puis ajoutée à la liste (sans restauration)
  async function importBackup(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await axios.post<BackupInfo>('/backup/import', formData);
    await fetchBackups();
    return data;
  }

  async function restoreBackup(b: BackupInfo) {
    return (await axios.post<{ message: string }>(`${backupUrl(b)}/restore`)).data.message;
  }

  return {
    backups,
    settings,
    loading,
    fetchBackups,
    fetchSettings,
    saveSettings,
    testDestination,
    createBackup,
    exportBackup,
    downloadBackup,
    deleteBackup,
    importBackup,
    restoreBackup,
  };
});
