import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, ApiError, asList } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { formatDate, formatDateTime, formatKg, formatMoney, formatNumber, formatPhone } from '../lib/format'
import { useFetch } from '../lib/useFetch'
import Field from './Field'
import { Empty, ErrorAlert, Loader, StatusBadge } from './ui'

/**
 * Page de gestion générique (liste + ajout + modification + suppression + actions),
 * décrite par une configuration. Utilisée par toutes les pages de l'espace connecté.
 */

export function useCtx() {
  const { t, i18n } = useTranslation()
  const auth = useAuth()
  const user = auth.user
  return {
    t,
    lang: i18n.language,
    user,
    is: (role) => Boolean(user?.roles?.includes(role)),
  }
}

export function formatValue(value, type, ctx) {
  if (value === null || value === undefined || value === '') return '—'
  switch (type) {
    case 'money':
      return <span className="num">{formatMoney(value, ctx.lang)}</span>
    case 'kg':
      return <span className="num">{formatKg(value, ctx.lang)}</span>
    case 'number':
      return <span className="num">{formatNumber(value, ctx.lang)}</span>
    case 'date':
      return formatDate(value, ctx.lang)
    case 'datetime':
      return formatDateTime(value, ctx.lang)
    case 'phone':
      return <span className="num">{formatPhone(value)}</span>
    case 'bool':
      return value ? ctx.t('common.yes') : ctx.t('common.no')
    default:
      return String(value)
  }
}

const TEXT_TYPES = ['text', 'textarea', 'tel']

function initialForm(fields, row, ctx) {
  const form = {}
  for (const field of fields) {
    if (row) {
      const value = row[field.name]
      form[field.name] = field.fromRow ? field.fromRow(row, ctx) : (value ?? (field.type === 'lines' ? [] : ''))
    } else {
      const fallback = field.type === 'lines' ? [{}] : field.type === 'checkboxes' ? [] : ''
      form[field.name] = typeof field.default === 'function' ? field.default(ctx) : (field.default ?? fallback)
    }
  }
  return form
}

function cleanPayload(fields, form, editing, ctx) {
  const body = {}
  for (const field of fields) {
    if (editing && field.createOnly) continue
    if (field.showWhen && !field.showWhen(form, ctx)) continue
    let value = form[field.name]
    if (field.type === 'lines') {
      value = (value || [])
        .filter((line) => line.product)
        .map((line) => {
          const out = { product: Number(line.product), quantity: line.quantity }
          if (line[field.priceKey] !== undefined && line[field.priceKey] !== '') out[field.priceKey] = line[field.priceKey]
          return out
        })
    } else if (value === '' && !TEXT_TYPES.includes(field.type || 'text')) {
      // Nombre, date ou choix laissé vide : « null » (champ facultatif).
      value = null
    }
    body[field.name] = value
  }
  return body
}

function LinesInput({ field, value, onChange, ctx, options, error }) {
  const lines = value?.length ? value : [{}]
  const products = options || []
  const update = (index, key, v) => {
    const next = lines.map((line, i) => (i === index ? { ...line, [key]: v } : line))
    if (key === 'product' && field.priceKey === 'unit_price') {
      const product = products.find((p) => String(p.value) === String(v))
      if (product?.raw?.sale_price && !next[index].unit_price) next[index].unit_price = product.raw.sale_price
    }
    onChange(next)
  }
  return (
    <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="label">{field.label}</legend>
      <div className="lines">
        {lines.map((line, index) => (
          <div className="line" key={index}>
            <Field
              label={ctx.t('fields.product')}
              type="select"
              value={line.product ?? ''}
              onChange={(v) => update(index, 'product', v)}
              options={[{ value: '', label: '—' }, ...products]}
              required
            />
            <Field
              label={ctx.t('fields.quantity')}
              type="number"
              min="0"
              value={line.quantity ?? ''}
              onChange={(v) => update(index, 'quantity', v)}
              required
            />
            <Field
              label={field.priceKey === 'unit_cost' ? ctx.t('fields.unitCost') : ctx.t('fields.unitPrice')}
              type="number"
              min="0"
              value={line[field.priceKey] ?? ''}
              onChange={(v) => update(index, field.priceKey, v)}
            />
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => onChange(lines.filter((_, i) => i !== index))}
              disabled={lines.length === 1}
            >
              {ctx.t('common.remove')}
            </button>
          </div>
        ))}
      </div>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => onChange([...lines, {}])}>
        + {ctx.t('common.addLine')}
      </button>
      {error && <div className="error">{error}</div>}
    </fieldset>
  )
}

