/**
 * QuestionOverlay — Non-intrusive notification overlay for contextual questions.
 *
 * Displays at the top of the screen without blocking interaction with the rest of the app.
 * Supports three question types:
 * - yes_no: Two buttons (Yes / No)
 * - single_choice: List of option buttons (max 5)
 * - free_text: Text input (max 300 chars) with submit button
 *
 * On response: creates QuestionResponse with timestamp, pipes to offline buffer
 * via questionHandler.submitResponse(), and dismisses with animation.
 *
 * Requirements: 4.2, 4.3, 4.4, 4.5, 4.7
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Animated,
  Keyboard,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { ContextualQuestionPayload, QuestionType } from '@/types';
import { submitResponse, dismissActiveQuestion, displayNextQueued } from '@/services/questionHandler';

// --- Constants ---

const MAX_FREE_TEXT_LENGTH = 300;
const ANIMATION_DURATION_MS = 300;

// --- Props ---

export interface QuestionOverlayProps {
  question: ContextualQuestionPayload | null;
  onDismiss?: () => void;
}

// --- Component ---

export default function QuestionOverlay({
  question,
  onDismiss,
}: QuestionOverlayProps): React.JSX.Element | null {
  const [freeText, setFreeText] = useState('');
  const [isVisible, setIsVisible] = useState(false);
  const slideAnim = useRef(new Animated.Value(-200)).current;

  // Show/hide animation when question changes
  useEffect(() => {
    if (question) {
      setIsVisible(true);
      setFreeText('');
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: ANIMATION_DURATION_MS,
        useNativeDriver: true,
      }).start();
    } else {
      animateOut();
    }
  }, [question]);

  const animateOut = useCallback(() => {
    Animated.timing(slideAnim, {
      toValue: -200,
      duration: ANIMATION_DURATION_MS,
      useNativeDriver: true,
    }).start(() => {
      setIsVisible(false);
    });
  }, [slideAnim]);

  const handleResponse = useCallback(
    (responseText: string) => {
      Keyboard.dismiss();
      submitResponse(responseText);
      animateOut();
      onDismiss?.();

      // After a brief delay, show next queued question if available
      setTimeout(() => {
        displayNextQueued();
      }, ANIMATION_DURATION_MS + 100);
    },
    [animateOut, onDismiss]
  );

  const handleDismissTimeout = useCallback(() => {
    dismissActiveQuestion();
    animateOut();
    onDismiss?.();

    setTimeout(() => {
      displayNextQueued();
    }, ANIMATION_DURATION_MS + 100);
  }, [animateOut, onDismiss]);

  if (!isVisible || !question) return null;

  return (
    <Animated.View
      style={[
        styles.container,
        { transform: [{ translateY: slideAnim }] },
      ]}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={styles.card}>
        {/* Question text */}
        <Text style={styles.questionText} accessibilityRole="text">
          {question.question_text}
        </Text>

        {/* Response UI based on question type */}
        {renderResponseUI(question.question_type, question.options, freeText, setFreeText, handleResponse)}

        {/* Dismiss button */}
        <TouchableOpacity
          style={styles.dismissButton}
          onPress={handleDismissTimeout}
          accessibilityLabel="Dismiss question"
          accessibilityRole="button"
        >
          <Text style={styles.dismissText}>Dismiss</Text>
        </TouchableOpacity>
      </View>
    </Animated.View>
  );
}

// --- Response UI Renderer ---

function renderResponseUI(
  questionType: QuestionType,
  options: string[] | undefined,
  freeText: string,
  setFreeText: (text: string) => void,
  onResponse: (text: string) => void
): React.JSX.Element {
  switch (questionType) {
    case 'yes_no':
      return (
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.optionButton, styles.yesButton]}
            onPress={() => onResponse('yes')}
            accessibilityLabel="Yes"
            accessibilityRole="button"
          >
            <Text style={styles.optionButtonText}>Yes</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.optionButton, styles.noButton]}
            onPress={() => onResponse('no')}
            accessibilityLabel="No"
            accessibilityRole="button"
          >
            <Text style={styles.optionButtonText}>No</Text>
          </TouchableOpacity>
        </View>
      );

    case 'single_choice':
      return (
        <View style={styles.optionsList}>
          {(options ?? []).slice(0, 5).map((option, index) => (
            <TouchableOpacity
              key={`option-${index}`}
              style={styles.choiceButton}
              onPress={() => onResponse(option)}
              accessibilityLabel={option}
              accessibilityRole="button"
            >
              <Text style={styles.choiceButtonText}>{option}</Text>
            </TouchableOpacity>
          ))}
        </View>
      );

    case 'free_text':
      return (
        <View style={styles.freeTextContainer}>
          <TextInput
            style={styles.textInput}
            value={freeText}
            onChangeText={(text) => setFreeText(text.slice(0, MAX_FREE_TEXT_LENGTH))}
            placeholder="Type your response..."
            placeholderTextColor="#999"
            maxLength={MAX_FREE_TEXT_LENGTH}
            multiline
            accessibilityLabel="Response text input"
            accessibilityHint={`Maximum ${MAX_FREE_TEXT_LENGTH} characters`}
          />
          <Text style={styles.charCount}>
            {freeText.length}/{MAX_FREE_TEXT_LENGTH}
          </Text>
          <TouchableOpacity
            style={[
              styles.submitButton,
              freeText.trim().length === 0 && styles.submitButtonDisabled,
            ]}
            onPress={() => onResponse(freeText.trim())}
            disabled={freeText.trim().length === 0}
            accessibilityLabel="Submit response"
            accessibilityRole="button"
          >
            <Text style={styles.submitButtonText}>Submit</Text>
          </TouchableOpacity>
        </View>
      );

    default:
      return <View />;
  }
}

// --- Styles ---

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 1000,
    paddingTop: 50, // Account for status bar
    paddingHorizontal: 12,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 6,
  },
  questionText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1a1a1a',
    marginBottom: 12,
    lineHeight: 22,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 8,
  },
  optionButton: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  yesButton: {
    backgroundColor: '#4CAF50',
  },
  noButton: {
    backgroundColor: '#F44336',
  },
  optionButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  optionsList: {
    gap: 8,
    marginBottom: 8,
  },
  choiceButton: {
    backgroundColor: '#E3F2FD',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#1976D2',
  },
  choiceButtonText: {
    color: '#1976D2',
    fontSize: 15,
    fontWeight: '500',
  },
  freeTextContainer: {
    marginBottom: 8,
  },
  textInput: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    minHeight: 80,
    maxHeight: 120,
    textAlignVertical: 'top',
    color: '#1a1a1a',
  },
  charCount: {
    fontSize: 12,
    color: '#999',
    textAlign: 'right',
    marginTop: 4,
    marginBottom: 8,
  },
  submitButton: {
    backgroundColor: '#1976D2',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  submitButtonDisabled: {
    backgroundColor: '#B0BEC5',
  },
  submitButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  dismissButton: {
    alignItems: 'center',
    paddingVertical: 8,
    marginTop: 4,
  },
  dismissText: {
    color: '#757575',
    fontSize: 14,
  },
});
