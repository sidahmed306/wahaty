// Description de chaque page de l'espace connecté (liste, champs du formulaire, actions).
// Le composant ResourcePage s'occupe de l'affichage ; ici on dit seulement « quoi ».

import { api, apiUrl, tokens } from '../../api/client'
import { formatValue } from '../../components/ResourcePage'
import { formatMoney, formatNumber, localized, today } from '../../lib/format'

const name = (r, ctx) => localized(r, 'name', ctx.lang)
const isAgent = (ctx) => ctx.is('field_agent')
const isDirection = (ctx) => ctx.is('direction')
/** Écriture possible : pas la Direction (lecture seule sur les données privées). */
const canWrite = (ctx) => !isDirection(ctx)

const SOURCES = {
  varieties: { path: '/api/varieties/', label: name },
  oases: { path: '/api/oases/', label: name },
  farmers: { path: '/api/agent/farmers/', label: (r) => r.full_name },
  farms: {
    path: '/api/farms/',
    label: (r, ctx) => (isAgent(ctx) || isDirection(ctx) ? `${r.name} — ${r.owner_name}` : r.name),
  },
  products: { path: '/api/products/', label: (r) => r.name },
  suppliers: { path: '/api/suppliers/', label: (r) => r.name },
  customers: { path: '/api/customers/', label: (r) => r.name },
}

/** Agent de terrain : choisir l'agriculteur pour qui il saisit (à la création seulement). */
const ownerField = (ctx) => ({
  name: 'owner',
  label: ctx.t('fields.farmer'),
  type: 'select',
  source: SOURCES.farmers,
  when: isAgent,
  createOnly: true,
  required: true,
})

const ownerColumn = (ctx) => ({
  label: ctx.t('fields.farmer'),
  key: 'owner_name',
  show: (row, c) => isAgent(c) || isDirection(c),
})

const PAYMENT_METHODS = ['cash', 'bankily', 'masrvi', 'sedad', 'bank_transfer', 'other']
const methodOptions = (ctx) => PAYMENT_METHODS.map((m) => ({ value: m, label: ctx.t(`methods.${m}`) }))

// ---------------------------------------------------------------- Agriculteur

export const farms = {
  path: '/api/farms/',
  title: (ctx) => ctx.t('farms.title'),
  addLabel: (ctx) => ctx.t('farms.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row) => row.name,
  columnsFor: (ctx) => [
    ownerColumn(ctx),
    { label: ctx.t('fields.oasis'), render: (r) => name(r.oasis_detail, ctx) },
    { label: ctx.t('farms.totalPalms'), key: 'total_palms', type: 'number' },
    { label: ctx.t('farms.productive'), key: 'productive_palms', type: 'number' },
    { label: ctx.t('farms.young'), key: 'young_palms', type: 'number' },
    { label: ctx.t('fields.area'), key: 'area_hectares', type: 'number' },
  ],
  fields: (ctx) => [
    ownerField(ctx),
    { name: 'name', label: ctx.t('fields.name'), required: true },
    { name: 'oasis', label: ctx.t('fields.oasis'), type: 'select', source: SOURCES.oases, required: true },
    { name: 'area_hectares', label: ctx.t('fields.area'), type: 'number' },
    { name: 'latitude', label: ctx.t('fields.latitude'), type: 'number', help: ctx.t('fields.gpsHelp') },
    { name: 'longitude', label: ctx.t('fields.longitude'), type: 'number' },
  ],
}
/** Nom d'une ligne liée (ferme, fournisseur…) retrouvé dans les listes déjà chargées. */
const lookup = (ctx, source, id) => {
  const row = (ctx.sources?.[source.path] || []).find((r) => r.id === id)
  return row ? source.label(row, ctx) : `#${id}`
}

export const palmGroups = {
  path: '/api/palm-groups/',
  title: (ctx) => ctx.t('palms.title'),
  intro: (ctx) => ctx.t('palms.intro'),
  addLabel: (ctx) => ctx.t('palms.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row, ctx) => name(row.variety_detail, ctx),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.farm'), render: (r, c) => lookup(c, SOURCES.farms, r.farm) },
    { label: ctx.t('farms.productive'), key: 'productive_count', type: 'number' },
    { label: ctx.t('farms.young'), key: 'young_count', type: 'number' },
    { label: ctx.t('farms.totalPalms'), key: 'total_count', type: 'number' },
  ],
  fields: (ctx) => [
    { name: 'farm', label: ctx.t('fields.farm'), type: 'select', source: SOURCES.farms, required: true },
    { name: 'variety', label: ctx.t('fields.variety'), type: 'select', source: SOURCES.varieties, required: true },
    { name: 'productive_count', label: ctx.t('farms.productive'), type: 'number', default: '0', required: true },
    { name: 'young_count', label: ctx.t('farms.young'), type: 'number', default: '0', required: true },
  ],
}