/** Charge les listes de choix (variétés, fermes, clients…) utilisées par les champs « select ». */
function useSources(fields, ctx) {
  const [sources, setSources] = useState({})
  const paths = useMemo(
    () => [...new Set(fields.filter((f) => f.source && (!f.when || f.when(ctx))).map((f) => f.source.path))],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fields, ctx.user?.id],
  )
  const load = useCallback(async () => {
    const entries = await Promise.all(
      paths.map(async (path) => {
        try {
          return [path, asList(await api(path))]
        } catch {
          return [path, []]
        }
      }),
    )
    setSources(Object.fromEntries(entries))
  }, [paths])
  useEffect(() => {
    load()
  }, [load])
  return [sources, load]
}

function optionsFor(field, sources, ctx, form) {
  if (field.options) return typeof field.options === 'function' ? field.options(ctx, form) : field.options
  if (!field.source) return []
  let rows = sources[field.source.path] || []
  if (field.source.filter) rows = rows.filter((r) => field.source.filter(r, form, ctx))
  return rows.map((r) => ({ value: String(r.id), label: field.source.label(r, ctx), raw: r }))
}

export function ResourceForm({ config, fields, row, ctx, sources, onSaved, onCancel }) {
  const editing = Boolean(row)
  const [form, setForm] = useState(() => initialForm(fields, row, ctx))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const visible = fields.filter(
    (f) => !(editing && f.createOnly) && !(f.when && !f.when(ctx)) && !(f.showWhen && !f.showWhen(form, ctx)),
  )

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      let body = cleanPayload(visible, form, editing, ctx)
      if (config.toPayload) body = config.toPayload(body, ctx, editing)
      const saved = editing
        ? await api(`${config.path}${row.id}/`, { method: 'PATCH', body })
        : await api(config.path, { method: 'POST', body })
      onSaved(saved, editing)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, null))
    } finally {
      setBusy(false)
    }
  }

  const fieldErrors = error?.fields || {}
  const unknownErrors = Object.keys(fieldErrors).filter((k) => !visible.some((f) => f.name === k))

  return (
    <form className="panel form" onSubmit={submit} noValidate>
      <h2 style={{ fontSize: '1.2rem', margin: 0 }}>{editing ? ctx.t('common.edit') : ctx.t('common.add')}</h2>
      {error && (!Object.keys(fieldErrors).length || unknownErrors.length > 0) && (
        <div className="alert" role="alert">
          {error.general || unknownErrors.map((k) => fieldErrors[k]).join(' ') || ctx.t('errors.generic')}
        </div>
      )}
      <div className="form-grid">
        {visible
          .filter((f) => f.type !== 'lines' && f.type !== 'textarea')
          .map((field) => (
            <Field
              key={field.name}
              label={field.label}
              name={field.name}
              type={field.type === 'money' || field.type === 'kg' ? 'number' : field.type}
              min={field.type === 'money' || field.type === 'kg' || field.type === 'number' ? '0' : undefined}
              value={form[field.name]}
              onChange={(v) => setForm((f) => ({ ...f, [field.name]: v }))}
              error={fieldErrors[field.name]}
              help={field.help}
              required={field.required}
              options={
                field.type === 'select'
                  ? [
                      ...(field.required ? [] : [{ value: '', label: '—' }]),
                      ...(field.required && !form[field.name] ? [{ value: '', label: ctx.t('common.choose') }] : []),
                      ...optionsFor(field, sources, ctx, form),
                    ]
                  : optionsFor(field, sources, ctx, form)
              }
            />
          ))}
      </div>
      {visible
        .filter((f) => f.type === 'textarea')
        .map((field) => (
          <Field
            key={field.name}
            label={field.label}
            type="textarea"
            value={form[field.name]}
            onChange={(v) => setForm((f) => ({ ...f, [field.name]: v }))}
            error={fieldErrors[field.name]}
            help={field.help}
            required={field.required}
          />
        ))}
      {visible
        .filter((f) => f.type === 'lines')
        .map((field) => (
          <LinesInput
            key={field.name}
            field={field}
            ctx={ctx}
            value={form[field.name]}
            onChange={(v) => setForm((f) => ({ ...f, [field.name]: v }))}
            options={optionsFor({ source: field.source }, sources, ctx, form)}
            error={fieldErrors[field.name]}
          />
        ))}
      <div className="btn-row">
        <button className="btn btn-primary" disabled={busy}>
          {busy ? ctx.t('common.wait') : ctx.t('common.save')}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          {ctx.t('common.cancel')}
        </button>
      </div>
    </form>
  )
}

