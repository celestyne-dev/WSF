import { apiClient } from './client'

// WSF Checkout Phase 1 — normalizes both the public `prices` options
// (camelCase, with server-formatted text + checkoutAvailable +
// paymentMethods) and the admin dump's rows (same keys, plus every row
// regardless of `enabled`). Amounts stay exact: integer `amountMinor` and
// the server's decimal `amount` string — never a float.
export function mapPriceOptions(prices) {
  return (Array.isArray(prices) ? prices : []).map((p) => ({
    currency: p.currency,
    amountMinor: p.amountMinor,
    amount: p.amount ?? '',
    formatted: p.formatted || `${p.currency} ${p.amount ?? ''}`,
    enabled: p.enabled ?? true,
    checkoutAvailable: !!p.checkoutAvailable,
    paymentMethods: Array.isArray(p.paymentMethods) ? p.paymentMethods : [],
  }))
}

// GET /payments/config — non-secret: the ISO 4217 catalogue (code, name,
// symbol, minorUnit), the global default currency and enabled currencies.
export async function fetchPaymentConfig() {
  const { data } = await apiClient.get('/payments/config')
  return {
    defaultCurrency: data?.defaultCurrency || 'USD',
    enabledCurrencies: data?.enabledCurrencies || [],
    currencies: data?.currencies || [],
  }
}
