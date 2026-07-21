/**
 * Proactive Input Sheet
 *
 * A bottom-sheet modal that allows carers to voluntarily report status changes.
 * Provides predefined options (Requirement 5.2), optional free-text note with
 * 500-char limit (Requirement 5.3), attaches GPS coordinates and timestamp
 * (Requirements 5.4, 5.7), shows confirmation feedback (Requirement 5.6),
 * and pipes submissions to the Offline Buffer (Requirement 5.5).
 */

import React, { useState, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  TouchableOpacity,
  TextInput,
  ScrollView,
  Platform,
} from 'react-native';

import { ProactiveInputType, ProactiveInput } from '@/types';
import { enqueue } from '@/services/offlineBuffer';

// --- Types ---

interface ProactiveInputSheetProps {
  visible: boolean;
  onClose: () => void;
  currentVisitId?: number;
}

interface InputOption {
  type: ProactiveInputType;
  label: string;
  icon: string;
}

// --- Constants ---

const MAX_NOTE_LENGTH = 500;

const INPUT_OPTIONS: InputOption[] = [
  { type: 'arrived', label: 'Arrived', icon: '📍' },
  { type: 'visit_started', label: 'Visit Started', icon: '▶️' },
  { type: 'visit_completed', label: 'Visit Completed', icon: '✅' },
  { type: 'running_late', label: 'Running Late', icon: '⏰' },
  { type: 'issue_encountered', label: 'Issue Encountered', icon: '⚠️' },
  { type: 'cannot_complete', label: 'Cannot Complete', icon: '❌' },
];

// --- GPS Helper ---

interface LocationResult {
  latitude: number | undefined;
  longitude: number | undefined;
  location_unavailable: boolean;
}

/**
 * Attempt to get current GPS coordinates.
 * If unavailable, returns location_unavailable: true with null coords.
 */
async function getCurrentLocation(): Promise<LocationResult> {
  try {
    // Use expo-location in production. Here we use a promise-based approach
    // that gracefully degrades when location is unavailable.
    const { default: Location } = await import('expo-location');

    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') {
      return { latitude: undefined, longitude: undefined, location_unavailable: true };
    }

    const location = await Location.getCurrentPositionAsync({
      accuracy: Location.Accuracy.Balanced,
    });

    return {
      latitude: location.coords.latitude,
      longitude: location.coords.longitude,
      location_unavailable: false,
    };
  } catch {
    // GPS unavailable — flag it per Requirement 5.7
    return { latitude: undefined, longitude: undefined, location_unavailable: true };
  }
}

// --- Component ---

