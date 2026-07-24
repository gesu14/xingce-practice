import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { canonicalizeHashUrl } from './lib/canonicalizeHashUrl';
import './index.css';

// HashRouter ignores path/query outside `#`. Fix pasted/bookmarked Browser-style
// URLs (and contaminated `/quiz?…#/quiz?…` leftovers) before the router mounts.
canonicalizeHashUrl();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
