// Lecture de QR codes avec l'API BarcodeDetector (Chrome / Android)

export interface BarcodeDetectorLike {
  detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]>;
}

declare global {
  interface Window {
    BarcodeDetector?: new (options: { formats: string[] }) => BarcodeDetectorLike;
  }
}

export function scannerAvailable(): boolean {
  return typeof window !== 'undefined' && !!window.BarcodeDetector && !!navigator.mediaDevices?.getUserMedia;
}

/** Référence de bouture lue dans un QR : lien « …/frags?ref=B-2026-0001 » ou référence seule. */
export function fragRefFromQr(value: string): string | null {
  try {
    const ref = new URL(value).searchParams.get('ref');
    if (ref) return ref;
  } catch {
    // pas une URL
  }
  const match = /B-\d{4}-\d{4,}/.exec(value);
  return match ? match[0] : null;
}
