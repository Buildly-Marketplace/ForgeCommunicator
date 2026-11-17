// Photos picked for a free on-phone note live in the OS cache by default, which
// can be purged. Copy them into the app's document directory so notes keep them.

import { Directory, File, Paths } from 'expo-file-system';

import type { PendingCapture } from './types';

type Photo = PendingCapture['photos'][number];

function dirFor(clientId: string) {
  return new Directory(Paths.document, 'jottings', clientId);
}

export async function persistPhotos(clientId: string, photos: Photo[]): Promise<Photo[]> {
  if (!photos.length) return photos;
  const dir = dirFor(clientId);
  dir.create({ intermediates: true, idempotent: true });
  const out: Photo[] = [];
  for (const [i, photo] of photos.entries()) {
    if (photo.uri.startsWith(dir.uri)) {
      out.push(photo); // already persisted
      continue;
    }
    const dest = new File(dir, `${i}-${photo.name.replace(/[^\w.-]/g, '_')}`);
    try {
      await new File(photo.uri).copy(dest);
      out.push({ ...photo, uri: dest.uri });
    } catch {
      out.push(photo); // keep the original reference rather than losing the photo
    }
  }
  return out;
}

export function deletePhotos(clientId: string) {
  try {
    const dir = dirFor(clientId);
    if (dir.exists) dir.delete();
  } catch {
    // nothing to clean up
  }
}