export const harvests = {
  path: '/api/harvests/',
  title: (ctx) => ctx.t('harvests.title'),
  addLabel: (ctx) => ctx.t('harvests.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row, ctx) => `${name(row.variety_detail, ctx)} · ${row.season}`,
  columnsFor: (ctx) => [
    { label: ctx.t('fields.farm'), render: (r, c) => lookup(c, SOURCES.farms, r.farm) },
    { label: ctx.t('fields.date'), key: 'harvest_date', type: 'date' },
    { label: ctx.t('fields.quantityKg'), key: 'quantity_kg', type: 'kg' },
    { label: ctx.t('harvests.season'), key: 'season' },
    { label: ctx.t('fields.notes'), key: 'notes' },
  ],
  fields: (ctx) => [
    { name: 'farm', label: ctx.t('fields.farm'), type: 'select', source: SOURCES.farms, required: true },
    { name: 'variety', label: ctx.t('fields.variety'), type: 'select', source: SOURCES.varieties, required: true },
    { name: 'harvest_date', label: ctx.t('fields.date'), type: 'date', default: today, required: true },
    { name: 'quantity_kg', label: ctx.t('fields.quantityKg'), type: 'kg', required: true },
    { name: 'season', label: ctx.t('harvests.season'), type: 'number', help: ctx.t('harvests.seasonHelp') },
    { name: 'notes', label: ctx.t('fields.notes'), type: 'textarea' },
  ],
}

export const sales = {
  path: '/api/sales/',
  title: (ctx) => ctx.t('sales.title'),
  addLabel: (ctx) => ctx.t('sales.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row, ctx) => formatValue(row.total_amount, 'money', ctx),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.date'), key: 'sale_date', type: 'date' },
    { label: ctx.t('fields.variety'), render: (r) => name(r.variety_detail, ctx) || '—' },
    { label: ctx.t('fields.quantityKg'), key: 'quantity_kg', type: 'kg' },
    { label: ctx.t('fields.pricePerKg'), key: 'unit_price', type: 'money' },
    { label: ctx.t('sales.buyer'), key: 'buyer_name' },
  ],
  fields: (ctx) => [
    ownerField(ctx),
    { name: 'sale_date', label: ctx.t('fields.date'), type: 'date', default: today, required: true },
    { name: 'variety', label: ctx.t('fields.variety'), type: 'select', source: SOURCES.varieties },
    { name: 'farm', label: ctx.t('fields.farm'), type: 'select', source: SOURCES.farms },
    { name: 'quantity_kg', label: ctx.t('fields.quantityKg'), type: 'kg', required: true },
    { name: 'unit_price', label: ctx.t('fields.pricePerKg'), type: 'money', required: true },
    { name: 'buyer_name', label: ctx.t('sales.buyer') },
    { name: 'notes', label: ctx.t('fields.notes'), type: 'textarea' },
  ],
}

export const expenses = {
  path: '/api/expenses/',
  title: (ctx) => ctx.t('expenses.title'),
  addLabel: (ctx) => ctx.t('expenses.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row, ctx) => formatValue(row.amount, 'money', ctx),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.date'), key: 'expense_date', type: 'date' },
    { label: ctx.t('fields.category'), render: (r) => name(r.category_detail, ctx) },
    { label: ctx.t('fields.description'), key: 'description' },
  ],
  fields: (ctx) => [
    ownerField(ctx),
    { name: 'expense_date', label: ctx.t('fields.date'), type: 'date', default: today, required: true },
    {
      name: 'category',
      label: ctx.t('fields.category'),
      type: 'select',
      required: true,
      source: {
        path: '/api/expense-categories/',
        label: name,
        filter: (c, form, ctx2) => c.applies_to === 'both' || ctx2.is(c.applies_to) || isAgent(ctx2),
      },
    },
    { name: 'amount', label: ctx.t('fields.amount'), type: 'money', required: true },
    {
      name: 'farm',
      label: ctx.t('fields.farm'),
      type: 'select',
      source: SOURCES.farms,
      when: (c) => c.is('farmer') || isAgent(c),
    },
    { name: 'description', label: ctx.t('fields.description'), type: 'textarea' },
  ],
}

// ---------------------------------------------------------------- Vendeur

const UNITS = ['kg', 'box', 'bag', 'piece']