export default function ProactiveInputSheet({
  visible,
  onClose,
  currentVisitId,
}: ProactiveInputSheetProps) {
  const [selectedOption, setSelectedOption] = useState<ProactiveInputType | null>(null);
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  const resetState = useCallback(() => {
    setSelectedOption(null);
    setNote('');
    setSubmitting(false);
    setShowConfirmation(false);
  }, []);

  const handleClose = useCallback(() => {
    resetState();
    onClose();
  }, [onClose, resetState]);

  const handleOptionSelect = (type: ProactiveInputType) => {
    setSelectedOption(type);
  };

  const handleBack = () => {
    setSelectedOption(null);
    setNote('');
  };

  const handleSubmit = async () => {
    if (!selectedOption || currentVisitId === undefined) return;

    setSubmitting(true);

    // Get GPS coordinates (or flag as unavailable)
    const location = await getCurrentLocation();

    // Create timestamp
    const captured_at = new Date().toISOString();

    // Build payload matching the ProactiveInput interface
    const payload: ProactiveInput = {
      visit_id: currentVisitId,
      input_type: selectedOption,
      note: note.trim() || undefined,
      latitude: location.latitude,
      longitude: location.longitude,
      location_unavailable: location.location_unavailable,
      captured_at,
    };

    // Pipe to Offline Buffer (Requirement 5.5)
    enqueue('proactive_input', payload, captured_at);

    // Show confirmation feedback (Requirement 5.6)
    setSubmitting(false);
    setShowConfirmation(true);

    // Auto-dismiss after 1.5 seconds
    setTimeout(() => {
      handleClose();
    }, 1500);
  };

  // --- Render: Confirmation ---
  if (showConfirmation) {
    return (
      <Modal
        visible={visible}
        animationType="slide"
        transparent
        onRequestClose={handleClose}
      >
        <View style={styles.overlay}>
          <View style={styles.sheet}>
            <View style={styles.confirmationContainer}>
              <Text style={styles.confirmationIcon}>✓</Text>
              <Text style={styles.confirmationText}>Status update recorded</Text>
            </View>
          </View>
        </View>
      </Modal>
    );
  }

  // --- Render: Note Input (after option selected) ---
  if (selectedOption) {
    const selectedLabel =
      INPUT_OPTIONS.find((o) => o.type === selectedOption)?.label ?? '';

    return (
      <Modal
        visible={visible}
        animationType="slide"
        transparent
        onRequestClose={handleClose}
      >
        <View style={styles.overlay}>
          <View style={styles.sheet}>
            {/* Header */}
            <View style={styles.header}>
              <TouchableOpacity
                onPress={handleBack}
                accessibilityLabel="Go back"
                accessibilityRole="button"
                testID="proactive-input-back"
              >
                <Text style={styles.backButton}>← Back</Text>
              </TouchableOpacity>
              <Text style={styles.headerTitle}>{selectedLabel}</Text>
              <TouchableOpacity
                onPress={handleClose}
                accessibilityLabel="Close"
                accessibilityRole="button"
                testID="proactive-input-close-note"
              >
                <Text style={styles.closeButton}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Note Input */}
            <Text style={styles.noteLabel}>Add a note (optional)</Text>
            <TextInput
              style={styles.noteInput}
              value={note}
              onChangeText={(text) => {
                // Client-side validation: max 500 chars (Requirement 5.3)
                if (text.length <= MAX_NOTE_LENGTH) {
                  setNote(text);
                }
              }}
              placeholder="Type a note..."
              placeholderTextColor="#9CA3AF"
              multiline
              maxLength={MAX_NOTE_LENGTH}
              accessibilityLabel="Optional note"
              testID="proactive-input-note"
            />
            <Text style={styles.charCounter}>
              {note.length}/{MAX_NOTE_LENGTH}
            </Text>

            {/* Submit Button */}
            <TouchableOpacity
              style={[styles.submitButton, submitting && styles.submitButtonDisabled]}
              onPress={handleSubmit}
              disabled={submitting}
              accessibilityLabel="Submit status update"
              accessibilityRole="button"
              testID="proactive-input-submit"
            >
              <Text style={styles.submitButtonText}>
                {submitting ? 'Submitting...' : 'Submit'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    );
  }

  // --- Render: Option Selection ---
  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={handleClose}
    >
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          {/* Header */}
          <View style={styles.header}>
            <Text style={styles.headerTitle}>Report Status</Text>
            <TouchableOpacity
              onPress={handleClose}
              accessibilityLabel="Close status reporting"
              accessibilityRole="button"
              testID="proactive-input-close"
            >
              <Text style={styles.closeButton}>✕</Text>
            </TouchableOpacity>
          </View>

          {/* Options */}
          <ScrollView
            style={styles.optionsList}
            contentContainerStyle={styles.optionsContent}
          >
            {INPUT_OPTIONS.map((option) => (
              <TouchableOpacity
                key={option.type}
                style={styles.optionButton}
                onPress={() => handleOptionSelect(option.type)}
                accessibilityLabel={option.label}
                accessibilityRole="button"
                testID={`proactive-option-${option.type}`}
              >
                <Text style={styles.optionIcon}>{option.icon}</Text>
                <Text style={styles.optionLabel}>{option.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 20,
    paddingBottom: Platform.OS === 'ios' ? 34 : 20, // Safe area for iOS
    paddingTop: 16,
    maxHeight: '80%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
    flex: 1,
    textAlign: 'center',
  },
  closeButton: {
    fontSize: 20,
    color: '#6B7280',
    padding: 4,
  },
  backButton: {
    fontSize: 16,
    color: '#2563EB',
    padding: 4,
  },
  optionsList: {
    flexGrow: 0,
  },
  optionsContent: {
    paddingBottom: 8,
  },
  optionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 20,
    marginBottom: 10,
  },
  optionIcon: {
    fontSize: 22,
    marginRight: 14,
  },
  optionLabel: {
    fontSize: 16,
    fontWeight: '500',
    color: '#1F2937',
  },
  noteLabel: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 8,
  },
  noteInput: {
    backgroundColor: '#F9FAFB',
    borderWidth: 1,
    borderColor: '#D1D5DB',
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    color: '#1F2937',
    minHeight: 100,
    textAlignVertical: 'top',
  },
  charCounter: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'right',
    marginTop: 4,
    marginBottom: 16,
  },
  submitButton: {
    backgroundColor: '#2563EB',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitButtonDisabled: {
    backgroundColor: '#93C5FD',
  },
  submitButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  confirmationContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  confirmationIcon: {
    fontSize: 48,
    color: '#10B981',
    marginBottom: 12,
  },
  confirmationText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
  },
});
