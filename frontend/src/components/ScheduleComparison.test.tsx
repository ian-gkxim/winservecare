import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  ScheduleComparison,
  computeSavings,
  computeCostDifference,
  buildAssignmentMap,
  getChangedVisitIds,
} from './ScheduleComparison';
import { Schedule, Route } from '../types';

function makeRoute(carerId: number, stops: Array<{ visitId: number; patientId: number; startTime: string; endTime: string }>): Route {
  return {
    carerId,
    stops: stops.map((s, i) => ({
      visitId: s.visitId,
      patientId: s.patientId,
      arrivalTime: s.startTime,
      startTime: s.startTime,
      endTime: s.endTime,
      travelTimeFromPrev: i === 0 ? 0 : 10,
      mileageFromPrev: i === 0 ? 0 : 3.5,
    })),
    totalTravelMinutes: 30,
    totalMileage: 10.5,
    totalCost: 50,
  };
}

function makeSchedule(overrides: Partial<Schedule> = {}): Schedule {
  return {
    routes: [
      makeRoute(1, [
        { visitId: 1, patientId: 1, startTime: '08:00', endTime: '08:30' },
        { visitId: 2, patientId: 2, startTime: '09:00', endTime: '09:45' },
      ]),
      makeRoute(2, [
        { visitId: 3, patientId: 3, startTime: '08:30', endTime: '09:00' },
      ]),
    ],
    totalTravelHours: 4.0,
    totalMileage: 60.0,
    totalOvertimeHours: 2.0,
    continuityScore: 75,
    totalCost: 500.0,
    ...overrides,
  };
}

describe('computeSavings', () => {
  it('computes absolute and percentage savings correctly', () => {
    const current = makeSchedule({ totalTravelHours: 10, totalMileage: 100, totalOvertimeHours: 5 });
    const proposed = makeSchedule({ totalTravelHours: 7, totalMileage: 80, totalOvertimeHours: 3 });

    const savings = computeSavings(current, proposed);

    expect(savings[0].label).toBe('Travel Hours');
    expect(savings[0].absolute).toBeCloseTo(3);
    expect(savings[0].percent).toBeCloseTo(30);

    expect(savings[1].label).toBe('Mileage');
    expect(savings[1].absolute).toBeCloseTo(20);
    expect(savings[1].percent).toBeCloseTo(20);

    expect(savings[2].label).toBe('Overtime');
    expect(savings[2].absolute).toBeCloseTo(2);
    expect(savings[2].percent).toBeCloseTo(40);
  });

  it('handles zero current values without division by zero', () => {
    const current = makeSchedule({ totalTravelHours: 0, totalMileage: 0, totalOvertimeHours: 0 });
    const proposed = makeSchedule({ totalTravelHours: 2, totalMileage: 10, totalOvertimeHours: 1 });

    const savings = computeSavings(current, proposed);

    expect(savings[0].percent).toBe(0);
    expect(savings[1].percent).toBe(0);
    expect(savings[2].percent).toBe(0);
  });

  it('handles negative savings (proposed worse than current)', () => {
    const current = makeSchedule({ totalTravelHours: 5, totalMileage: 50, totalOvertimeHours: 2 });
    const proposed = makeSchedule({ totalTravelHours: 7, totalMileage: 60, totalOvertimeHours: 3 });

    const savings = computeSavings(current, proposed);

    expect(savings[0].absolute).toBe(-2);
    expect(savings[0].percent).toBeCloseTo(-40);
  });
});

describe('computeCostDifference', () => {
  it('computes cost savings correctly', () => {
    const current = makeSchedule({ totalCost: 1000 });
    const proposed = makeSchedule({ totalCost: 750 });

    const result = computeCostDifference(current, proposed);

    expect(result.absolute).toBe(250);
    expect(result.percent).toBeCloseTo(25);
  });

  it('handles zero current cost without division by zero', () => {
    const current = makeSchedule({ totalCost: 0 });
    const proposed = makeSchedule({ totalCost: 100 });

    const result = computeCostDifference(current, proposed);

    expect(result.absolute).toBe(-100);
    expect(result.percent).toBe(0);
  });
});

describe('buildAssignmentMap', () => {
  it('maps visitId to carerId from routes', () => {
    const routes = [
      makeRoute(1, [
        { visitId: 10, patientId: 1, startTime: '08:00', endTime: '08:30' },
        { visitId: 20, patientId: 2, startTime: '09:00', endTime: '09:30' },
      ]),
      makeRoute(2, [
        { visitId: 30, patientId: 3, startTime: '10:00', endTime: '10:45' },
      ]),
    ];

    const map = buildAssignmentMap(routes);

    expect(map.get(10)).toBe(1);
    expect(map.get(20)).toBe(1);
    expect(map.get(30)).toBe(2);
  });
});

