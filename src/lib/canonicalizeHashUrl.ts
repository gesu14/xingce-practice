/**
 * HashRouter only reads location.hash. Browser-style entry URLs such as
 * `/quiz?mode=sprint&pack=…` leave path/query *outside* the hash. Later in-app
 * navigation only updates `#/…`, producing contaminated addresses like:
 * `/quiz?pack=sprint-02#/quiz?pack=sprint-01`.
 *
 * Rewrite outer path+search into the hash (or keep an existing hash route) and
 * clear the outer path so the address bar stays canonical: `/#/…`.
 */

function normalizeBase(baseUrl: string): string {
  if (!baseUrl || baseUrl === '/') return '/';
  return baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
}

/** Path relative to Vite base, always starting with `/`. */
function pathRelativeToBase(pathname: string, base: string): string | null {
  if (base === '/') return pathname.startsWith('/') ? pathname : `/${pathname}`;

  const baseNoSlash = base.slice(0, -1);
  if (pathname === baseNoSlash || pathname === base) return '/';
  if (pathname.startsWith(`${baseNoSlash}/`)) {
    const rest = pathname.slice(baseNoSlash.length);
    return rest.startsWith('/') ? rest : `/${rest}`;
  }
  return null;
}

function normalizeHash(hash: string): string {
  if (!hash || hash === '#') return '';
  if (hash === '#/') return '#/';
  if (hash.startsWith('#/')) return hash;
  if (hash.startsWith('#')) return `#/${hash.slice(1)}`;
  return `#/${hash}`;
}

/**
 * @returns Canonical path+hash for replaceState, or `null` if already clean.
 */
export function resolveCanonicalHashUrl(
  pathname: string,
  search: string,
  hash: string,
  baseUrl: string = '/',
): string | null {
  const base = normalizeBase(baseUrl);
  const relative = pathRelativeToBase(pathname, base);
  if (relative === null) return null;

  const outerIsRoot = relative === '/' || relative === '';
  const hasOuterRoute = !outerIsRoot || Boolean(search);
  if (!hasOuterRoute) return null;

  const existing = normalizeHash(hash);
  const nextHash =
    existing && existing !== '#/'
      ? existing
      : `#${outerIsRoot ? '/' : relative}${search}`;

  return `${base}${nextHash}`;
}

/** Run once before React mounts so HashRouter sees a clean location. */
export function canonicalizeHashUrl(): void {
  const next = resolveCanonicalHashUrl(
    window.location.pathname,
    window.location.search,
    window.location.hash,
    import.meta.env.BASE_URL || '/',
  );
  if (!next) return;

  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (current === next) return;

  window.history.replaceState(window.history.state, '', next);
}
