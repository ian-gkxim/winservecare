/**
 * VisitDetailScreen — displays full details of a scheduled visit.
 *
 * Features:
 * - Patient name, full address, time window, duration, required skills,
 *   patient preferences, current status + confidence indicator
 * - "Open in Maps" button that launches the native maps app with the patient address
 * - Back navigation (handled by React Navigation stack)
 *
 * Requirements: 2.6
 */

import { RouteProp, useRoute } from '@react-navigation/native';
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import apiClient from '@/services/apiClient';
import { MobileVisitDetail, MobileVisitSummary, VisitStatus } from '@/types';

// --- Status colors (shared with ScheduleScreen) ---

const STATUS_COLORS: Record<VisitStatus, string> = {
  [VisitStatus.PENDING]: '#9E9E9E',
  [VisitStatus.TRAVELLING]: '#2196F3',
  [VisitStatus.ARRIVED]: '#03A9F4',
  [VisitStatus.IN_PROGRESS]: '#4CAF50',
  [VisitStatus.COMPLETED]: '#388E3C',
  [VisitStatus.DELAYED]: '#FF9800',
  [VisitStatus.MISSED]: '#F44336',
  [VisitStatus.CANCELLED]: '#757575',
};

const STATUS_LABELS: Record<VisitStatus, string> = {
  [VisitStatus.PENDING]: 'Pending',
  [VisitStatus.TRAVELLING]: 'Travelling',
  [VisitStatus.ARRIVED]: 'Arrived',
  [VisitStatus.IN_PROGRESS]: 'In Progress',
  [VisitStatus.COMPLETED]: 'Completed ✓',
  [VisitStatus.DELAYED]: 'Delayed',
  [VisitStatus.MISSED]: 'Missed',
  [VisitStatus.CANCELLED]: 'Cancelled',
};

// --- Route params type ---

type VisitDetailRouteParams = {
  VisitDetail: {
    visitId: number;
    visit: MobileVisitSummary;
  };
};

// --- Helpers ---

