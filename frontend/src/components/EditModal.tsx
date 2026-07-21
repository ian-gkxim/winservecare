import { useState, useEffect, useRef, useCallback } from 'react';

export interface FieldDefinition {
  key: string;
  label: string;
  type: 'text' | 'number' | 'select' | 'multiselect';
  required?: boolean;
  options?: string[];
  min?: number;
  max?: number;
  readOnly?: boolean;
}

export interface EditModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (values: Record<string, unknown>) => void;
  title: string;
  fields: FieldDefinition[];
  initialValues?: Record<string, unknown>;
}

interface ValidationErrors {
  [key: string]: string;
}

export function EditModal({
  isOpen,
  onClose,
  onSubmit,
  title,
  fields,
  initialValues = {},
}: EditModalProps) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<ValidationErrors>({});
  const modalRef = useRef<HTMLDivElement>(null);
  const firstFocusableRef = useRef<HTMLElement | null>(null);

  // Initialise form values when modal opens or initialValues change
  useEffect(() => {
    if (isOpen) {
      const defaults: Record<string, unknown> = {};
      fields.forEach((field) => {
        if (initialValues[field.key] !== undefined) {
          defaults[field.key] = initialValues[field.key];
        } else if (field.type === 'multiselect') {
          defaults[field.key] = [];
        } else if (field.type === 'number') {
          defaults[field.key] = field.min ?? 0;
        } else {
          defaults[field.key] = '';
        }
      });
      setValues(defaults);
      setErrors({});
    }
  }, [isOpen, initialValues, fields]);

  // Focus trap and escape key handling
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }

      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    // Focus the first input on open
    setTimeout(() => {
      if (modalRef.current) {
        const firstInput = modalRef.current.querySelector<HTMLElement>(
          'input, select, textarea'
        );
        if (firstInput) {
          firstInput.focus();
          firstFocusableRef.current = firstInput;
        }
      }
    }, 0);

    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const validate = useCallback((): boolean => {
    const newErrors: ValidationErrors = {};

    fields.forEach((field) => {
      if (field.readOnly) return;

      const value = values[field.key];

      // Required field validation
      if (field.required) {
        if (field.type === 'multiselect') {
          if (!Array.isArray(value) || value.length === 0) {
            newErrors[field.key] = `${field.label} is required`;
          }
        } else if (value === '' || value === null || value === undefined) {
          newErrors[field.key] = `${field.label} is required`;
        }
      }

      // Number range validation
      if (field.type === 'number' && value !== '' && value !== null && value !== undefined) {
        const num = Number(value);
        if (isNaN(num)) {
          newErrors[field.key] = `${field.label} must be a valid number`;
        } else {
          if (field.min !== undefined && num < field.min) {
            newErrors[field.key] = `${field.label} must be at least ${field.min}`;
          }
          if (field.max !== undefined && num > field.max) {
            newErrors[field.key] = `${field.label} must be at most ${field.max}`;
          }
        }
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [fields, values]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      // Convert number fields to actual numbers
      const processed: Record<string, unknown> = {};
      fields.forEach((field) => {
        if (field.type === 'number') {
          processed[field.key] = Number(values[field.key]);
        } else {
          processed[field.key] = values[field.key];
        }
      });
      onSubmit(processed);
    }
  };

  const handleFieldChange = (key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    // Clear error on change
    if (errors[key]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const handleMultiselectToggle = (key: string, option: string) => {
    setValues((prev) => {
      const current = (prev[key] as string[]) || [];
      const updated = current.includes(option)
        ? current.filter((v) => v !== option)
        : [...current, option];
      return { ...prev, [key]: updated };
    });
    if (errors[key]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        ref={modalRef}
        className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto"
      >
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 id="modal-title" className="text-lg font-semibold text-gray-900">
            {title}
          </h2>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="px-6 py-4 space-y-4">
            {fields.map((field) => (
              <div key={field.key}>
                <label
                  htmlFor={`field-${field.key}`}
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  {field.label}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </label>

                {field.type === 'text' && (
                  <input
                    id={`field-${field.key}`}
                    type="text"
                    value={(values[field.key] as string) ?? ''}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    readOnly={field.readOnly}
                    className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors[field.key] ? 'border-red-300' : 'border-gray-300'
                    } ${field.readOnly ? 'bg-gray-100 cursor-not-allowed' : ''}`}
                    aria-invalid={!!errors[field.key]}
                    aria-describedby={errors[field.key] ? `error-${field.key}` : undefined}
                  />
                )}

                {field.type === 'number' && (
                  <input
                    id={`field-${field.key}`}
                    type="number"
                    value={values[field.key] !== undefined ? String(values[field.key]) : ''}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    min={field.min}
                    max={field.max}
                    readOnly={field.readOnly}
                    className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors[field.key] ? 'border-red-300' : 'border-gray-300'
                    } ${field.readOnly ? 'bg-gray-100 cursor-not-allowed' : ''}`}
                    aria-invalid={!!errors[field.key]}
                    aria-describedby={errors[field.key] ? `error-${field.key}` : undefined}
                  />
                )}

                {field.type === 'select' && (
                  <select
                    id={`field-${field.key}`}
                    value={(values[field.key] as string) ?? ''}
                    onChange={(e) => handleFieldChange(field.key, e.target.value)}
                    disabled={field.readOnly}
                    className={`w-full px-3 py-2 border rounded-md shadow-sm text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                      errors[field.key] ? 'border-red-300' : 'border-gray-300'
                    } ${field.readOnly ? 'bg-gray-100 cursor-not-allowed' : ''}`}
                    aria-invalid={!!errors[field.key]}
                    aria-describedby={errors[field.key] ? `error-${field.key}` : undefined}
                  >
                    <option value="">Select {field.label.toLowerCase()}...</option>
                    {field.options?.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                )}

                {field.type === 'multiselect' && (
                  <div
                    className={`border rounded-md p-2 max-h-40 overflow-y-auto ${
                      errors[field.key] ? 'border-red-300' : 'border-gray-300'
                    }`}
                    role="group"
                    aria-labelledby={`field-${field.key}`}
                  >
                    {field.options && field.options.length > 0 ? (
                      field.options.map((opt) => (
                        <label
                          key={opt}
                          className="flex items-center gap-2 px-2 py-1 text-sm hover:bg-gray-50 rounded cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={((values[field.key] as string[]) || []).includes(opt)}
                            onChange={() => handleMultiselectToggle(field.key, opt)}
                            disabled={field.readOnly}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          {opt}
                        </label>
                      ))
                    ) : (
                      <span className="text-sm text-gray-500 px-2">No options available</span>
                    )}
                  </div>
                )}

                {errors[field.key] && (
                  <p
                    id={`error-${field.key}`}
                    className="mt-1 text-xs text-red-600"
                    role="alert"
                  >
                    {errors[field.key]}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