describe('getChangedVisitIds', () => {
  it('identifies visits that changed carer assignment', () => {
    const currentRoutes = [
      makeRoute(1, [
        { visitId: 1, patientId: 1, startTime: '08:00', endTime: '08:30' },
        { visitId: 2, patientId: 2, startTime: '09:00', endTime: '09:30' },
      ]),
      makeRoute(2, [
        { visitId: 3, patientId: 3, startTime: '10:00', endTime: '10:30' },
      ]),
    ];

    const proposedRoutes = [
      makeRoute(1, [
        { visitId: 1, patientId: 1, startTime: '08:00', endTime: '08:30' },
        { visitId: 3, patientId: 3, startTime: '09:00', endTime: '09:30' }, // was carer 2
      ]),
      makeRoute(2, [
        { visitId: 2, patientId: 2, startTime: '09:00', endTime: '09:30' }, // was carer 1
      ]),
    ];

    const changed = getChangedVisitIds(currentRoutes, proposedRoutes);

    expect(changed.has(2)).toBe(true);
    expect(changed.has(3)).toBe(true);
    expect(changed.has(1)).toBe(false);
  });

  it('returns empty set when nothing changed', () => {
    const routes = [
      makeRoute(1, [{ visitId: 1, patientId: 1, startTime: '08:00', endTime: '08:30' }]),
    ];
    const changed = getChangedVisitIds(routes, routes);
    expect(changed.size).toBe(0);
  });
});

describe('ScheduleComparison component', () => {
  it('shows empty state when both schedules are null', () => {
    render(<ScheduleComparison current={null} proposed={null} />);
    expect(screen.getByText(/no schedule data available/i)).toBeInTheDocument();
  });

  it('shows empty state when proposed is null', () => {
    const current = makeSchedule();
    render(<ScheduleComparison current={current} proposed={null} />);
    expect(screen.getByText(/proposed schedule not available/i)).toBeInTheDocument();
  });

  it('shows empty state when current is null', () => {
    const proposed = makeSchedule();
    render(<ScheduleComparison current={null} proposed={proposed} />);
    expect(screen.getByText(/current schedule not available/i)).toBeInTheDocument();
  });

  it('renders savings metrics when both schedules are provided', () => {
    const current = makeSchedule({ totalTravelHours: 10, totalMileage: 100, totalOvertimeHours: 5, totalCost: 1000 });
    const proposed = makeSchedule({ totalTravelHours: 7, totalMileage: 80, totalOvertimeHours: 3, totalCost: 750 });

    render(<ScheduleComparison current={current} proposed={proposed} />);

    expect(screen.getByText('Travel Hours')).toBeInTheDocument();
    expect(screen.getByText('Mileage')).toBeInTheDocument();
    expect(screen.getByText('Overtime')).toBeInTheDocument();
    expect(screen.getByText('Total Cost Savings')).toBeInTheDocument();
  });

  it('renders side-by-side schedule panels', () => {
    const current = makeSchedule();
    const proposed = makeSchedule();

    render(<ScheduleComparison current={current} proposed={proposed} />);

    expect(screen.getByText('Current Schedule')).toBeInTheDocument();
    expect(screen.getByText('Proposed Schedule')).toBeInTheDocument();
  });

  it('highlights visits with changed carer assignment', () => {
    const current = makeSchedule({
      routes: [
        makeRoute(1, [{ visitId: 1, patientId: 1, startTime: '08:00', endTime: '08:30' }]),
        makeRoute(2, [{ visitId: 2, patientId: 2, startTime: '09:00', endTime: '09:30' }]),
      ],
    });
    const proposed = makeSchedule({
      routes: [
        makeRoute(1, [
          { visitId: 1, patientId: 1, startTime: '08:00', endTime: '08:30' },
          { visitId: 2, patientId: 2, startTime: '09:00', endTime: '09:30' }, // changed from carer 2
        ]),
      ],
    });

    render(<ScheduleComparison current={current} proposed={proposed} />);

    // Visit 2 changed assignment - should show "Changed" label
    const changedLabels = screen.getAllByText('Changed');
    expect(changedLabels.length).toBeGreaterThan(0);
  });
});
