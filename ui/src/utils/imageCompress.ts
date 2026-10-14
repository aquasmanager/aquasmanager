/**
 * Photos prises au téléphone (4 à 8 Mo, 4000 px et plus) : réduites avant l'envoi
 * pour un envoi rapide et des sauvegardes légères. Une image déjà petite, ou qu'on
 * ne sait pas décoder (HEIC sur un navigateur qui ne le lit pas), part telle quelle.
 */

const MAX_SIDE = 2048;
const QUALITY = 0.85;
const SMALL_ENOUGH = 700 * 1024;

export async function compressImage(file: File, maxSide = MAX_SIDE): Promise<File> {
  if (!file.type.startsWith('image/') || file.type === 'image/gif' || file.type === 'image/svg+xml') return file;
  let bitmap: ImageBitmap;
  try {
    // Orientation EXIF appliquée (photo prise en portrait)
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    return file;
  }
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size <= SMALL_ENOUGH) {
    bitmap.close();
    return file;
  }
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    bitmap.close();
    return file;
  }
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY));
  if (!blob || blob.size >= file.size) return file;
  const name = file.name.replace(/\.[^.]+$/, '') + '.jpg';
  return new File([blob], name, { type: 'image/jpeg', lastModified: file.lastModified });
}

/** FormData « file » d'une photo, réduite si besoin. */
export async function photoFormData(file: File): Promise<FormData> {
  const formData = new FormData();
  formData.append('file', await compressImage(file));
  // Date du fichier d'origine (prise de vue pour une photo de la galerie) : la
  // compression efface les données EXIF
  if (file.lastModified) formData.append('taken_at', new Date(file.lastModified).toISOString());
  return formData;
}

/** Page photographiée (facture, certificat) : tournée de `quarterTurns` quarts de tour
 *  dans le sens horaire, réduite à 2000 px. */
export async function preparePage(file: File, quarterTurns = 0): Promise<Blob> {
  const turns = ((quarterTurns % 4) + 4) % 4;
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  } catch {
    return file;
  }
  const scale = Math.min(1, 2000 / Math.max(bitmap.width, bitmap.height));
  const w = Math.round(bitmap.width * scale);
  const h = Math.round(bitmap.height * scale);
  const canvas = document.createElement('canvas');
  canvas.width = turns % 2 ? h : w;
  canvas.height = turns % 2 ? w : h;
  const ctx = canvas.getContext('2d');
  if (!ctx) {
    bitmap.close();
    return file;
  }
  ctx.translate(canvas.width / 2, canvas.height / 2);
  ctx.rotate((turns * Math.PI) / 2);
  ctx.drawImage(bitmap, -w / 2, -h / 2, w, h);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', QUALITY));
  return blob ?? file;
}