export const products = {
  path: '/api/products/',
  title: (ctx) => ctx.t('products.title'),
  addLabel: (ctx) => ctx.t('products.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row) => row.name,
  badge: (row) => (row.is_low_stock ? { value: 'low', group: 'stock' } : null),
  columnsFor: (ctx) => [
    {
      label: ctx.t('products.stock'),
      render: (r) => (
        <span className="num">
          {formatValue(r.stock, 'number', ctx)} {ctx.t(`units.${r.unit}`)}
        </span>
      ),
    },
    { label: ctx.t('products.salePrice'), key: 'sale_price', type: 'money' },
    { label: ctx.t('products.threshold'), key: 'low_stock_threshold', type: 'number' },
  ],
  fields: (ctx) => [
    { name: 'name', label: ctx.t('fields.name'), required: true },
    { name: 'variety', label: ctx.t('fields.variety'), type: 'select', source: SOURCES.varieties },
    {
      name: 'unit',
      label: ctx.t('products.unit'),
      type: 'select',
      required: true,
      default: 'kg',
      options: (c) => UNITS.map((u) => ({ value: u, label: c.t(`units.${u}`) })),
    },
    { name: 'sale_price', label: ctx.t('products.salePrice'), type: 'money' },
    { name: 'low_stock_threshold', label: ctx.t('products.threshold'), type: 'number', help: ctx.t('products.thresholdHelp') },
  ],
}

export const stockMovements = {
  path: '/api/stock-movements/',
  title: (ctx) => ctx.t('movements.title'),
  intro: (ctx) => ctx.t('movements.intro'),
  addLabel: (ctx) => ctx.t('movements.add'),
  canCreate: canWrite,
  titleOf: (row) => row.product_name,
  badge: (row) => ({ value: row.kind, group: 'movementKinds' }),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.quantity'), key: 'quantity', type: 'number' },
    { label: ctx.t('fields.date'), key: 'movement_date', type: 'datetime' },
    { label: ctx.t('fields.notes'), key: 'note' },
  ],
  fields: (ctx) => [
    { name: 'product', label: ctx.t('fields.product'), type: 'select', source: SOURCES.products, required: true },
    {
      name: 'kind',
      label: ctx.t('movements.kind'),
      type: 'select',
      required: true,
      options: (c) => ['adjust_in', 'loss', 'adjust_out'].map((k) => ({ value: k, label: c.t(`movementKinds.${k}`) })),
    },
    { name: 'quantity', label: ctx.t('fields.quantity'), type: 'number', required: true },
    { name: 'note', label: ctx.t('movements.why'), type: 'textarea', required: true },
  ],
}

export const suppliers = {
  path: '/api/suppliers/',
  title: (ctx) => ctx.t('suppliers.title'),
  addLabel: (ctx) => ctx.t('suppliers.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row) => row.name,
  columnsFor: (ctx) => [
    { label: ctx.t('fields.phone'), key: 'phone', type: 'phone' },
    { label: ctx.t('suppliers.purchases'), key: 'purchases_total', type: 'money' },
    { label: ctx.t('suppliers.paid'), key: 'paid_total', type: 'money' },
    { label: ctx.t('suppliers.balance'), key: 'balance', type: 'money' },
  ],
  fields: (ctx) => [
    { name: 'name', label: ctx.t('fields.name'), required: true },
    { name: 'phone', label: ctx.t('fields.phone'), type: 'tel' },
    { name: 'oasis', label: ctx.t('fields.oasis'), type: 'select', source: SOURCES.oases },
    { name: 'notes', label: ctx.t('fields.notes'), type: 'textarea' },
  ],
}

export const purchases = {
  path: '/api/purchases/',
  title: (ctx) => ctx.t('purchases.title'),
  intro: (ctx) => ctx.t('purchases.intro'),
  addLabel: (ctx) => ctx.t('purchases.add'),
  canCreate: canWrite,
  titleOf: (row, ctx) => `${row.supplier_name} · ${formatValue(row.purchase_date, 'date', ctx)}`,
  badge: (row) => (row.cancelled_at ? { value: 'cancelled', group: 'orderStatus' } : null),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.total'), key: 'total_amount', type: 'money' },
    { label: ctx.t('purchases.reference'), key: 'reference' },
    {
      label: ctx.t('purchases.items'),
      render: (r) => r.items.map((i) => `${i.product_name} × ${formatNumber(i.quantity, ctx.lang)}`).join(' ، '),
    },
    { label: ctx.t('purchases.cancelReason'), key: 'cancel_reason', show: (r) => Boolean(r.cancelled_at) },
  ],
  fields: (ctx) => [
    { name: 'supplier', label: ctx.t('fields.supplier'), type: 'select', source: SOURCES.suppliers, required: true },
    { name: 'purchase_date', label: ctx.t('fields.date'), type: 'date', default: today, required: true },
    { name: 'reference', label: ctx.t('purchases.reference') },
    { name: 'lines', label: ctx.t('purchases.items'), type: 'lines', source: SOURCES.products, priceKey: 'unit_cost' },
  ],
  actionsFor: (ctx) => [
    {
      label: ctx.t('purchases.cancel'),
      tone: 'danger',
      show: (row, c) => !row.cancelled_at && canWrite(c),
      input: ctx.t('purchases.cancelReason'),
      run: (row, c, reason) => api(`/api/purchases/${row.id}/cancel/`, { method: 'POST', body: { reason } }),
    },
  ],
}

