// Must match backend app/models/commerce.py's ORDER_STATUSES/
// PAYMENT_STATUSES/FULFILLMENT_STATUSES exactly — these three state
// machines are independent (see that model's own comments): an order can
// be "processing" and still "unpaid", or "completed" with a manually
// recorded "paid" payment entered after the fact. No payment gateway is
// wired up yet, so payment/refund fields here are administrative records,
// not the result of real payment processing.
export const ORDER_STATUSES = ['pending', 'confirmed', 'processing', 'completed', 'cancelled', 'refunded']
export const ORDER_STATUS_TERMINAL = ['completed', 'cancelled', 'refunded']

export const PAYMENT_STATUSES = ['unpaid', 'pending', 'paid', 'failed', 'partially_refunded', 'refunded']
export const PAYMENT_STATUS_TERMINAL = ['refunded']

export const FULFILLMENT_STATUSES = ['not_applicable', 'unfulfilled', 'processing', 'shipped', 'delivered', 'cancelled']
