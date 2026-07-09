import type { ExportResponse } from '@/shared/services/api/types';

/**
 * Turn a backend export payload into a browser download. Text formats arrive as
 * UTF-8 strings; PDF arrives base64-encoded.
 */
export function downloadExport(response: ExportResponse): void {
  const blob =
    response.encoding === 'base64'
      ? base64ToBlob(response.content, response.mediaType)
      : new Blob([response.content], { type: response.mediaType });

  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = response.filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function base64ToBlob(base64: string, mediaType: string): Blob {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mediaType });
}