function ActionButton({ action, row, ctx, onDone }) {
  const [asking, setAsking] = useState(false)
  const [input, setInput] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    setError(null)
    try {
      const result = await action.run(row, ctx, input)
      setAsking(false)
      setInput('')
      onDone(result, action)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (asking) {
    return (
      <div className="panel" style={{ gridColumn: '1 / -1', marginBottom: 0 }}>
        {action.input ? (
          <Field label={action.input} type="textarea" value={input} onChange={setInput} required />
        ) : (
          <p>{action.confirm}</p>
        )}
        <ErrorAlert error={error} />
        <div className="btn-row mt">
          <button
            type="button"
            className={`btn btn-sm ${action.tone === 'danger' ? 'btn-danger' : 'btn-primary'}`}
            disabled={busy || (action.input && !input.trim())}
            onClick={run}
          >
            {busy ? ctx.t('common.wait') : ctx.t('common.confirm')}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAsking(false)}>
            {ctx.t('common.cancel')}
          </button>
        </div>
      </div>
    )
  }
  return (
    <>
      <button
        type="button"
        className={`btn btn-sm ${action.tone === 'danger' ? 'btn-danger' : action.tone === 'primary' ? 'btn-primary' : 'btn-outline'}`}
        disabled={busy}
        onClick={() => (action.input || action.confirm ? setAsking(true) : run())}
      >
        {busy ? ctx.t('common.wait') : action.label}
      </button>
      {error && !asking && <ErrorAlert error={error} />}
    </>
  )
}

function RowCard({ config, columns, allActions, row, ctx, onEdit, onChanged }) {
  const [open, setOpen] = useState(false)
  const actions = allActions.filter((a) => !a.show || a.show(row, ctx))
  const deletable = config.canDelete?.(row, ctx)
  const editable = config.canEdit?.(row, ctx)
  const badge = config.badge?.(row, ctx)

  const deleteAction = {
    label: ctx.t('common.delete'),
    tone: 'danger',
    confirm: ctx.t('common.confirmDelete'),
    run: () => api(`${config.path}${row.id}/`, { method: 'DELETE' }),
  }

  return (
    <article className="row-card">
      <div className="row-top">
        <span className="row-title">{config.titleOf(row, ctx)}</span>
        {badge && <StatusBadge value={badge.value} group={badge.group} />}
      </div>
      <dl className="kv">
        {columns
          .filter((c) => !c.show || c.show(row, ctx))
          .map((column) => (
            <div key={column.label}>
              <dt>{column.label}</dt>
              <dd>{column.render ? column.render(row, ctx) : formatValue(row[column.key], column.type, ctx)}</dd>
            </div>
          ))}
      </dl>
      {open && config.detail && <div className="mt">{config.detail(row, ctx, onChanged)}</div>}
      {(config.detail || editable || deletable || actions.length > 0) && (
        <div className="btn-row">
          {config.detail && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
              {open ? ctx.t('common.hide') : ctx.t('common.details')}
            </button>
          )}
          {editable && (
            <button type="button" className="btn btn-outline btn-sm" onClick={() => onEdit(row)}>
              {ctx.t('common.edit')}
            </button>
          )}
          {actions.map((action) => (
            <ActionButton key={action.label} action={action} row={row} ctx={ctx} onDone={onChanged} />
          ))}
          {deletable && <ActionButton action={deleteAction} row={row} ctx={ctx} onDone={onChanged} />}
        </div>
      )}
    </article>
  )
}