function formatTime(iso: string): string {
  const date = new Date(iso);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * Open the patient address in the device's native maps application.
 * Uses Apple Maps on iOS, Google Maps on Android.
 */
function openInMaps(address: string, lat: number, lng: number): void {
  const encodedAddress = encodeURIComponent(address);

  const url =
    Platform.OS === 'ios'
      ? `maps://app?daddr=${lat},${lng}&q=${encodedAddress}`
      : `geo:${lat},${lng}?q=${encodedAddress}`;

  Linking.canOpenURL(url)
    .then((supported) => {
      if (supported) {
        return Linking.openURL(url);
      }
      // Fallback to Google Maps web URL
      return Linking.openURL(
        `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`
      );
    })
    .catch(() => {
      Alert.alert(
        'Maps Unavailable',
        'Unable to open the maps application. Please ensure a maps app is installed.'
      );
    });
}

// --- Main Screen ---

export default function VisitDetailScreen() {
  const route = useRoute<RouteProp<VisitDetailRouteParams, 'VisitDetail'>>();
  const { visitId, visit: summaryVisit } = route.params;

  const [detail, setDetail] = useState<MobileVisitDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch full visit detail (includes patient_preferences)
  useEffect(() => {
    let cancelled = false;

    async function fetchDetail() {
      try {
        const response = await apiClient.get<MobileVisitDetail>(
          `/api/mobile/schedule/${visitId}`
        );
        if (!cancelled) {
          setDetail(response.data);
        }
      } catch {
        // Fallback to summary data passed via navigation params
        if (!cancelled) {
          setDetail(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchDetail();
    return () => {
      cancelled = true;
    };
  }, [visitId]);

  // Use full detail if available, otherwise fall back to summary
  const visitData = detail ?? summaryVisit;
  const statusColor = STATUS_COLORS[visitData.status];
  const statusLabel = STATUS_LABELS[visitData.status];

  const handleOpenMaps = useCallback(() => {
    openInMaps(
      visitData.patient_address,
      visitData.patient_lat,
      visitData.patient_lng
    );
  }, [visitData]);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Patient Name */}
      <Text style={styles.patientName}>{visitData.patient_name}</Text>

      {/* Status + Confidence */}
      <View style={styles.statusRow}>
        <View style={[styles.statusPill, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
        <View style={styles.confidenceContainer}>
          <View
            style={[
              styles.confidenceBar,
              {
                width: `${visitData.confidence_score}%`,
                backgroundColor: statusColor,
              },
            ]}
          />
          <Text style={styles.confidenceText}>
            {visitData.confidence_score}% confidence
          </Text>
        </View>
      </View>

      {/* Address */}
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>Address</Text>
        <Text style={styles.sectionValue}>{visitData.patient_address}</Text>
      </View>

      {/* Time Window */}
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>Time Window</Text>
        <Text style={styles.sectionValue}>
          {formatTime(visitData.window_start)} –{' '}
          {formatTime(visitData.window_end)}
        </Text>
      </View>

      {/* Duration */}
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>Duration</Text>
        <Text style={styles.sectionValue}>
          {visitData.duration_minutes} minutes
        </Text>
      </View>

      {/* Required Skills */}
      <View style={styles.section}>
        <Text style={styles.sectionLabel}>Required Skills</Text>
        {visitData.required_skills.length > 0 ? (
          <View style={styles.skillsRow}>
            {visitData.required_skills.map((skill) => (
              <View key={skill} style={styles.skillBadge}>
                <Text style={styles.skillText}>{skill}</Text>
              </View>
            ))}
          </View>
        ) : (
          <Text style={styles.noDataText}>None specified</Text>
        )}
      </View>

      {/* Patient Preferences (only available in full detail) */}
      {detail?.patient_preferences && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Patient Preferences</Text>
          {detail.patient_preferences.length > 0 ? (
            <View style={styles.preferencesList}>
              {detail.patient_preferences.map((pref, idx) => (
                <View key={idx} style={styles.preferenceItem}>
                  <Text style={styles.bulletPoint}>•</Text>
                  <Text style={styles.preferenceText}>{pref}</Text>
                </View>
              ))}
            </View>
          ) : (
            <Text style={styles.noDataText}>None specified</Text>
          )}
        </View>
      )}

      {/* Open in Maps button */}
      <TouchableOpacity
        style={styles.mapsButton}
        onPress={handleOpenMaps}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel="Open address in maps for navigation"
      >
        <Text style={styles.mapsButtonText}>Open in Maps</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  patientName: {
    fontSize: 22,
    fontWeight: '700',
    color: '#212121',
    marginBottom: 12,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 20,
  },
  statusPill: {
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 4,
    marginRight: 12,
  },
  statusText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  confidenceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  confidenceBar: {
    height: 5,
    borderRadius: 3,
    width: 50,
    marginRight: 6,
  },
  confidenceText: {
    fontSize: 12,
    color: '#757575',
  },
  section: {
    marginBottom: 18,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9E9E9E',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  sectionValue: {
    fontSize: 16,
    color: '#333333',
  },
  skillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 4,
  },
  skillBadge: {
    backgroundColor: '#E3F2FD',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  skillText: {
    fontSize: 13,
    color: '#1565C0',
    fontWeight: '500',
  },
  noDataText: {
    fontSize: 14,
    color: '#BDBDBD',
    fontStyle: 'italic',
  },
  preferencesList: {
    marginTop: 4,
  },
  preferenceItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 4,
  },
  bulletPoint: {
    fontSize: 16,
    color: '#4CAF50',
    marginRight: 8,
    lineHeight: 22,
  },
  preferenceText: {
    fontSize: 14,
    color: '#333333',
    flex: 1,
    lineHeight: 22,
  },
  mapsButton: {
    backgroundColor: '#2196F3',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 24,
  },
  mapsButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '700',
  },
});
