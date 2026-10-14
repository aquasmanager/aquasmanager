/**
 * Visionneuse de fichiers dans l'appli (PDF, images) : une seule fenêtre,
 * montée dans la mise en page, ouverte depuis n'importe quelle page. Évite
 * l'ouverture d'un onglet (bloquée ou transformée en téléchargement sur
 * téléphone, surtout dans l'appli installée).
 */
import { ref, shallowRef } from 'vue';
import { defineStore } from 'pinia';

export interface ViewedFile {
  title: string;
  // Nom proposé au téléchargement
  filename: string;
  // Type MIME attendu (le Blob reçu peut en porter un autre)
  contentType?: string;
  // Récupère le contenu (avec le jeton : les fichiers ne sont pas publics)
  load: () => Promise<Blob>;
}

export const useFileViewerStore = defineStore('fileViewer', () => {
  const open = ref(false);
  const file = shallowRef<ViewedFile | null>(null);

  function show(viewed: ViewedFile) {
    file.value = viewed;
    open.value = true;
  }

  return { open, file, show };
});
