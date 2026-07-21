import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EditModal, FieldDefinition } from './EditModal';

const baseFields: FieldDefinition[] = [
  { key: 'name', label: 'Name', type: 'text', required: true },
  { key: 'age', label: 'Age', type: 'number', required: true, min: 1, max: 120 },
  { key: 'priority', label: 'Priority', type: 'select', options: ['low', 'medium', 'high'] },
  { key: 'skills', label: 'Skills', type: 'multiselect', options: ['cooking', 'driving', 'medication'], required: true },
];

const defaultProps = {
  isOpen: true,
  onClose: vi.fn(),
  onSubmit: vi.fn(),
  title: 'Edit Record',
  fields: baseFields,
  initialValues: { name: 'Alice', age: 30, priority: 'medium', skills: ['cooking'] },
};

describe('EditModal', () => {
  it('does not render when isOpen is false', () => {
    render(<EditModal {...defaultProps} isOpen={false} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders with title and fields', () => {
    render(<EditModal {...defaultProps} />);
    expect(screen.getByText('Edit Record')).toBeInTheDocument();
    expect(screen.getByLabelText(/Name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Age/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Priority/)).toBeInTheDocument();
  });

  it('pre-fills form with initial values', () => {
    render(<EditModal {...defaultProps} />);
    expect(screen.getByLabelText(/Name/)).toHaveValue('Alice');
    expect(screen.getByLabelText(/Age/)).toHaveValue(30);
  });

  it('shows validation error for empty required text field', async () => {
    render(<EditModal {...defaultProps} initialValues={{ name: '', age: 30, skills: ['cooking'] }} />);
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(screen.getByText('Name is required')).toBeInTheDocument();
    });
  });

  it('shows validation error for number out of range (below min)', async () => {
    render(<EditModal {...defaultProps} initialValues={{ name: 'Alice', age: 0, skills: ['cooking'] }} />);
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(screen.getByText('Age must be at least 1')).toBeInTheDocument();
    });
  });

  it('shows validation error for number out of range (above max)', async () => {
    render(<EditModal {...defaultProps} initialValues={{ name: 'Alice', age: 150, skills: ['cooking'] }} />);
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(screen.getByText('Age must be at most 120')).toBeInTheDocument();
    });
  });

  it('shows validation error for required multiselect with no selections', async () => {
    render(<EditModal {...defaultProps} initialValues={{ name: 'Alice', age: 30, skills: [] }} />);
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(screen.getByText('Skills is required')).toBeInTheDocument();
    });
  });

  it('calls onSubmit with processed values on valid submission', async () => {
    const onSubmit = vi.fn();
    render(<EditModal {...defaultProps} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Alice',
        age: 30,
        priority: 'medium',
        skills: ['cooking'],
      });
    });
  });

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn();
    render(<EditModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose on Escape key', () => {
    const onClose = vi.fn();
    render(<EditModal {...defaultProps} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn();
    render(<EditModal {...defaultProps} onClose={onClose} />);
    const backdrop = screen.getByRole('dialog');
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });

  it('clears validation error when user fixes the field', async () => {
    render(<EditModal {...defaultProps} initialValues={{ name: '', age: 30, skills: ['cooking'] }} />);
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => {
      expect(screen.getByText('Name is required')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: 'Bob' } });
    expect(screen.queryByText('Name is required')).not.toBeInTheDocument();
  });

  it('renders multiselect options as checkboxes', () => {
    render(<EditModal {...defaultProps} />);
    expect(screen.getByLabelText('cooking')).toBeInTheDocument();
    expect(screen.getByLabelText('driving')).toBeInTheDocument();
    expect(screen.getByLabelText('medication')).toBeInTheDocument();
  });

  it('toggles multiselect values', () => {
    render(<EditModal {...defaultProps} />);
    const drivingCheckbox = screen.getByLabelText('driving');
    expect(drivingCheckbox).not.toBeChecked();
    fireEvent.click(drivingCheckbox);
    expect(drivingCheckbox).toBeChecked();
  });

  it('has proper aria attributes for accessibility', () => {
    render(<EditModal {...defaultProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'modal-title');
  });
});
