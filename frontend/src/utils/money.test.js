// Run with: node --test src/utils/money.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  canCheckoutPrice,
  minorToAmountString,
  pickDefaultPrice,
  priceSelectorOptions,
  pricesToPayload,
  selectedPriceOption,
  validateAmountString,
  validatePriceRows,
} from './money.js'

const CATALOGUE = [
  { code: 'USD', minorUnit: 2 },
  { code: 'KES', minorUnit: 2 },
  { code: 'JPY', minorUnit: 0 },
]

test('amount validation never rounds', () => {
  assert.equal(validateAmountString('19.99', 2), null)
  assert.equal(validateAmountString('2500', 0), null)
  assert.match(validateAmountString('19.999', 2), /at most 2 decimal places/)
  assert.match(validateAmountString('25.5', 0), /no decimal places/)
  assert.match(validateAmountString('-5', 2), /positive number/)
  assert.match(validateAmountString('0.00', 2), /greater than zero/)
  assert.match(validateAmountString('1e3', 2), /positive number/)
  assert.match(validateAmountString('', 2), /Enter an amount/)
})

test('minor units to exact strings with no float math', () => {
  assert.equal(minorToAmountString(1999, 2), '19.99')
  assert.equal(minorToAmountString(250000, 2), '2500.00')
  assert.equal(minorToAmountString(5, 2), '0.05')
  assert.equal(minorToAmountString(2500, 0), '2500')
})

test('price rows: duplicates, unknown currency, enabled requirement', () => {
  assert.equal(validatePriceRows([{ currency: 'USD', amount: '20', enabled: true }, { currency: 'KES', amount: '2500', enabled: true }], CATALOGUE), null)
  assert.match(validatePriceRows([{ currency: 'USD', amount: '1' }, { currency: 'USD', amount: '2' }], CATALOGUE), /more than once/)
  assert.match(validatePriceRows([{ currency: 'ZZZ', amount: '1' }], CATALOGUE), /choose a currency/)
  assert.match(validatePriceRows([{ currency: 'USD', amount: '1', enabled: false }], CATALOGUE, { requireEnabled: true }), /Enable at least one/)
  assert.deepEqual(pricesToPayload([{ currency: 'USD', amount: ' 19.99 ', enabled: true }]), [{ currency: 'USD', amount: '19.99', enabled: true }])
})

test('default price preselection prefers a payable price (same order as the backend)', () => {
  const usdDown = [{ currency: 'USD', checkoutAvailable: false }, { currency: 'KES', checkoutAvailable: true }]
  assert.equal(pickDefaultPrice(usdDown, 'USD').currency, 'KES')
  const both = [{ currency: 'KES', checkoutAvailable: true }, { currency: 'USD', checkoutAvailable: true }]
  assert.equal(pickDefaultPrice(both, 'USD').currency, 'USD')
  const none = [{ currency: 'KES', checkoutAvailable: false }, { currency: 'USD', checkoutAvailable: false }]
  assert.equal(pickDefaultPrice(none, 'USD').currency, 'USD')
  assert.equal(pickDefaultPrice(none, 'EUR').currency, 'KES')
  assert.equal(pickDefaultPrice([], 'USD'), null)
})

test('unavailable currencies stay visible but disabled in the selector', () => {
  const options = priceSelectorOptions([
    { currency: 'USD', formatted: '$20.00', checkoutAvailable: false },
    { currency: 'KES', formatted: 'KES 2,500.00', checkoutAvailable: true },
  ])
  assert.deepEqual(options, [
    { value: 'USD', label: 'USD — $20.00 — unavailable online', disabled: true },
    { value: 'KES', label: 'KES — KES 2,500.00', disabled: false },
  ])
})

test('an unavailable selected or single price can never start checkout', () => {
  const single = [{ currency: 'USD', formatted: '$20.00', checkoutAvailable: false }]
  assert.equal(canCheckoutPrice(single, null, 'USD'), false)
  assert.equal(selectedPriceOption(single, null, 'USD').currency, 'USD') // still displayed
  const mixed = [{ currency: 'USD', checkoutAvailable: false }, { currency: 'KES', checkoutAvailable: true }]
  assert.equal(canCheckoutPrice(mixed, 'USD', 'USD'), false)
  assert.equal(canCheckoutPrice(mixed, null, 'USD'), true) // payable default = KES
  assert.equal(canCheckoutPrice(mixed, 'KES', 'USD'), true)
  assert.equal(canCheckoutPrice([], null, 'USD'), true) // legacy items: backend decides
})
