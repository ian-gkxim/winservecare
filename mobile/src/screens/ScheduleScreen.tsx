/**
 * ScheduleScreen — displays the carer's visits for today, sorted by window_start.
 *
 * Features:
 * - FlatList with visit cards showing patient name, address, time window, duration,
 *   required skills badges, and status pill with confidence indicator
 * - Pull-to-refresh gesture
 * - Auto-refresh every 60 seconds
 * - Offline mode: shows cached data with a persistent top banner
 * - Empty state: "No visits scheduled for today"
 * - Error state: error message with "Try Again" button
 * - Tap on visit → navigate to VisitDetailScreen
 *
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
 */

import NetInfo from '@react-native-community/netinfo';
import { useNavigation } from '@react-navigation/native';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import apiClient from '@/services/apiClient';
import { cacheSchedule, getCachedSchedule } from '@/services/scheduleCache';
import { MobileVisitSummary, VisitStatus } from '@/types';

// --- Status pill color mapping ---

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

// --- Helpers ---

/**
 * Format an ISO timestamp to a short time string (HH:MM).
 */
function formatTime(iso: string): string {
  const date = new Date(iso);
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

// --- Components ---

interface VisitCardProps {
  visit: MobileVisitSummary;
  onPress: (visit: MobileVisitSummary) => void;
}

function VisitCard({ visit, onPress }: VisitCardProps) {
  const statusColor = STATUS_COLORS[visit.status];
  const statusLabel = STATUS_LABELS[visit.status];

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => onPress(visit)}
      activeOpacity={0.7}
      accessibilityRole="button"
      accessibilityLabel={`Visit to ${visit.patient_name} at ${formatTime(visit.window_start)}`}
    >
      {/* Header: patient name + status pill */}
      <View style={styles.cardHeader}>
        <Text style={styles.patientName} numberOfLines={1}>
          {visit.patient_name}
        </Text>
        <View style={[styles.statusPill, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
      </View>

      {/* Address */}
      <Text style={styles.address} numberOfLines={2}>
        {visit.patient_address}
      </Text>

      {/* Time window, duration, confidence */}
      <View style={styles.metaRow}>
        <Text style={styles.timeWindow}>
          {formatTime(visit.window_start)} – {formatTime(visit.window_end)}
        </Text>
        <Text style={styles.duration}>{visit.duration_minutes} min</Text>
        <View style={styles.confidenceContainer}>
          <View
            style={[
              styles.confidenceBar,
              { width: `${visit.confidence_score}%`, backgroundColor: statusColor },
            ]}
          />
          <Text style={styles.confidenceText}>{visit.confidence_score}%</Text>
        </View>
      </View>

      {/* Skills badges */}
      {visit.required_skills.length > 0 && (
        <View style={styles.skillsRow}>
          {visit.required_skills.map((skill) => (
            <View key={skill} style={styles.skillBadge}>
              <Text style={styles.skillText}>{skill}</Text>
            </View>
          ))}
        </View>
      )}
    </TouchableOpacity>
  );
}

// --- Main Screen ---

export default function ScheduleScreen() {
  const navigation = useNavigation<any>();
  const [visits, setVisits] = useState<MobileVisitSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // --- Network connectivity monitoring ---
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      setIsOffline(!state.isConnected);
    });
    return () => unsubscribe();
  }, []);

  // --- Fetch schedule from backend or cache ---
  const fetchSchedule = useCallback(
    async (showRefreshIndicator = false) => {
      if (showRefreshIndicator) setIsRefreshing(true);
      setError(null);

      try {
        const netState = await NetInfo.fetch();

        if (!netState.isConnected) {
          // Offline: load from cache
          const cached = await getCachedSchedule();
          setVisits(cached);
          setIsOffline(true);
        } else {
          // Online: fetch from backend
          const response = await apiClient.get<MobileVisitSummary[]>(
            '/api/mobile/schedule'
          );
          const sortedVisits = response.data.sort(
            (a, b) =>
              new Date(a.window_start).getTime() -
              new Date(b.window_start).getTime()
          );
          setVisits(sortedVisits);
          setIsOffline(false);

          // Cache for offline use
          await cacheSchedule(sortedVisits);
        }
      } catch (err: any) {
        // On failure, try to show cached data
        try {
          const cached = await getCachedSchedule();
          if (cached.length > 0) {
            setVisits(cached);
            setError('Could not refresh schedule. Showing cached data.');
          } else {
            setError(
              err?.message || 'Failed to load schedule. Please try again.'
            );
          }
        } catch {
          setError(
            err?.message || 'Failed to load schedule. Please try again.'
          );
        }
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    []
  );

  // --- Initial load ---
  useEffect(() => {
    fetchSchedule();
  }, [fetchSchedule]);

  // --- Auto-refresh every 60 seconds ---
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      fetchSchedule();
    }, 60_000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchSchedule]);

  // --- Navigation to detail ---
  const handleVisitPress = useCallback(
    (visit: MobileVisitSummary) => {
      navigation.navigate('VisitDetail', { visitId: visit.id, visit });
    },
    [navigation]
  );

  // --- Pull-to-refresh ---
  const handleRefresh = useCallback(() => {
    fetchSchedule(true);
  }, [fetchSchedule]);

  // --- Render helpers ---

  const renderEmptyState = () => {
    if (isLoading) return null;

    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>No visits scheduled for today</Text>
      </View>
    );
  };

  const renderErrorState = () => {
    if (!error || visits.length > 0) return null;

    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity
          style={styles.retryButton}
          onPress={() => fetchSchedule()}
          accessibilityRole="button"
          accessibilityLabel="Try again"
        >
          <Text style={styles.retryButtonText}>Try Again</Text>
        </TouchableOpacity>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Persistent offline banner */}
      {isOffline && (
        <View style={styles.offlineBanner} accessibilityRole="alert">
          <Text style={styles.offlineBannerText}>
            You are offline. Showing cached schedule.
          </Text>
        </View>
      )}

      {/* Soft error banner when we have data but fetch failed */}
      {error && visits.length > 0 && (
        <View style={styles.softErrorBanner}>
          <Text style={styles.softErrorText}>{error}</Text>
        </View>
      )}

      {/* Visit list or empty/error state */}
      {error && visits.length === 0 ? (
        renderErrorState()
      ) : (
        <FlatList
          data={visits}
          keyExtractor={(item) => item.id.toString()}
          renderItem={({ item }) => (
            <VisitCard visit={item} onPress={handleVisitPress} />
          )}
          contentContainerStyle={
            visits.length === 0 ? styles.listEmpty : styles.listContent
          }
          ListEmptyComponent={renderEmptyState}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor="#2196F3"
            />
          }
        />
      )}
    </View>
  );
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  offlineBanner: {
    backgroundColor: '#FF9800',
    paddingVertical: 8,
    paddingHorizontal: 16,
    alignItems: 'center',
  },
  offlineBannerText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '600',
  },
  softErrorBanner: {
    backgroundColor: '#FFF3E0',
    paddingVertical: 6,
    paddingHorizontal: 16,
    alignItems: 'center',
  },
  softErrorText: {
    color: '#E65100',
    fontSize: 12,
  },
  listContent: {
    padding: 12,
    paddingBottom: 24,
  },
  listEmpty: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  patientName: {
    fontSize: 16,
    fontWeight: '700',
    color: '#212121',
    flex: 1,
    marginRight: 8,
  },
  statusPill: {
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  statusText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  address: {
    fontSize: 13,
    color: '#616161',
    marginBottom: 8,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  timeWindow: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333333',
    marginRight: 12,
  },
  duration: {
    fontSize: 13,
    color: '#757575',
    marginRight: 12,
  },
  confidenceContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  confidenceBar: {
    height: 4,
    borderRadius: 2,
    maxWidth: 40,
    marginRight: 4,
  },
  confidenceText: {
    fontSize: 11,
    color: '#9E9E9E',
  },
  skillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  skillBadge: {
    backgroundColor: '#E3F2FD',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  skillText: {
    fontSize: 11,
    color: '#1565C0',
    fontWeight: '500',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  emptyText: {
    fontSize: 16,
    color: '#9E9E9E',
    textAlign: 'center',
  },
  errorContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  errorText: {
    fontSize: 15,
    color: '#D32F2F',
    textAlign: 'center',
    marginBottom: 16,
  },
  retryButton: {
    backgroundColor: '#2196F3',
    borderRadius: 8,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '600',
  },
});