export const supplierPayments = {
  path: '/api/supplier-payments/',
  title: (ctx) => ctx.t('supplierPayments.title'),
  addLabel: (ctx) => ctx.t('supplierPayments.add'),
  canCreate: canWrite,
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row, ctx) => formatValue(row.amount, 'money', ctx),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.supplier'), render: (r, c) => lookup(c, SOURCES.suppliers, r.supplier) },
    { label: ctx.t('fields.date'), key: 'payment_date', type: 'date' },
    { label: ctx.t('fields.method'), render: (r) => ctx.t(`methods.${r.method}`) },
    { label: ctx.t('fields.reference'), key: 'reference' },
  ],
  fields: (ctx) => [
    { name: 'supplier', label: ctx.t('fields.supplier'), type: 'select', source: SOURCES.suppliers, required: true },
    {
      name: 'purchase',
      label: ctx.t('supplierPayments.purchase'),
      type: 'select',
      source: {
        path: '/api/purchases/',
        label: (r, c) => `${formatValue(r.purchase_date, 'date', c)} · ${r.reference || '#' + r.id}`,
        filter: (r, form) => !r.cancelled_at && String(r.supplier) === String(form.supplier),
      },
    },
    { name: 'payment_date', label: ctx.t('fields.date'), type: 'date', default: today, required: true },
    { name: 'amount', label: ctx.t('fields.amount'), type: 'money', required: true },
    { name: 'method', label: ctx.t('fields.method'), type: 'select', options: methodOptions, default: 'cash', required: true },
    { name: 'reference', label: ctx.t('fields.reference') },
  ],
}

export const customers = {
  path: '/api/customers/',
  title: (ctx) => ctx.t('customers.title'),
  addLabel: (ctx) => ctx.t('customers.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx),
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row) => row.name,
  badge: (row) => ({ value: row.segment, group: 'segments' }),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.phone'), key: 'phone', type: 'phone' },
    { label: ctx.t('customers.orders'), key: 'orders_count', type: 'number' },
    { label: ctx.t('customers.purchased'), key: 'total_purchased', type: 'money' },
    { label: ctx.t('customers.paid'), key: 'paid_total', type: 'money' },
    {
      label: ctx.t('customers.balance'),
      render: (r) =>
        Number(r.balance) < 0 ? (
          <span>
            {ctx.t('customers.advance')} {formatValue(String(-Number(r.balance)), 'money', ctx)}
          </span>
        ) : (
          formatValue(r.balance, 'money', ctx)
        ),
    },
    { label: ctx.t('customers.lastOrder'), key: 'last_order_date', type: 'date' },
  ],
  fields: (ctx) => [
    { name: 'name', label: ctx.t('fields.name'), required: true },
    { name: 'phone', label: ctx.t('fields.phone'), type: 'tel' },
    { name: 'whatsapp', label: ctx.t('fields.whatsapp'), type: 'tel' },
    { name: 'city', label: ctx.t('fields.city') },
    { name: 'address', label: ctx.t('fields.address') },
    { name: 'notes', label: ctx.t('fields.notes'), type: 'textarea' },
  ],
}

export const customerPayments = {
  path: '/api/customer-payments/',
  title: (ctx) => ctx.t('customerPayments.title'),
  addLabel: (ctx) => ctx.t('customerPayments.add'),
  canCreate: canWrite,
  canDelete: (row, ctx) => canWrite(ctx),
  titleOf: (row, ctx) => `${row.customer_name} · ${formatMoney(row.amount, ctx.lang)}`,
  columnsFor: (ctx) => [
    { label: ctx.t('fields.date'), key: 'payment_date', type: 'date' },
    { label: ctx.t('fields.method'), render: (r) => ctx.t(`methods.${r.method}`) },
    { label: ctx.t('fields.reference'), key: 'reference' },
  ],
  fields: (ctx) => [
    { name: 'customer', label: ctx.t('fields.customer'), type: 'select', source: SOURCES.customers, required: true },
    {
      name: 'order',
      label: ctx.t('customerPayments.order'),
      type: 'select',
      source: {
        path: '/api/orders/',
        label: (r, c) => `${r.number} · ${formatMoney(r.total_amount, c.lang)}`,
        filter: (r, form) => r.status !== 'cancelled' && String(r.customer) === String(form.customer),
      },
    },
    { name: 'payment_date', label: ctx.t('fields.date'), type: 'date', default: today, required: true },
    { name: 'amount', label: ctx.t('fields.amount'), type: 'money', required: true },
    { name: 'method', label: ctx.t('fields.method'), type: 'select', options: methodOptions, default: 'cash', required: true },
    { name: 'reference', label: ctx.t('fields.reference') },
  ],
}

