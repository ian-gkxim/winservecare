/**
 * Proactive Input Floating Action Button (FAB)
 *
 * A persistent floating circular button fixed to the bottom-right of the screen,
 * always visible and accessible within 2 taps from any screen (Requirement 5.1).
 * On press, opens the ProactiveInputSheet modal.
 */

import React, { useState } from 'react';
import { StyleSheet, TouchableOpacity, Text } from 'react-native';

import ProactiveInputSheet from '@/screens/ProactiveInputSheet';

interface ProactiveInputFABProps {
  /** The current visit ID to associate with the proactive input */
  currentVisitId?: number;
}

export default function ProactiveInputFAB({
  currentVisitId,
}: ProactiveInputFABProps) {
  const [sheetVisible, setSheetVisible] = useState(false);

  const handlePress = () => {
    setSheetVisible(true);
  };

  const handleClose = () => {
    setSheetVisible(false);
  };

  return (
    <>
      <TouchableOpacity
        style={styles.fab}
        onPress={handlePress}
        activeOpacity={0.8}
        accessibilityLabel="Report status update"
        accessibilityRole="button"
        accessibilityHint="Opens status reporting options"
        testID="proactive-input-fab"
      >
        <Text style={styles.fabIcon}>+</Text>
      </TouchableOpacity>

      <ProactiveInputSheet
        visible={sheetVisible}
        onClose={handleClose}
        currentVisitId={currentVisitId}
      />
    </>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    bottom: 24,
    right: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#2563EB',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 6, // Android shadow
    shadowColor: '#000', // iOS shadow
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.27,
    shadowRadius: 4.65,
    zIndex: 999,
  },
  fabIcon: {
    fontSize: 28,
    color: '#FFFFFF',
    fontWeight: 'bold',
    lineHeight: 30,
  },
});
