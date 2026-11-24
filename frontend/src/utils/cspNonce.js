// The per-request Content-Security-Policy nonce the server writes into the
// page (<meta name="csp-nonce">, backend app/services/security_headers.py).
// Passed to libraries that insert a <style> element at runtime so the CSP
// can stay style-src 'self' + nonce (no 'unsafe-inline').
export function readCspNonce(doc = typeof document !== 'undefined' ? document : null) {
  const value = doc?.querySelector?.('meta[name="csp-nonce"]')?.getAttribute('content')
  return value && /^[A-Za-z0-9_-]{16,64}$/.test(value) ? value : undefined
}
