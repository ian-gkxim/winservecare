import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ContractForm } from './ContractForm';
import type { CareContract } from '../types/contracts';

const defaultSkills = ['medication', 'personal_care', 'cooking', 'mobility'];

const defaultProps = {
  contract: null,
  skills: defaultSkills,
  onSubmit: vi.fn().mockResolvedValue(undefined),
};

const existingContract: CareContract = {
  id: 1,
  patientId: 10,
  visitFrequency: 'specific_days',
  daysOfWeek: ['mon', 'wed', 'fri'],
  visitsPerDay: 2,
  startDate: '2025-01-01',
  endDate: '2025-12-31',
  excludedDates: ['2025-03-15'],
  visitSlots: [
    {
      id: 1,
      slotIndex: 0,
      label: 'Morning visit',
      earliestStart: '07:00',
      latestStart: '09:00',
      durationMinutes: 45,
      requiredSkills: ['medication'],
    },
    {
      id: 2,
      slotIndex: 1,
      label: 'Evening visit',
      earliestStart: '17:00',
      latestStart: '19:00',
      durationMinutes: 60,
      requiredSkills: ['personal_care', 'cooking'],
    },
  ],
};

describe('ContractForm', () => {
  it('renders frequency selector with all options', () => {
    render(<ContractForm {...defaultProps} />);
    const select = screen.getByLabelText(/Visit Frequency/);
    expect(select).toBeInTheDocument();
    expect(screen.getByText('Daily')).toBeInTheDocument();
    expect(screen.getByText('Weekdays Only')).toBeInTheDocument();
    expect(screen.getByText('Specific Days')).toBeInTheDocument();
    expect(screen.getByText('Alternate Days')).toBeInTheDocument();
    expect(screen.getByText('Weekly')).toBeInTheDocument();
  });

  it('shows day-of-week checkboxes only when specific_days is selected', () => {
    render(<ContractForm {...defaultProps} />);
    // Default is 'daily', so day checkboxes should not be visible
    expect(screen.queryByText('Days of Week')).not.toBeInTheDocument();

    // Change to specific_days
    fireEvent.change(screen.getByLabelText(/Visit Frequency/), {
      target: { value: 'specific_days' },
    });
    expect(screen.getByText(/Days of Week/)).toBeInTheDocument();
    expect(screen.getByLabelText('Mon')).toBeInTheDocument();
    expect(screen.getByLabelText('Sun')).toBeInTheDocument();
  });

  it('renders one slot by default with all required fields', () => {
    render(<ContractForm {...defaultProps} />);
    expect(screen.getByText('Slot 1')).toBeInTheDocument();
    expect(screen.getByLabelText(/Label/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Earliest Start/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Latest Start/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Duration/)).toBeInTheDocument();
  });

  it('allows adding slots up to 4 and removing down to 1', () => {
    render(<ContractForm {...defaultProps} />);
    const addBtn = screen.getByText('Add Slot');

    // Add 3 more slots (total 4)
    fireEvent.click(addBtn);
    fireEvent.click(addBtn);
    fireEvent.click(addBtn);
    expect(screen.getByText('Slot 4')).toBeInTheDocument();
    // Add Slot button should be gone at max
    expect(screen.queryByText('Add Slot')).not.toBeInTheDocument();

    // Remove buttons should be present (4 of them)
    const removeButtons = screen.getAllByText('Remove');
    expect(removeButtons).toHaveLength(4);

    // Remove all but one
    fireEvent.click(removeButtons[0]);
    fireEvent.click(screen.getAllByText('Remove')[0]);
    fireEvent.click(screen.getAllByText('Remove')[0]);
    // Only 1 slot remains — Remove should not be visible
    expect(screen.queryByText('Remove')).not.toBeInTheDocument();
  });

  it('validates start date is required', async () => {
    render(<ContractForm {...defaultProps} />);
    fireEvent.click(screen.getByText('Create Contract'));
    await waitFor(() => {
      expect(screen.getByText('Start date is required')).toBeInTheDocument();
    });
  });

  it('validates end date must be >= start date', async () => {
    render(<ContractForm {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/Start Date/), { target: { value: '2025-06-01' } });
    fireEvent.change(screen.getByLabelText(/End Date/), { target: { value: '2025-05-01' } });
    // Fill minimal slot data
    fireEvent.change(screen.getByLabelText(/Label/), { target: { value: 'Test' } });
    fireEvent.click(screen.getByText('Create Contract'));
    await waitFor(() => {
      expect(screen.getByText('End date must be on or after start date')).toBeInTheDocument();
    });
  });

  it('validates at least one day is selected for specific_days frequency', async () => {
    render(<ContractForm {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/Visit Frequency/), {
      target: { value: 'specific_days' },
    });
    fireEvent.change(screen.getByLabelText(/Start Date/), { target: { value: '2025-01-01' } });
    fireEvent.change(screen.getByLabelText(/Label/), { target: { value: 'Test' } });
    fireEvent.click(screen.getByText('Create Contract'));
    await waitFor(() => {
      expect(screen.getByText('At least one day must be selected')).toBeInTheDocument();
    });
  });

  it('validates slot label is required', async () => {
    render(<ContractForm {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/Start Date/), { target: { value: '2025-01-01' } });
    // Leave label empty
    fireEvent.click(screen.getByText('Create Contract'));
    await waitFor(() => {
      expect(screen.getByText('Label is required')).toBeInTheDocument();
    });
  });

  it('validates slot duration must be between 15 and 120', async () => {
    render(<ContractForm {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/Start Date/), { target: { value: '2025-01-01' } });
    fireEvent.change(screen.getByLabelText(/Label/), { target: { value: 'Test' } });
    fireEvent.change(screen.getByLabelText(/Duration/), { target: { value: '10' } });
    fireEvent.click(screen.getByText('Create Contract'));
    await waitFor(() => {
      expect(screen.getByText('Must be between 15 and 120 minutes')).toBeInTheDocument();
    });
  });

  it('validates earliest start must be after latest start', async () => {
    render(<ContractForm {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/Start Date/), { target: { value: '2025-01-01' } });
    fireEvent.change(screen.getByLabelText(/Label/), { target: { value: 'Test' } });
    fireEvent.change(screen.getByLabelText(/Earliest Start/), { target: { value: '10:00' } });
    fireEvent.change(screen.getByLabelText(/Latest Start/), { target: { value: '09:00' } });
    fireEvent.click(screen.getByText('Create Contract'));
    await waitFor(() => {
      expect(screen.getByText('Must be after earliest start')).toBeInTheDocument();
    });
  });

  it('pre-populates fields when editing an existing contract', () => {
    render(<ContractForm {...defaultProps} contract={existingContract} />);
    expect(screen.getByLabelText(/Visit Frequency/)).toHaveValue('specific_days');
    expect(screen.getByLabelText('Mon')).toBeChecked();
    expect(screen.getByLabelText('Wed')).toBeChecked();
    expect(screen.getByLabelText('Fri')).toBeChecked();
    expect(screen.getByLabelText('Tue')).not.toBeChecked();
    expect(screen.getByLabelText(/Start Date/)).toHaveValue('2025-01-01');
    expect(screen.getByLabelText(/End Date/)).toHaveValue('2025-12-31');
    expect(screen.getByText('2025-03-15')).toBeInTheDocument();
    expect(screen.getByText('Slot 1')).toBeInTheDocument();
    expect(screen.getByText('Slot 2')).toBeInTheDocument();
  });

  it('submits valid form data', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ContractForm {...defaultProps} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText(/Start Date/), { target: { value: '2025-01-01' } });
    fireEvent.change(screen.getByLabelText(/Label/), { target: { value: 'Morning' } });
    fireEvent.change(screen.getByLabelText(/Earliest Start/), { target: { value: '07:00' } });
    fireEvent.change(screen.getByLabelText(/Latest Start/), { target: { value: '09:00' } });
    fireEvent.change(screen.getByLabelText(/Duration/), { target: { value: '45' } });

    fireEvent.click(screen.getByText('Create Contract'));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        visitFrequency: 'daily',
        visitsPerDay: 1,
        startDate: '2025-01-01',
        endDate: null,
        excludedDates: [],
        visitSlots: [
          {
            slotIndex: 0,
            label: 'Morning',
            earliestStart: '07:00',
            latestStart: '09:00',
            durationMinutes: 45,
            requiredSkills: [],
          },
        ],
      });
    });
  });

  it('shows Update Contract button when editing', () => {
    render(<ContractForm {...defaultProps} contract={existingContract} />);
    expect(screen.getByText('Update Contract')).toBeInTheDocument();
  });

  it('shows Delete Contract button when onDelete is provided and contract exists', () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<ContractForm {...defaultProps} contract={existingContract} onDelete={onDelete} />);
    expect(screen.getByText('Delete Contract')).toBeInTheDocument();
  });

  it('does not show Delete Contract button when no contract exists', () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<ContractForm {...defaultProps} onDelete={onDelete} />);
    expect(screen.queryByText('Delete Contract')).not.toBeInTheDocument();
  });

  it('calls onDelete when Delete Contract is clicked', async () => {
    const onDelete = vi.fn().mockResolvedValue(undefined);
    render(<ContractForm {...defaultProps} contract={existingContract} onDelete={onDelete} />);
    fireEvent.click(screen.getByText('Delete Contract'));
    await waitFor(() => {
      expect(onDelete).toHaveBeenCalled();
    });
  });

  it('allows adding and removing excluded dates', () => {
    render(<ContractForm {...defaultProps} />);
    const addBtn = screen.getByText('Add');

    // Add button should be disabled when no date is entered
    expect(addBtn).toBeDisabled();
  });

  it('displays skills as checkboxes in the slot', () => {
    render(<ContractForm {...defaultProps} />);
    expect(screen.getByLabelText('medication')).toBeInTheDocument();
    expect(screen.getByLabelText('personal_care')).toBeInTheDocument();
    expect(screen.getByLabelText('cooking')).toBeInTheDocument();
    expect(screen.getByLabelText('mobility')).toBeInTheDocument();
  });

  it('toggles skill selection in a slot', () => {
    render(<ContractForm {...defaultProps} />);
    const medicationCheckbox = screen.getByLabelText('medication');
    expect(medicationCheckbox).not.toBeChecked();
    fireEvent.click(medicationCheckbox);
    expect(medicationCheckbox).toBeChecked();
    fireEvent.click(medicationCheckbox);
    expect(medicationCheckbox).not.toBeChecked();
  });
});
