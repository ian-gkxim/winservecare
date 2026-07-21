import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AnimatedMap, STEP_DELAYS } from './AnimatedMap';
import type { AnimationStep } from '../types';

// Mock the API module
vi.mock('../services/api', () => ({
  getConfig: vi.fn(),
}));

// Mock @googlemaps/js-api-loader
vi.mock('@googlemaps/js-api-loader', () => ({
  Loader: vi.fn().mockImplementation(() => ({
    importLibrary: vi.fn().mockResolvedValue({}),
  })),
}));

import { getConfig } from '../services/api';

const mockGetConfig = vi.mocked(getConfig);

describe('AnimatedMap', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders fallback message when API key is missing', async () => {
    mockGetConfig.mockResolvedValue({ googleMapsApiKey: '', hasApiKey: false });

    render(
      <AnimatedMap steps={[]} isRunning={false} isPaused={false} currentStep={0} />
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Google Maps API key not configured/)).toBeInTheDocument();
  });

  it('renders fallback message when Google Maps fails to load', async () => {
    mockGetConfig.mockRejectedValue(new Error('Network error'));

    render(
      <AnimatedMap steps={[]} isRunning={false} isPaused={false} currentStep={0} />
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByText(/Failed to load Google Maps/)).toBeInTheDocument();
  });

  it('renders map container when API key is present', async () => {
    mockGetConfig.mockResolvedValue({ googleMapsApiKey: 'test-key', hasApiKey: true });

    // Mock google.maps.Map constructor
    const mockMap = {
      setCenter: vi.fn(),
      getCenter: vi.fn().mockReturnValue({ lat: () => 51.4545, lng: () => -2.5879 }),
    };
    (globalThis as unknown as { google: unknown }).google = {
      maps: {
        Map: vi.fn().mockReturnValue(mockMap),
        Marker: vi.fn().mockReturnValue({
          setMap: vi.fn(),
          getPosition: vi.fn().mockReturnValue({ lat: () => 51.4545, lng: () => -2.5879 }),
          getTitle: vi.fn().mockReturnValue(''),
          setPosition: vi.fn(),
        }),
        Polyline: vi.fn().mockReturnValue({
          setMap: vi.fn(),
          getPath: vi.fn().mockReturnValue({ getLength: () => 0 }),
          setOptions: vi.fn(),
        }),
        InfoWindow: vi.fn().mockReturnValue({
          open: vi.fn(),
          close: vi.fn(),
        }),
        SymbolPath: {
          CIRCLE: 0,
          BACKWARD_CLOSED_ARROW: 3,
          FORWARD_CLOSED_ARROW: 1,
        },
      },
    };

    render(
      <AnimatedMap steps={[]} isRunning={false} isPaused={false} currentStep={0} />
    );

    await waitFor(() => {
      expect(screen.getByRole('application')).toBeInTheDocument();
    });
  });

  it('exports STEP_DELAYS with all 8 step types', () => {
    const expectedTypes = ['locations', 'matrix', 'assignments', 'pruning', 'evaluation', 'improvement', 'solution', 'animation'];
    expectedTypes.forEach((type) => {
      expect(STEP_DELAYS[type]).toBeGreaterThanOrEqual(1000);
      expect(STEP_DELAYS[type]).toBeLessThanOrEqual(3000);
    });
  });

  it('has correct props interface', () => {
    const steps: AnimationStep[] = [
      {
        stepNumber: 1,
        stepName: 'Plot Locations',
        data: { type: 'locations', carers: [], patients: [] },
      },
    ];

    // Verify component renders without error with valid props
    mockGetConfig.mockResolvedValue({ googleMapsApiKey: '', hasApiKey: false });

    const { container } = render(
      <AnimatedMap steps={steps} isRunning={true} isPaused={false} currentStep={1} />
    );

    expect(container).toBeTruthy();
  });
});
