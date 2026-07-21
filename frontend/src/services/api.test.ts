import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import api, {
  getCarers,
  updateCarer,
  getPatients,
  updatePatient,
  getVisits,
  deleteVisit,
  getSkills,
  createSkill,
  getConstraints,
  updateConstraint,
  getScenarios,
  createScenario,
  getScenario,
  compareScenarios,
  getExceptions,
  resolveException,
  getKpis,
  getLatestReport,
  getConfig,
  updateConfig,
} from './api';

vi.mock('axios', () => {
  const mockAxiosInstance = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: { request: { use: vi.fn() }, response: { use: vi.fn() } },
  };
  return {
    default: { create: vi.fn(() => mockAxiosInstance) },
  };
});

describe('API Service', () => {
  // Since we mock axios.create, the returned instance is what our module uses
  // We need to get the mocked instance
  let mockInstance: ReturnType<typeof axios.create>;

  beforeEach(() => {
    mockInstance = api;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Carers', () => {
    it('getCarers calls GET /carers', async () => {
      const carers = [{ id: 1, name: 'Alice' }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: carers });

      const result = await getCarers();
      expect(mockInstance.get).toHaveBeenCalledWith('/carers');
      expect(result).toEqual(carers);
    });

    it('updateCarer calls PUT /carers/:id with data', async () => {
      const updated = { id: 1, name: 'Alice Updated' };
      vi.mocked(mockInstance.put).mockResolvedValue({ data: updated });

      const result = await updateCarer(1, { name: 'Alice Updated' });
      expect(mockInstance.put).toHaveBeenCalledWith('/carers/1', { name: 'Alice Updated' });
      expect(result).toEqual(updated);
    });
  });

  describe('Patients', () => {
    it('getPatients calls GET /patients', async () => {
      const patients = [{ id: 1, name: 'Bob' }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: patients });

      const result = await getPatients();
      expect(mockInstance.get).toHaveBeenCalledWith('/patients');
      expect(result).toEqual(patients);
    });

    it('updatePatient calls PUT /patients/:id with data', async () => {
      const updated = { id: 1, name: 'Bob Updated' };
      vi.mocked(mockInstance.put).mockResolvedValue({ data: updated });

      const result = await updatePatient(1, { name: 'Bob Updated' });
      expect(mockInstance.put).toHaveBeenCalledWith('/patients/1', { name: 'Bob Updated' });
      expect(result).toEqual(updated);
    });
  });

  describe('Visits', () => {
    it('getVisits calls GET /visits', async () => {
      const visits = [{ id: 1, patientId: 1 }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: visits });

      const result = await getVisits();
      expect(mockInstance.get).toHaveBeenCalledWith('/visits');
      expect(result).toEqual(visits);
    });

    it('deleteVisit calls DELETE /visits/:id', async () => {
      vi.mocked(mockInstance.delete).mockResolvedValue({ status: 204 });

      await deleteVisit(5);
      expect(mockInstance.delete).toHaveBeenCalledWith('/visits/5');
    });
  });

  describe('Skills', () => {
    it('getSkills calls GET /skills', async () => {
      const skills = [{ id: 1, name: 'Medication', carerCount: 2, visitCount: 5 }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: skills });

      const result = await getSkills();
      expect(mockInstance.get).toHaveBeenCalledWith('/skills');
      expect(result).toEqual(skills);
    });

    it('createSkill calls POST /skills with data', async () => {
      const created = { id: 2, name: 'Dementia Care', carerCount: 0, visitCount: 0 };
      vi.mocked(mockInstance.post).mockResolvedValue({ data: created });

      const result = await createSkill({ name: 'Dementia Care' });
      expect(mockInstance.post).toHaveBeenCalledWith('/skills', { name: 'Dementia Care' });
      expect(result).toEqual(created);
    });
  });

  describe('Constraints', () => {
    it('getConstraints calls GET /constraints', async () => {
      const constraints = [{ id: 1, name: 'Skill Match', isEnabled: true }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: constraints });

      const result = await getConstraints();
      expect(mockInstance.get).toHaveBeenCalledWith('/constraints');
      expect(result).toEqual(constraints);
    });

    it('updateConstraint calls PUT /constraints/:id with data', async () => {
      const updated = { id: 1, name: 'Skill Match', isEnabled: false };
      vi.mocked(mockInstance.put).mockResolvedValue({ data: updated });

      const result = await updateConstraint(1, { isEnabled: false });
      expect(mockInstance.put).toHaveBeenCalledWith('/constraints/1', { isEnabled: false });
      expect(result).toEqual(updated);
    });
  });

  describe('Scenarios', () => {
    it('getScenarios calls GET /scenarios', async () => {
      const scenarios = [{ id: 1, name: 'Baseline' }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: scenarios });

      const result = await getScenarios();
      expect(mockInstance.get).toHaveBeenCalledWith('/scenarios');
      expect(result).toEqual(scenarios);
    });

    it('createScenario calls POST /scenarios with name', async () => {
      const scenario = { id: 1, name: 'Test Scenario' };
      vi.mocked(mockInstance.post).mockResolvedValue({ data: scenario });

      const result = await createScenario({ name: 'Test Scenario' });
      expect(mockInstance.post).toHaveBeenCalledWith('/scenarios', { name: 'Test Scenario' });
      expect(result).toEqual(scenario);
    });

    it('getScenario calls GET /scenarios/:id', async () => {
      const scenario = { id: 1, name: 'Baseline' };
      vi.mocked(mockInstance.get).mockResolvedValue({ data: scenario });

      const result = await getScenario(1);
      expect(mockInstance.get).toHaveBeenCalledWith('/scenarios/1');
      expect(result).toEqual(scenario);
    });

    it('compareScenarios calls GET /scenarios/compare with ids param', async () => {
      const comparison = { scenario1: {}, scenario2: {}, differences: [], changedVisits: [] };
      vi.mocked(mockInstance.get).mockResolvedValue({ data: comparison });

      const result = await compareScenarios([1, 2]);
      expect(mockInstance.get).toHaveBeenCalledWith('/scenarios/compare', { params: { ids: '1,2' } });
      expect(result).toEqual(comparison);
    });
  });

  describe('Exceptions', () => {
    it('getExceptions calls GET /exceptions', async () => {
      const exceptions = [{ id: 1, description: 'Conflict' }];
      vi.mocked(mockInstance.get).mockResolvedValue({ data: exceptions });

      const result = await getExceptions();
      expect(mockInstance.get).toHaveBeenCalledWith('/exceptions');
      expect(result).toEqual(exceptions);
    });

    it('resolveException calls PUT /exceptions/:id/resolve', async () => {
      const resolved = { id: 1, isResolved: true };
      vi.mocked(mockInstance.put).mockResolvedValue({ data: resolved });

      const result = await resolveException(1);
      expect(mockInstance.put).toHaveBeenCalledWith('/exceptions/1/resolve');
      expect(result).toEqual(resolved);
    });
  });

  describe('KPIs', () => {
    it('getKpis calls GET /kpis', async () => {
      const kpis = { totalVisits: 20, carersAvailable: 5 };
      vi.mocked(mockInstance.get).mockResolvedValue({ data: kpis });

      const result = await getKpis();
      expect(mockInstance.get).toHaveBeenCalledWith('/kpis');
      expect(result).toEqual(kpis);
    });
  });

  describe('Reports', () => {
    it('getLatestReport calls GET /reports/latest', async () => {
      const report = { travelTimeSaved: 1.5 };
      vi.mocked(mockInstance.get).mockResolvedValue({ data: report });

      const result = await getLatestReport();
      expect(mockInstance.get).toHaveBeenCalledWith('/reports/latest');
      expect(result).toEqual(report);
    });
  });

  describe('Config', () => {
    it('getConfig calls GET /config', async () => {
      const config = { googleMapsApiKey: '', hasApiKey: false };
      vi.mocked(mockInstance.get).mockResolvedValue({ data: config });

      const result = await getConfig();
      expect(mockInstance.get).toHaveBeenCalledWith('/config');
      expect(result).toEqual(config);
    });

    it('updateConfig calls PUT /config with data', async () => {
      const config = { googleMapsApiKey: 'abc123', hasApiKey: true };
      vi.mocked(mockInstance.put).mockResolvedValue({ data: config });

      const result = await updateConfig({ googleMapsApiKey: 'abc123' });
      expect(mockInstance.put).toHaveBeenCalledWith('/config', { googleMapsApiKey: 'abc123' });
      expect(result).toEqual(config);
    });
  });
});
