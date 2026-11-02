// Run with: node --test src/utils/money.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { minorToAmountString, pickDefaultPrice, pricesToPayload, validateAmountString, validatePriceRows } from './money.js'

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

test('default price preselection', () => {
  const prices = [{ currency: 'KES', checkoutAvailable: true }, { currency: 'USD', checkoutAvailable: false }]
  assert.equal(pickDefaultPrice(prices, 'USD').currency, 'USD')
  assert.equal(pickDefaultPrice(prices, 'EUR').currency, 'KES')
  assert.equal(pickDefaultPrice([], 'USD'), null)
})
