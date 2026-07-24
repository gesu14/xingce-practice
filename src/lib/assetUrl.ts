/** Prefix app assets with Vite base (e.g. `/xingce-practice/` on GitHub Pages). */
export function assetUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//i.test(path) || path.startsWith('data:')) return path;

  const base = import.meta.env.BASE_URL || '/';
  const raw = path.startsWith('/') ? path.slice(1) : path;
  const [pathname, query] = raw.split('?');
  const prefix = base.endsWith('/') ? base : `${base}/`;
  return `${prefix}${pathname}${query ? `?${query}` : ''}`;
}