const NEXT_STATUS = {
  received: ['confirmed'],
  confirmed: ['prepared'],
  prepared: ['out_for_delivery'],
  out_for_delivery: ['delivered'],
}
const CANCELLABLE = ['received', 'confirmed', 'prepared']

const changeStatus = (status) => (row, ctx, reason) =>
  api(`/api/orders/${row.id}/status/`, {
    method: 'POST',
    body: status === 'cancelled' ? { status, cancel_reason: reason } : { status },
  })

export const orders = {
  path: '/api/orders/',
  title: (ctx) => ctx.t('orders.title'),
  addLabel: (ctx) => ctx.t('orders.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx) && row.status === 'received',
  titleOf: (row) => `${row.number} · ${row.customer_name}`,
  badge: (row) => (row.is_late ? { value: 'late', group: 'orderStatus' } : { value: row.status, group: 'orderStatus' }),
  filtersFor: (ctx) => [
    {
      name: 'status',
      label: ctx.t('orders.status'),
      type: 'select',
      options: ['received', 'confirmed', 'prepared', 'out_for_delivery', 'delivered', 'cancelled'].map((s) => ({
        value: s,
        label: ctx.t(`orderStatus.${s}`),
      })),
    },
    {
      name: 'late',
      label: ctx.t('orders.lateOnly'),
      type: 'select',
      options: [{ value: 'true', label: ctx.t('common.yes') }],
    },
  ],
  columnsFor: (ctx) => [
    { label: ctx.t('orders.status'), render: (r) => ctx.t(`orderStatus.${r.status}`) },
    { label: ctx.t('fields.total'), key: 'total_amount', type: 'money' },
    { label: ctx.t('orders.orderDate'), key: 'order_date', type: 'date' },
    { label: ctx.t('orders.expected'), key: 'expected_delivery_date', type: 'date' },
    {
      label: ctx.t('orders.late'),
      show: (r) => r.is_late,
      render: (r) => ctx.t('orders.daysLate', { count: r.days_late }),
    },
  ],
  fields: (ctx) => [
    { name: 'customer', label: ctx.t('fields.customer'), type: 'select', source: SOURCES.customers, required: true },
    { name: 'order_date', label: ctx.t('orders.orderDate'), type: 'date', default: today },
    { name: 'expected_delivery_date', label: ctx.t('orders.expected'), type: 'date' },
    { name: 'delivery_address', label: ctx.t('fields.address') },
    { name: 'delivery_fee', label: ctx.t('orders.deliveryFee'), type: 'money', default: '0' },
    { name: 'discount', label: ctx.t('orders.discount'), type: 'money', default: '0' },
    {
      name: 'items',
      label: ctx.t('orders.items'),
      type: 'lines',
      source: SOURCES.products,
      priceKey: 'unit_price',
      fromRow: (row) => row.lines.map((l) => ({ product: String(l.product), quantity: l.quantity, unit_price: l.unit_price })),
    },
    { name: 'notes', label: ctx.t('fields.notes'), type: 'textarea' },
  ],
  detail: (row, ctx) => (
    <div className="stack">
      <div className="table-wrap">
        <table className="simple">
          <thead>
            <tr>
              <th>{ctx.t('fields.product')}</th>
              <th>{ctx.t('fields.quantity')}</th>
              <th>{ctx.t('fields.unitPrice')}</th>
              <th>{ctx.t('fields.total')}</th>
            </tr>
          </thead>
          <tbody>
            {row.lines.map((l) => (
              <tr key={l.id}>
                <td>{l.product_name}</td>
                <td>{formatValue(l.quantity, 'number', ctx)}</td>
                <td>{formatValue(l.unit_price, 'money', ctx)}</td>
                <td>{formatValue(l.line_total, 'money', ctx)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="small">
        {ctx.t('orders.subtotal')} {formatValue(row.subtotal, 'money', ctx)} · {ctx.t('orders.deliveryFee')}{' '}
        {formatValue(row.delivery_fee, 'money', ctx)} · {ctx.t('orders.discount')} {formatValue(row.discount, 'money', ctx)}
      </div>
      {row.cancel_reason && (
        <div className="alert">
          {ctx.t('orders.cancelReason')} : {row.cancel_reason}
        </div>
      )}
      <div>
        <strong>{ctx.t('orders.history')}</strong>
        <ul className="small">
          {row.history.map((h, i) => (
            <li key={i}>
              {formatValue(h.changed_at, 'datetime', ctx)} — {h.from_status ? ctx.t(`orderStatus.${h.from_status}`) + ' → ' : ''}
              {ctx.t(`orderStatus.${h.to_status}`)} {h.changed_by_name ? `(${h.changed_by_name})` : ''}
            </li>
          ))}
        </ul>
      </div>
    </div>
  ),
}

orders.actionsFor = (ctx) => [
  ...['confirmed', 'prepared', 'out_for_delivery', 'delivered'].map((status) => ({
    label: ctx.t(`orders.to.${status}`),
    tone: 'primary',
    show: (row, c) => canWrite(c) && NEXT_STATUS[row.status]?.includes(status),
    confirm: status === 'delivered' ? ctx.t('orders.confirmDeliver') : undefined,
    run: changeStatus(status),
  })),
  {
    label: ctx.t('orders.makeInvoice'),
    show: (row, c) => canWrite(c) && !['received', 'cancelled'].includes(row.status),
    run: (row) => api('/api/invoices/', { method: 'POST', body: { order: row.id } }),
    message: (invoice, c) => c.t('orders.invoiceCreated', { number: invoice.number }),
  },
  {
    label: ctx.t('orders.cancel'),
    tone: 'danger',
    show: (row, c) => canWrite(c) && CANCELLABLE.includes(row.status),
    input: ctx.t('orders.cancelReason'),
    run: changeStatus('cancelled'),
  },
]

/** Ouvre le PDF (la demande doit porter le jeton de connexion : pas un simple lien). */
export async function openInvoicePdf(invoice) {
  const win = window.open('', '_blank')
  const response = await fetch(apiUrl(`/api/invoices/${invoice.id}/pdf/`), {
    headers: { Authorization: `Bearer ${tokens.access}` },
  })
  if (!response.ok) {
    win?.close()
    throw new Error(`PDF ${response.status}`)
  }
  const url = URL.createObjectURL(await response.blob())
  if (win) win.location.href = url
  else window.location.href = url
}

export const invoices = {
  path: '/api/invoices/',
  title: (ctx) => ctx.t('invoices.title'),
  intro: (ctx) => ctx.t('invoices.intro'),
  addLabel: (ctx) => ctx.t('invoices.add'),
  canCreate: canWrite,
  titleOf: (row) => `${row.number} · ${row.customer_snapshot?.name || ''}`,
  badge: (row) => ({ value: row.status, group: 'invoiceStatus' }),
  columnsFor: (ctx) => [
    { label: ctx.t('invoices.order'), key: 'order_number' },
    { label: ctx.t('fields.date'), key: 'issue_date', type: 'date' },
    { label: ctx.t('fields.total'), key: 'total_amount', type: 'money' },
    { label: ctx.t('invoices.cancelReason'), key: 'cancel_reason', show: (r) => r.status === 'cancelled' },
  ],
  fields: (ctx) => [
    {
      name: 'order',
      label: ctx.t('invoices.order'),
      type: 'select',
      required: true,
      source: {
        path: '/api/orders/',
        label: (r, c) => `${r.number} · ${r.customer_name} · ${formatMoney(r.total_amount, c.lang)}`,
        filter: (r) => !['received', 'cancelled'].includes(r.status),
      },
    },
  ],
  afterSave: (row, ctx) => ctx.t('orders.invoiceCreated', { number: row.number }),
}

invoices.actionsFor = (ctx) => [
  { label: ctx.t('invoices.pdf'), tone: 'primary', run: (row) => openInvoicePdf(row), message: () => ctx.t('invoices.pdfOpened') },
  {
    label: ctx.t('invoices.cancel'),
    tone: 'danger',
    show: (row, c) => row.status === 'issued' && canWrite(c),
    input: ctx.t('invoices.cancelReason'),
    run: (row, c, reason) => api(`/api/invoices/${row.id}/cancel/`, { method: 'POST', body: { reason } }),
  },
]

// ---------------------------------------------------------------- Marché

export const myListings = {
  path: '/api/market/my-listings/',
  title: (ctx) => ctx.t('listings.title'),
  intro: (ctx) => ctx.t('listings.intro'),
  addLabel: (ctx) => ctx.t('listings.add'),
  canCreate: canWrite,
  canEdit: (row, ctx) => canWrite(ctx) && row.is_editable,
  canDelete: (row, ctx) => canWrite(ctx) && row.status !== 'pending',
  titleOf: (row) => row.title,
  badge: (row) => ({ value: row.status, group: 'listingStatus' }),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.variety'), render: (r) => name(r.variety_detail, ctx) },
    { label: ctx.t('fields.oasis'), render: (r) => name(r.oasis_detail, ctx) },
    { label: ctx.t('fields.pricePerKg'), key: 'price_per_kg', type: 'money' },
    { label: ctx.t('fields.quantityKg'), key: 'quantity_kg', type: 'kg' },
    { label: ctx.t('listings.photos'), render: (r) => String(r.photos.length) },
    { label: ctx.t('listings.rejection'), key: 'rejection_reason', show: (r) => r.status === 'rejected' },
  ],
  fields: (ctx) => [
    { name: 'title', label: ctx.t('listings.titleField'), required: true },
    { name: 'variety', label: ctx.t('fields.variety'), type: 'select', source: SOURCES.varieties, required: true },
    { name: 'oasis', label: ctx.t('fields.oasis'), type: 'select', source: SOURCES.oases, required: true },
    { name: 'price_per_kg', label: ctx.t('fields.pricePerKg'), type: 'money', required: true },
    { name: 'quantity_kg', label: ctx.t('fields.quantityKg'), type: 'kg', required: true },
    { name: 'contact_phone', label: ctx.t('listings.contactPhone'), type: 'tel', help: ctx.t('listings.contactHelp') },
    { name: 'whatsapp_phone', label: ctx.t('fields.whatsapp'), type: 'tel' },
    { name: 'description', label: ctx.t('fields.description'), type: 'textarea' },
  ],
  toPayload: (body) => {
    const out = { ...body }
    if (!out.contact_phone) delete out.contact_phone
    return out
  },
}

myListings.actionsFor = (ctx) => [
  {
    label: ctx.t('listings.submit'),
    tone: 'primary',
    show: (row, c) => canWrite(c) && ['draft', 'rejected'].includes(row.status),
    run: (row) => api(`/api/market/my-listings/${row.id}/submit/`, { method: 'POST' }),
    message: () => ctx.t('listings.submitted'),
  },
  {
    label: ctx.t('listings.unpublish'),
    show: (row, c) => canWrite(c) && ['published', 'pending'].includes(row.status),
    run: (row) => api(`/api/market/my-listings/${row.id}/unpublish/`, { method: 'POST' }),
  },
  {
    label: ctx.t('listings.markSold'),
    show: (row, c) => canWrite(c) && row.status === 'published',
    confirm: ctx.t('listings.confirmSold'),
    run: (row) => api(`/api/market/my-listings/${row.id}/sold/`, { method: 'POST' }),
  },
]

// ---------------------------------------------------------------- Agent de terrain

export const agentFarmers = {
  path: '/api/agent/farmers/',
  title: (ctx) => ctx.t('agent.title'),
  intro: (ctx) => ctx.t('agent.intro'),
  addLabel: (ctx) => ctx.t('agent.add'),
  titleOf: (row) => row.full_name,
  badge: (row) => ({ value: row.status, group: 'accountStatus' }),
  columnsFor: (ctx) => [
    { label: ctx.t('fields.phone'), key: 'phone', type: 'phone' },
    { label: ctx.t('agent.registeredOn'), key: 'date_joined', type: 'date' },
    {
      label: ctx.t('agent.access'),
      render: (r) => (r.can_edit ? ctx.t('agent.canEdit') : ctx.t('agent.readOnly')),
    },
  ],
  fields: (ctx) => [
    { name: 'full_name', label: ctx.t('fields.fullName'), required: true },
    { name: 'phone', label: ctx.t('fields.phone'), type: 'tel', required: true },
    { name: 'oasis', label: ctx.t('fields.oasis'), type: 'select', source: SOURCES.oases },
    {
      name: 'preferred_language',
      label: ctx.t('fields.language'),
      type: 'select',
      default: 'ar',
      required: true,
      options: [
        { value: 'ar', label: 'العربية' },
        { value: 'fr', label: 'Français' },
      ],
    },
  ],
  afterSave: (row, ctx) => ctx.t('agent.codeMessage', { code: row.claim_code, date: formatValue(row.claim_code_expires_at, 'date', ctx) }),
}

agentFarmers.actionsFor = (ctx) => [
  {
    label: ctx.t('agent.newCode'),
    show: (row) => row.can_edit,
    confirm: ctx.t('agent.newCodeConfirm'),
    run: (row) => api(`/api/agent/farmers/${row.id}/claim-code/`, { method: 'POST' }),
    message: (result, c) => c.t('agent.codeMessage', { code: result.claim_code, date: formatValue(result.claim_code_expires_at, 'date', c) }),
  },
]

// ---------------------------------------------------------------- Direction

export const users = {
  path: '/api/users/',
  title: (ctx) => ctx.t('users.title'),
  titleOf: (row) => row.full_name,
  badge: (row) => ({ value: row.status, group: 'accountStatus' }),
  filtersFor: (ctx) => [
    {
      name: 'status',
      label: ctx.t('users.status'),
      type: 'select',
      options: ['pending', 'approved', 'suspended'].map((s) => ({ value: s, label: ctx.t(`accountStatus.${s}`) })),
    },
    {
      name: 'role',
      label: ctx.t('users.role'),
      type: 'select',
      options: ['farmer', 'seller', 'field_agent', 'direction'].map((r) => ({ value: r, label: ctx.t(`roles.${r}`) })),
    },
    { name: 'search', label: ctx.t('common.search'), type: 'text' },
  ],
  columnsFor: (ctx) => [
    { label: ctx.t('fields.phone'), key: 'phone', type: 'phone' },
    { label: ctx.t('users.roles'), render: (r) => r.roles.map((x) => ctx.t(`roles.${x}`)).join(' + ') },
    { label: ctx.t('users.joined'), key: 'date_joined', type: 'date' },
    { label: ctx.t('users.lastLogin'), key: 'last_login', type: 'datetime' },
  ],
}

users.actionsFor = (ctx) => [
  {
    label: ctx.t('users.approve'),
    tone: 'primary',
    show: (row, c) => row.status !== 'approved' && row.id !== c.user?.id,
    run: (row) => api(`/api/users/${row.id}/approve/`, { method: 'POST' }),
  },
  {
    label: ctx.t('users.suspend'),
    tone: 'danger',
    show: (row, c) => row.status === 'approved' && row.id !== c.user?.id,
    confirm: ctx.t('users.suspendConfirm'),
    run: (row) => api(`/api/users/${row.id}/suspend/`, { method: 'POST' }),
  },
]

export const review = {
  path: '/api/market/review/',
  title: (ctx) => ctx.t('review.title'),
  intro: (ctx) => ctx.t('review.intro'),
  titleOf: (row) => row.title,
  badge: (row) => ({ value: row.status, group: 'listingStatus' }),
  columnsFor: (ctx) => [
    { label: ctx.t('market.seller'), key: 'seller_name' },
    { label: ctx.t('fields.variety'), render: (r) => name(r.variety_detail, ctx) },
    { label: ctx.t('fields.oasis'), render: (r) => name(r.oasis_detail, ctx) },
    { label: ctx.t('fields.pricePerKg'), key: 'price_per_kg', type: 'money' },
    { label: ctx.t('fields.quantityKg'), key: 'quantity_kg', type: 'kg' },
  ],
  detail: (row) => (
    <div className="stack">
      {row.description && <p dir="auto">{row.description}</p>}
      <div className="photos">
        {row.photos.map((p) => (
          <img key={p.id} src={p.image} alt="" />
        ))}
      </div>
    </div>
  ),
}

review.actionsFor = (ctx) => [
  {
    label: ctx.t('review.approve'),
    tone: 'primary',
    run: (row) => api(`/api/market/review/${row.id}/approve/`, { method: 'POST' }),
  },
  {
    label: ctx.t('review.reject'),
    tone: 'danger',
    input: ctx.t('review.reason'),
    run: (row, c, reason) => api(`/api/market/review/${row.id}/reject/`, { method: 'POST', body: { reason } }),
  },
]

export const audit = {
  path: '/api/audit/',
  title: (ctx) => ctx.t('audit.title'),
  intro: (ctx) => ctx.t('audit.intro'),
  titleOf: (row) => row.object_repr || row.object_type,
  badge: (row) => ({ value: row.action, group: 'auditActions' }),
  filtersFor: (ctx) => [
    {
      name: 'action',
      label: ctx.t('audit.action'),
      type: 'select',
      options: ['create', 'update', 'delete', 'status_change', 'login', 'login_failed'].map((a) => ({
        value: a,
        label: ctx.t(`auditActions.${a}`),
      })),
    },
    { name: 'date_from', label: ctx.t('common.from'), type: 'date' },
    { name: 'date_to', label: ctx.t('common.to'), type: 'date' },
  ],
  columnsFor: (ctx) => [
    { label: ctx.t('fields.date'), key: 'created_at', type: 'datetime' },
    { label: ctx.t('audit.who'), render: (r) => r.user_name || ctx.t('audit.system') },
    { label: ctx.t('audit.forWhom'), key: 'acting_for_name', show: (r) => Boolean(r.acting_for_name) },
    { label: ctx.t('audit.object'), key: 'object_type' },
    { label: 'IP', key: 'ip_address' },
  ],
  detail: (row, ctx) => (
    <div className="table-wrap">
      <table className="simple">
        <thead>
          <tr>
            <th>{ctx.t('audit.field')}</th>
            <th>{ctx.t('audit.before')}</th>
            <th>{ctx.t('audit.after')}</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(row.changes || {}).map(([key, value]) => (
            <tr key={key}>
              <td>{key}</td>
              <td dir="ltr">{Array.isArray(value) ? JSON.stringify(value[0]) : ''}</td>
              <td dir="ltr">{Array.isArray(value) ? JSON.stringify(value[1]) : JSON.stringify(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ),
}
