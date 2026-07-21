import { useState, useEffect, useCallback } from 'react';
import { DataTable, type Column } from '../components/DataTable';
import { EditModal, type FieldDefinition } from '../components/EditModal';
import { ContractForm } from '../components/ContractForm';
import ConfirmationToast from '../components/ConfirmationToast';
import ErrorBanner from '../components/ErrorBanner';
import {
  getPatients,
  updatePatient,
  getSkills,
  getPatientContract,
  savePatientContract,
  deletePatientContract,
} from '../services/api';
import type { Patient, PatientUpdate } from '../types';
import type { CareContract, CareContractCreate } from '../types/contracts';

const columns: Column<Patient>[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'address', label: 'Address', sortable: true },
  {
    key: 'preferences',
    label: 'Preferences',
    render: (value) => (value as string[]).join(', '),
  },
  { key: 'priority', label: 'Priority', sortable: true },
  {
    key: 'continuityScore',
    label: 'Continuity Score',
    sortable: true,
    render: (value) => `${value}%`,
  },
];

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Contract management state
  const [contractPatient, setContractPatient] = useState<Patient | null>(null);
  const [contract, setContract] = useState<CareContract | null>(null);
  const [skillOptions, setSkillOptions] = useState<string[]>([]);
  const [contractLoading, setContractLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [patientsData, skillsData] = await Promise.all([getPatients(), getSkills()]);
      setPatients(patientsData);
      setSkillOptions(skillsData.map((s) => s.name));
    } catch {
      setErrorMessage('Failed to load patients data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRowClick = (patient: Patient) => {
    setSelectedPatient(patient);
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setSelectedPatient(null);
  };

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!selectedPatient) return;

    const updateData: PatientUpdate = {
      name: values.name as string,
      address: values.address as string,
      priority: values.priority as 'low' | 'medium' | 'high',
    };

    try {
      await updatePatient(selectedPatient.id, updateData);
      setIsModalOpen(false);
      setSelectedPatient(null);
      setToastMessage('Patient updated successfully.');
      await fetchData();
    } catch {
      setErrorMessage('Failed to update patient. Please try again.');
    }
  };

  const handleManageContract = async (patient: Patient) => {
    // If clicking the same patient, toggle the panel off
    if (contractPatient?.id === patient.id) {
      setContractPatient(null);
      setContract(null);
      return;
    }

    setContractPatient(patient);
    setContractLoading(true);
    try {
      const existingContract = await getPatientContract(patient.id);
      setContract(existingContract);
    } catch {
      setContract(null);
    } finally {
      setContractLoading(false);
    }
  };

  const handleContractSubmit = async (data: CareContractCreate) => {
    if (!contractPatient) return;

    await savePatientContract(contractPatient.id, data);
    setToastMessage('Care contract saved successfully.');
    // Refresh the contract to get the persisted version with IDs
    const updatedContract = await getPatientContract(contractPatient.id);
    setContract(updatedContract);
  };

  const handleContractDelete = async () => {
    if (!contractPatient) return;

    await deletePatientContract(contractPatient.id);
    setContract(null);
    setToastMessage('Care contract deleted successfully.');
  };

  const handleContractClose = () => {
    setContractPatient(null);
    setContract(null);
  };

  const editFields: FieldDefinition[] = [
    { key: 'name', label: 'Name', type: 'text', required: true },
    { key: 'address', label: 'Address', type: 'text' },
    {
      key: 'priority',
      label: 'Priority',
      type: 'select',
      options: ['low', 'medium', 'high'],
    },
    {
      key: 'continuityScore',
      label: 'Continuity Score',
      type: 'number',
      readOnly: true,
    },
  ];

  const initialValues = selectedPatient
    ? {
        name: selectedPatient.name,
        address: selectedPatient.address,
        priority: selectedPatient.priority,
        continuityScore: selectedPatient.continuityScore,
      }
    : {};

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Patients</h1>

      {errorMessage && (
        <div className="mb-4">
          <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage(null)} />
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading patients...</p>
      ) : (
        <div className="space-y-4">
          <DataTable columns={columns} data={patients} onRowClick={handleRowClick} />

          {/* Contract management section */}
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Patient
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Contract
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {patients.map((patient) => (
                  <tr key={patient.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700">{patient.name}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleManageContract(patient)}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md border ${
                          contractPatient?.id === patient.id
                            ? 'text-blue-800 bg-blue-100 border-blue-300'
                            : 'text-blue-700 bg-blue-50 border-blue-200 hover:bg-blue-100'
                        }`}
                      >
                        {contractPatient?.id === patient.id ? 'Hide Contract' : 'Manage Contract'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Contract Form Panel */}
      {contractPatient && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">
              Contract for {contractPatient.name}
            </h2>
            <button
              onClick={handleContractClose}
              className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 border border-gray-200 rounded-md hover:bg-gray-200"
            >
              Close
            </button>
          </div>

          {contractLoading ? (
            <p className="text-gray-500">Loading contract...</p>
          ) : (
            <ContractForm
              contract={contract}
              skills={skillOptions}
              onSubmit={handleContractSubmit}
              onDelete={contract ? handleContractDelete : undefined}
            />
          )}
        </div>
      )}

      <EditModal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        onSubmit={handleSubmit}
        title="Edit Patient"
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
