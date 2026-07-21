import { useEffect, useRef, useState, useCallback } from 'react';
import { Loader } from '@googlemaps/js-api-loader';
import type { AnimationStep, StepData, MarkerData, AssignmentEdge, RouteAnimation } from '../types';
import api from '../services/api';

export interface AnimatedMapProps {
  steps: AnimationStep[];
  isRunning: boolean;
  isPaused: boolean;
  currentStep: number;
}

const BRISTOL_CENTER = { lat: 51.4545, lng: -2.5879 };
const CARER_COLOURS = ['#2563eb', '#16a34a', '#dc2626', '#ea580c', '#7c3aed'];

/** Delay (ms) per step type before auto-advancing */
export const STEP_DELAYS: Record<string, number> = {
  locations: 2000,
  matrix: 1000,
  assignments: 2500,
  pruning: 2500,
  evaluation: 3000,
  improvement: 2000,
  solution: 3000,
  animation: 3000,
};

interface MarkerEntry {
  marker: google.maps.Marker;
  entityType: 'carer' | 'patient';
  entityId: number;
}

export function AnimatedMap({ steps, isRunning, isPaused, currentStep }: AnimatedMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markerEntriesRef = useRef<MarkerEntry[]>([]);
  const polylinesRef = useRef<google.maps.Polyline[]>([]);
  const overlaysRef = useRef<google.maps.InfoWindow[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const autoAdvanceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const renderedStepRef = useRef<number>(-1);

  const [loadError, setLoadError] = useState<string | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Load Google Maps
  useEffect(() => {
    let cancelled = false;

    async function loadMap() {
      try {
        const response = await api.get('/config/maps-key');
        const apiKey = response.data?.key || '';

        if (!apiKey) {
          setLoadError('Google Maps API key not configured. Please set it in Configuration (/config).');
          return;
        }

        const loader = new Loader({
          apiKey,
          version: 'weekly',
        });

        await loader.importLibrary('maps');
        await loader.importLibrary('marker');

        if (cancelled || !mapContainerRef.current) return;

        const map = new google.maps.Map(mapContainerRef.current, {
          center: BRISTOL_CENTER,
          zoom: 12,
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: true,
        });

        mapRef.current = map;
        setMapLoaded(true);
      } catch (err) {
        if (!cancelled) {
          setLoadError(
            `Failed to load Google Maps: ${err instanceof Error ? err.message : 'Unknown error'}`
          );
        }
      }
    }

    loadMap();
    return () => { cancelled = true; };
  }, []);

  // Clear all map elements
  const clearMap = useCallback(() => {
    markerEntriesRef.current.forEach((entry) => entry.marker.setMap(null));
    markerEntriesRef.current = [];
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];
    overlaysRef.current.forEach((o) => o.close());
    overlaysRef.current = [];
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  }, []);

  // Render a specific step's data on the map
  const renderStep = useCallback(
    (step: AnimationStep) => {
      const map = mapRef.current;
      if (!map) return;

      const { data } = step;

      switch (data.type) {
        case 'locations':
          renderLocations(map, data);
          break;
        case 'matrix':
          renderMatrix(map, data);
          break;
        case 'assignments':
          renderAssignments(map, data);
          break;
        case 'pruning':
          renderPruning(map, data);
          break;
        case 'evaluation':
          renderEvaluation(map, data);
          break;
        case 'improvement':
          renderImprovement(map, data);
          break;
        case 'solution':
          renderSolution(map, data);
          break;
        case 'animation':
          renderRouteAnimation(map, data);
          break;
      }
    },
    []
  );

  // Step 1: Plot carer and patient markers
  function renderLocations(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'locations' }>
  ) {
    clearMap();

    data.carers.forEach((carer: MarkerData) => {
      const marker = new google.maps.Marker({
        position: { lat: carer.lat, lng: carer.lng },
        map,
        title: `Carer: ${carer.name}`,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 10,
          fillColor: '#2563eb',
          fillOpacity: 1,
          strokeColor: '#1d4ed8',
          strokeWeight: 2,
        },
        label: {
          text: carer.name.charAt(0),
          color: '#ffffff',
          fontSize: '11px',
          fontWeight: 'bold',
        },
      });
      markerEntriesRef.current.push({ marker, entityType: 'carer', entityId: carer.id });
    });

    data.patients.forEach((patient: MarkerData) => {
      const marker = new google.maps.Marker({
        position: { lat: patient.lat, lng: patient.lng },
        map,
        title: `Patient: ${patient.name}`,
        icon: {
          path: google.maps.SymbolPath.BACKWARD_CLOSED_ARROW,
          scale: 7,
          fillColor: '#16a34a',
          fillOpacity: 1,
          strokeColor: '#15803d',
          strokeWeight: 2,
        },
      });
      markerEntriesRef.current.push({ marker, entityType: 'patient', entityId: patient.id });
    });
  }

  // Step 2: Show matrix info overlay
  function renderMatrix(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'matrix' }>
  ) {
    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="padding:8px;font-family:system-ui;"><strong>Distance Matrix</strong><br/>Calculating ${data.pairCount} origin-destination pairs...</div>`,
      position: BRISTOL_CENTER,
    });
    infoWindow.open(map);
    overlaysRef.current.push(infoWindow);
  }

  // Step 3: Draw assignment edges
  function renderAssignments(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'assignments' }>
  ) {
    // Clear previous polylines but keep markers
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];
    overlaysRef.current.forEach((o) => o.close());
    overlaysRef.current = [];

    data.edges.forEach((edge: AssignmentEdge) => {
      const carerEntry = markerEntriesRef.current.find(
        (e) => e.entityType === 'carer' && e.entityId === edge.carerId
      );
      const patientEntry = markerEntriesRef.current.find(
        (e) => e.entityType === 'patient' && e.entityId === edge.patientId
      );

      if (carerEntry && patientEntry) {
        const line = new google.maps.Polyline({
          path: [
            carerEntry.marker.getPosition()!,
            patientEntry.marker.getPosition()!,
          ],
          map,
          strokeColor: '#94a3b8',
          strokeOpacity: 0.6,
          strokeWeight: 1.5,
        });
        polylinesRef.current.push(line);
      }
    });
  }

  // Step 4: Fade/remove pruned edges
  function renderPruning(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'pruning' }>
  ) {
    // Mark removed edges with red colour before fading
    data.removedEdges.forEach((edge: AssignmentEdge) => {
      const carerEntry = markerEntriesRef.current.find(
        (e) => e.entityType === 'carer' && e.entityId === edge.carerId
      );
      const patientEntry = markerEntriesRef.current.find(
        (e) => e.entityType === 'patient' && e.entityId === edge.patientId
      );

      if (carerEntry && patientEntry) {
        // Find and style the corresponding line
        const carerPos = carerEntry.marker.getPosition()!;
        const patientPos = patientEntry.marker.getPosition()!;

        const matchingLine = polylinesRef.current.find((line) => {
          const path = line.getPath();
          if (path.getLength() < 2) return false;
          const start = path.getAt(0);
          const end = path.getAt(1);
          return (
            Math.abs(start.lat() - carerPos.lat()) < 0.0001 &&
            Math.abs(start.lng() - carerPos.lng()) < 0.0001 &&
            Math.abs(end.lat() - patientPos.lat()) < 0.0001 &&
            Math.abs(end.lng() - patientPos.lng()) < 0.0001
          );
        });

        if (matchingLine) {
          matchingLine.setOptions({
            strokeColor: '#ef4444',
            strokeOpacity: 0.3,
            strokeWeight: 1,
            icons: [{
              icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, scale: 3 },
              offset: '0',
              repeat: '10px',
            }],
          });
        }
      }
    });

    // Show reason overlay
    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="padding:8px;font-family:system-ui;"><strong>Pruning</strong><br/>${data.reason}<br/><em>${data.removedEdges.length} edges removed</em></div>`,
      position: map.getCenter()!,
    });
    infoWindow.open(map);
    overlaysRef.current.push(infoWindow);
  }

  // Step 5: Show candidate routes as dashed lines
  function renderEvaluation(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'evaluation' }>
  ) {
    // Clear previous assignment lines
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];
    overlaysRef.current.forEach((o) => o.close());
    overlaysRef.current = [];

    data.candidateRoutes.forEach((route, idx) => {
      const colour = CARER_COLOURS[idx % CARER_COLOURS.length];

      // Build path from carer home to each stop's patient location
      const carerEntry = markerEntriesRef.current.find(
        (e) => e.entityType === 'carer' && e.entityId === route.carerId
      );

      const routePath: google.maps.LatLngLiteral[] = [];
      if (carerEntry) {
        const pos = carerEntry.marker.getPosition()!;
        routePath.push({ lat: pos.lat(), lng: pos.lng() });
      }

      route.stops.forEach((stop) => {
        const patientEntry = markerEntriesRef.current.find(
          (e) => e.entityType === 'patient' && e.entityId === stop.patientId
        );
        if (patientEntry) {
          const pos = patientEntry.marker.getPosition()!;
          routePath.push({ lat: pos.lat(), lng: pos.lng() });
        }
      });

      if (routePath.length > 1) {
        const line = new google.maps.Polyline({
          path: routePath,
          map,
          strokeColor: colour,
          strokeOpacity: 0,
          strokeWeight: 2,
          icons: [{
            icon: {
              path: 'M 0,-1 0,1',
              strokeOpacity: 0.7,
              strokeColor: colour,
              scale: 3,
            },
            offset: '0',
            repeat: '12px',
          }],
        });
        polylinesRef.current.push(line);
      }
    });
  }

  // Step 6: Show improvement score overlay
  function renderImprovement(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'improvement' }>
  ) {
    overlaysRef.current.forEach((o) => o.close());
    overlaysRef.current = [];

    const lastScore = data.iterations.length > 0
      ? data.iterations[data.iterations.length - 1].score
      : 0;
    const firstScore = data.iterations.length > 0 ? data.iterations[0].score : 0;

    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="padding:12px;font-family:system-ui;text-align:center;">
        <strong>Optimisation Progress</strong><br/>
        <span style="font-size:24px;color:#2563eb;">${lastScore.toFixed(2)}</span><br/>
        <em>${data.iterations.length} iterations</em><br/>
        <small>Improvement: ${((firstScore - lastScore) / Math.max(firstScore, 1) * 100).toFixed(1)}%</small>
      </div>`,
      position: map.getCenter()!,
    });
    infoWindow.open(map);
    overlaysRef.current.push(infoWindow);
  }

  // Step 7: Show final routes as solid coloured polylines
  function renderSolution(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'solution' }>
  ) {
    // Clear previous elements
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];
    overlaysRef.current.forEach((o) => o.close());
    overlaysRef.current = [];

    data.routes.forEach((route, idx) => {
      const colour = CARER_COLOURS[idx % CARER_COLOURS.length];

      // Build path from carer marker to each stop's patient location
      const carerEntry = markerEntriesRef.current.find(
        (e) => e.entityType === 'carer' && e.entityId === route.carerId
      );

      const routePath: google.maps.LatLngLiteral[] = [];
      if (carerEntry) {
        const pos = carerEntry.marker.getPosition()!;
        routePath.push({ lat: pos.lat(), lng: pos.lng() });
      }

      route.stops.forEach((stop) => {
        const patientEntry = markerEntriesRef.current.find(
          (e) => e.entityType === 'patient' && e.entityId === stop.patientId
        );
        if (patientEntry) {
          const pos = patientEntry.marker.getPosition()!;
          routePath.push({ lat: pos.lat(), lng: pos.lng() });
        }
      });

      if (routePath.length > 1) {
        const line = new google.maps.Polyline({
          path: routePath,
          map,
          strokeColor: colour,
          strokeOpacity: 0.9,
          strokeWeight: 4,
        });
        polylinesRef.current.push(line);
      }
    });

    // Show final score overlay
    const infoWindow = new google.maps.InfoWindow({
      content: `<div style="padding:12px;font-family:system-ui;text-align:center;">
        <strong>Solution Found</strong><br/>
        <span style="font-size:20px;color:#16a34a;">Score: ${data.finalScore.toFixed(2)}</span><br/>
        <em>${data.routes.length} routes</em>
      </div>`,
      position: map.getCenter()!,
    });
    infoWindow.open(map);
    overlaysRef.current.push(infoWindow);
  }

  // Step 8: Animate markers moving along routes
  function renderRouteAnimation(
    map: google.maps.Map,
    data: Extract<StepData, { type: 'animation' }>
  ) {
    // Clear old polylines but keep location markers
    polylinesRef.current.forEach((p) => p.setMap(null));
    polylinesRef.current = [];
    overlaysRef.current.forEach((o) => o.close());
    overlaysRef.current = [];

    data.routes.forEach((route: RouteAnimation, routeIdx: number) => {
      if (route.waypoints.length < 2) return;

      const routeColour = route.colour || CARER_COLOURS[routeIdx % CARER_COLOURS.length];

      // Draw the route polyline
      const line = new google.maps.Polyline({
        path: route.waypoints,
        map,
        strokeColor: routeColour,
        strokeOpacity: 0.8,
        strokeWeight: 3,
      });
      polylinesRef.current.push(line);

      // Animate a marker along the route
      const animMarker = new google.maps.Marker({
        position: route.waypoints[0],
        map,
        icon: {
          path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
          scale: 6,
          fillColor: routeColour,
          fillOpacity: 1,
          strokeColor: '#000',
          strokeWeight: 1,
          rotation: 0,
        },
        zIndex: 100 + routeIdx,
      });
      markerEntriesRef.current.push({ marker: animMarker, entityType: 'carer', entityId: route.carerId });

      // Animate through waypoints sequentially per route
      const totalDuration = 2000; // ms per route
      const startDelay = routeIdx * (totalDuration + 500);

      setTimeout(() => {
        let waypointIdx = 0;
        const stepsPerSegment = 20;
        let segmentStep = 0;

        function animate() {
          if (waypointIdx >= route.waypoints.length - 1) return;

          const from = route.waypoints[waypointIdx];
          const to = route.waypoints[waypointIdx + 1];
          const fraction = segmentStep / stepsPerSegment;

          const lat = from.lat + (to.lat - from.lat) * fraction;
          const lng = from.lng + (to.lng - from.lng) * fraction;
          animMarker.setPosition({ lat, lng });

          segmentStep++;
          if (segmentStep > stepsPerSegment) {
            segmentStep = 0;
            waypointIdx++;
          }

          if (waypointIdx < route.waypoints.length - 1) {
            animationFrameRef.current = requestAnimationFrame(animate);
          }
        }

        animationFrameRef.current = requestAnimationFrame(animate);
      }, startDelay);
    });
  }

  // Render steps when they change
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;
    if (currentStep < 1 || currentStep > steps.length) return;

    const stepData = steps[currentStep - 1];
    if (!stepData) return;

    // Only render if step hasn't been rendered yet
    if (renderedStepRef.current >= currentStep) return;
    renderedStepRef.current = currentStep;

    renderStep(stepData);
  }, [currentStep, steps, mapLoaded, renderStep]);

  // Handle pause/resume - clear auto-advance timer when paused
  useEffect(() => {
    if (isPaused && autoAdvanceTimerRef.current) {
      clearTimeout(autoAdvanceTimerRef.current);
      autoAdvanceTimerRef.current = null;
    }
  }, [isPaused]);

  // Reset rendered step tracking when not running
  useEffect(() => {
    if (!isRunning) {
      renderedStepRef.current = -1;
      if (autoAdvanceTimerRef.current) {
        clearTimeout(autoAdvanceTimerRef.current);
        autoAdvanceTimerRef.current = null;
      }
    }
  }, [isRunning]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      clearMap();
      if (autoAdvanceTimerRef.current) {
        clearTimeout(autoAdvanceTimerRef.current);
      }
    };
  }, [clearMap]);

  if (loadError) {
    return (
      <div
        className="flex items-center justify-center h-full min-h-[400px] bg-gray-100 rounded-lg border border-gray-200"
        role="alert"
        aria-label="Map load error"
      >
        <div className="text-center p-6">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
            />
          </svg>
          <p className="mt-3 text-sm text-gray-600">{loadError}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={mapContainerRef}
      className="w-full h-full min-h-[400px] rounded-lg"
      role="application"
      aria-label="Animated optimisation map"
    />
  );
}

export default AnimatedMap;
