import { intlLocale, t } from 'src/i18n/instance';
import axios from 'axios';
import type { DocumentFile } from 'src/types/purchaseDocument';
import { useFileViewerStore } from 'src/stores/fileViewerStore';

async function fetchDocumentFile(documentId: number, file: DocumentFile): Promise<Blob> {
  const { data } = await axios.get<Blob>(`/purchase-documents/${documentId}/files/${file.id}`, { responseType: 'blob' });
  return new Blob([data], { type: file.content_type });
}

// Les fichiers ne sont servis qu'aux comptes connectés : récupérés avec le jeton,
// puis affichés dans la visionneuse de l'appli, ou enregistrés.
export async function openDocumentFile(documentId: number, file: DocumentFile, download = false): Promise<void> {
  if (!download) {
    useFileViewerStore().show({
      title: file.original_name,
      filename: file.original_name,
      contentType: file.content_type,
      load: () => fetchDocumentFile(documentId, file),
    });
    return;
  }
  const url = URL.createObjectURL(await fetchDocumentFile(documentId, file));
  const link = document.createElement('a');
  link.href = url;
  link.download = file.original_name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return t('documents.size.kb', { n: Math.max(1, Math.round(bytes / 1024)) });
  return t('documents.size.mb', { n: (bytes / 1024 / 1024).toLocaleString(intlLocale(), { maximumFractionDigits: 1 }) });
}

export function fileIcon(file: DocumentFile): string {
  return file.content_type === 'application/pdf' ? 'picture_as_pdf' : 'image';
}
