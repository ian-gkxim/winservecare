import { useState, useEffect, useCallback } from 'react';
import { DataTable, type Column } from '../components/DataTable';
import { EditModal, type FieldDefinition } from '../components/EditModal';
import ConfirmationToast from '../components/ConfirmationToast';
import ErrorBanner from '../components/ErrorBanner';
import { getCarers, getSkills, updateCarer } from '../services/api';
import type { Carer, CarerUpdate } from '../types';

const columns: Column<Carer>[] = [
  { key: 'name', label: 'Name', sortable: true },
  {
    key: 'homeLat',
    label: 'Home Location',
    render: (_value, row) => `${row.homeLat.toFixed(4)}, ${row.homeLng.toFixed(4)}`,
  },
  {
    key: 'skills',
    label: 'Skills',
    render: (value) => (value as string[]).join(', '),
  },
  { key: 'maxWorkingHours', label: 'Max Hours', sortable: true },
  { key: 'maxContinuousHours', label: 'Max Continuous Hours', sortable: true },
  { key: 'minBreakMinutes', label: 'Min Break (min)', sortable: true },
];

export default function CarersPage() {
  const [carers, setCarers] = useState<Carer[]>([]);
  const [skillOptions, setSkillOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCarer, setSelectedCarer] = useState<Carer | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [carersData, skillsData] = await Promise.all([getCarers(), getSkills()]);
      setCarers(carersData);
      setSkillOptions(skillsData.map((s) => s.name));
    } catch {
      setErrorMessage('Failed to load carers data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = (carer: Carer) => {
    setSelectedCarer(carer);
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setSelectedCarer(null);
  };

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!selectedCarer) return;

    const updateData: CarerUpdate = {
      name: values.name as string,
      skills: values.skills as string[],
      maxWorkingHours: values.maxWorkingHours as number,
    };

    try {
      await updateCarer(selectedCarer.id, updateData);
      setIsModalOpen(false);
      setSelectedCarer(null);
      setToastMessage('Carer updated successfully.');
      await fetchData();
    } catch {
      setErrorMessage('Failed to update carer. Please try again.');
    }
  };

  const editFields: FieldDefinition[] = [
    { key: 'name', label: 'Name', type: 'text', required: true },
    {
      key: 'skills',
      label: 'Skills',
      type: 'multiselect',
      options: skillOptions,
    },
    {
      key: 'maxWorkingHours',
      label: 'Max Working Hours',
      type: 'number',
      min: 1,
      max: 24,
      required: true,
    },
  ];

  const initialValues = selectedCarer
    ? {
        name: selectedCarer.name,
        skills: selectedCarer.skills,
        maxWorkingHours: selectedCarer.maxWorkingHours,
      }
    : {};

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Carers</h1>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading carers...</p>
      ) : (
        <DataTable columns={columns} data={carers} onRowClick={handleRowClick} />
      )}

      <EditModal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        onSubmit={handleSubmit}
        title="Edit Carer"
        fields={editFields}
        initialValues={initialValues}
      />

      {toastMessage && (
        <ConfirmationToast
          message={toastMessage}
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