export default function ResourcePage({ config }) {
  const baseCtx = useCtx()
  /* eslint-disable react-hooks/exhaustive-deps */
  const fields = useMemo(() => (config.fields ? config.fields(baseCtx) : []), [config, baseCtx.lang, baseCtx.user?.id])
  const filters = useMemo(() => (config.filtersFor ? config.filtersFor(baseCtx) : []), [config, baseCtx.lang, baseCtx.user?.id])
  const columns = useMemo(() => (config.columnsFor ? config.columnsFor(baseCtx) : []), [config, baseCtx.lang, baseCtx.user?.id])
  const actions = useMemo(() => (config.actionsFor ? config.actionsFor(baseCtx) : []), [config, baseCtx.lang, baseCtx.user?.id])
  /* eslint-enable react-hooks/exhaustive-deps */
  const [filterValues, setFilterValues] = useState({})
  const [sources, reloadSources] = useSources([...fields, ...filters], baseCtx)
  const ctx = { ...baseCtx, sources }
  const { data, loading, error, reload } = useFetch(config.path, { ...config.params, ...filterValues })
  const [editing, setEditing] = useState(null) // null : fermé ; {} : ajout ; ligne : modification
  const [message, setMessage] = useState(null)
  const rows = asList(data)
  const canCreate = config.canCreate ? config.canCreate(ctx) : Boolean(config.fields)

  const saved = (row, wasEditing) => {
    setEditing(null)
    setMessage(config.afterSave ? config.afterSave(row, ctx, wasEditing) : ctx.t('common.saved'))
    reload()
    reloadSources()
  }

  const changed = (result, action) => {
    setMessage(action?.message ? action.message(result, ctx) : ctx.t('common.done'))
    reload()
    reloadSources()
  }

  return (
    <div>
      <div className="page-head">
        <h1>{config.title(ctx)}</h1>
        {canCreate && editing === null && (
          <button type="button" className="btn btn-primary" onClick={() => setEditing({})}>
            + {config.addLabel ? config.addLabel(ctx) : ctx.t('common.add')}
          </button>
        )}
      </div>
      {config.intro && <p className="muted">{config.intro(ctx)}</p>}
      {config.summary && config.summary(rows, ctx)}
      {message && (
        <div className="alert success" role="status" style={{ marginBottom: 12 }}>
          {message}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ marginInlineStart: 12 }}
            onClick={() => setMessage(null)}
          >
            {ctx.t('common.close')}
          </button>
        </div>
      )}
      {editing !== null && (
        <ResourceForm
          key={editing.id || 'new'}
          config={config}
          fields={fields}
          row={editing.id ? editing : null}
          ctx={ctx}
          sources={sources}
          onSaved={saved}
          onCancel={() => setEditing(null)}
        />
      )}
      {filters.length > 0 && (
        <div className="filters">
          {filters.map((filter) => (
            <Field
              key={filter.name}
              label={filter.label}
              type={filter.type}
              value={filterValues[filter.name] ?? ''}
              onChange={(v) => setFilterValues((f) => ({ ...f, [filter.name]: v }))}
              options={
                filter.type === 'select'
                  ? [{ value: '', label: ctx.t('common.all') }, ...optionsFor(filter, sources, ctx, {})]
                  : undefined
              }
            />
          ))}
        </div>
      )}
      <ErrorAlert error={error} />
      {loading && !data ? (
        <Loader />
      ) : rows.length === 0 ? (
        <Empty>{config.empty ? config.empty(ctx) : undefined}</Empty>
      ) : (
        <div className="rows">
          {rows.map((row) => (
            <RowCard
              key={row.id}
              config={config}
              columns={columns}
              allActions={actions}
              row={row}
              ctx={ctx}
              onEdit={setEditing}
              onChanged={changed}
            />
          ))}
        </div>
      )}
    </div>
  )
}
