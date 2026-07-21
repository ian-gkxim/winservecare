import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KPIRibbon, formatMetricValue } from './KPIRibbon';
import { KPIMetrics } from '../types';

const sampleMetrics: KPIMetrics = {
  totalVisits: 20,
  carersAvailable: 5,
  travelHours: 3.47,
  mileage: 45.23,
  overtime: 1.15,
  continuityScore: 78.6,
};

describe('KPIRibbon', () => {
  describe('rendering with metrics', () => {
    it('renders all 6 metric cards', () => {
      render(<KPIRibbon metrics={sampleMetrics} />);

      expect(screen.getByText('Total Visits')).toBeInTheDocument();
      expect(screen.getByText('Carers Available')).toBeInTheDocument();
      expect(screen.getByText('Travel Hours')).toBeInTheDocument();
      expect(screen.getByText('Mileage')).toBeInTheDocument();
      expect(screen.getByText('Overtime')).toBeInTheDocument();
      expect(screen.getByText('Continuity Score')).toBeInTheDocument();
    });

    it('formats integer metrics as whole numbers', () => {
      render(<KPIRibbon metrics={sampleMetrics} />);

      expect(screen.getByText('20')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('formats decimal metrics with 1 decimal place and suffix', () => {
      render(<KPIRibbon metrics={sampleMetrics} />);

      expect(screen.getByText('3.5 hrs')).toBeInTheDocument();
      expect(screen.getByText('45.2 mi')).toBeInTheDocument();
      expect(screen.getByText('1.1 hrs')).toBeInTheDocument();
    });

    it('formats continuity score as integer percentage', () => {
      render(<KPIRibbon metrics={sampleMetrics} />);

      expect(screen.getByText('79%')).toBeInTheDocument();
    });

    it('has accessible aria-labels on each metric card', () => {
      render(<KPIRibbon metrics={sampleMetrics} />);

      expect(screen.getByLabelText('Total Visits: 20')).toBeInTheDocument();
      expect(screen.getByLabelText('Carers Available: 5')).toBeInTheDocument();
      expect(screen.getByLabelText('Travel Hours: 3.5 hrs')).toBeInTheDocument();
      expect(screen.getByLabelText('Mileage: 45.2 mi')).toBeInTheDocument();
      expect(screen.getByLabelText('Overtime: 1.1 hrs')).toBeInTheDocument();
      expect(screen.getByLabelText('Continuity Score: 79%')).toBeInTheDocument();
    });

    it('renders the KPI region with accessible role', () => {
      render(<KPIRibbon metrics={sampleMetrics} />);

      expect(screen.getByRole('region', { name: 'Key Performance Indicators' })).toBeInTheDocument();
    });
  });

  describe('rendering with null metrics (data unavailable)', () => {
    it('renders placeholder indicators when metrics is null', () => {
      render(<KPIRibbon metrics={null} />);

      const placeholders = screen.getAllByText('—');
      expect(placeholders).toHaveLength(6);
    });

    it('has accessible aria-labels indicating data unavailable', () => {
      render(<KPIRibbon metrics={null} />);

      expect(screen.getByLabelText('Total Visits: Data unavailable')).toBeInTheDocument();
      expect(screen.getByLabelText('Carers Available: Data unavailable')).toBeInTheDocument();
      expect(screen.getByLabelText('Travel Hours: Data unavailable')).toBeInTheDocument();
      expect(screen.getByLabelText('Mileage: Data unavailable')).toBeInTheDocument();
      expect(screen.getByLabelText('Overtime: Data unavailable')).toBeInTheDocument();
      expect(screen.getByLabelText('Continuity Score: Data unavailable')).toBeInTheDocument();
    });
  });
});

describe('formatMetricValue', () => {
  it('formats totalVisits as integer', () => {
    expect(formatMetricValue('totalVisits', 20)).toBe('20');
    expect(formatMetricValue('totalVisits', 20.7)).toBe('21');
  });

  it('formats carersAvailable as integer', () => {
    expect(formatMetricValue('carersAvailable', 5)).toBe('5');
    expect(formatMetricValue('carersAvailable', 5.4)).toBe('5');
  });

  it('formats travelHours with 1 decimal and hrs suffix', () => {
    expect(formatMetricValue('travelHours', 3.47)).toBe('3.5 hrs');
    expect(formatMetricValue('travelHours', 0)).toBe('0.0 hrs');
    expect(formatMetricValue('travelHours', 10)).toBe('10.0 hrs');
  });

  it('formats mileage with 1 decimal and mi suffix', () => {
    expect(formatMetricValue('mileage', 45.23)).toBe('45.2 mi');
    expect(formatMetricValue('mileage', 0)).toBe('0.0 mi');
    expect(formatMetricValue('mileage', 100.99)).toBe('101.0 mi');
  });

  it('formats overtime with 1 decimal and hrs suffix', () => {
    expect(formatMetricValue('overtime', 1.25)).toBe('1.3 hrs');
    expect(formatMetricValue('overtime', 0)).toBe('0.0 hrs');
    expect(formatMetricValue('overtime', 2.0)).toBe('2.0 hrs');
  });

  it('formats continuityScore as integer percentage', () => {
    expect(formatMetricValue('continuityScore', 78.6)).toBe('79%');
    expect(formatMetricValue('continuityScore', 0)).toBe('0%');
    expect(formatMetricValue('continuityScore', 100)).toBe('100%');
    expect(formatMetricValue('continuityScore', 50.4)).toBe('50%');
  });
});
