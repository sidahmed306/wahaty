import { useId } from 'react'

/**
 * Champ de formulaire avec son libellé et son message d'erreur.
 * type : text, tel, password, number, date, textarea, select, checkboxes
 */
export default function Field({
  label,
  name,
  type = 'text',
  value,
  onChange,
  error,
  help,
  options = [],
  required = false,
  ...rest
}) {
  const id = useId()
  const describedBy = [error ? `${id}-error` : null, help ? `${id}-help` : null]
    .filter(Boolean)
    .join(' ')
  const common = {
    id,
    name,
    required,
    'aria-invalid': Boolean(error),
    'aria-describedby': describedBy || undefined,
    ...rest,
  }

  let control
  if (type === 'textarea') {
    control = <textarea {...common} value={value ?? ''} onChange={(e) => onChange(e.target.value)} dir="auto" />
  } else if (type === 'select') {
    control = (
      <select {...common} value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    )
  } else if (type === 'checkboxes') {
    const selected = Array.isArray(value) ? value : []
    return (
      <fieldset className={`field ${error ? 'invalid' : ''}`} style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="label">{label}</legend>
        <div className="checks">
          {options.map((o) => (
            <label key={o.value}>
              <input
                type="checkbox"
                name={name}
                checked={selected.includes(o.value)}
                onChange={(e) =>
                  onChange(e.target.checked ? [...selected, o.value] : selected.filter((v) => v !== o.value))
                }
              />
              {o.label}
            </label>
          ))}
        </div>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
      </fieldset>
    )
  } else {
    control = (
      <input
        {...common}
        type={type}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        inputMode={type === 'number' ? 'decimal' : type === 'tel' ? 'tel' : undefined}
        step={type === 'number' ? (rest.step ?? 'any') : undefined}
      />
    )
  }

  return (
    <div className={`field ${error ? 'invalid' : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {control}
      {help && (
        <div className="help" id={`${id}-help`}>
          {help}
        </div>
      )}
      {error && (
        <div className="error" id={`${id}-error`}>
          {error}
        </div>
      )}
    </div>
  )
}
