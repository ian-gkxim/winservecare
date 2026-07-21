import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { RecommendationsPanel } from './RecommendationsPanel';
import { Recommendation } from '../types';

const sampleRecommendations: Recommendation[] = [
  {
    id: 1,
    type: 'recommendation',
    title: 'Rebalance workloads',
    description: 'Carer A has 8 visits while Carer B has only 3. Consider redistributing.',
    impact: 8,
  },
  {
    id: 2,
    type: 'warning',
    title: 'Carer C approaching overtime',
    description: 'Carer C is scheduled for 7.5 of 8 maximum hours.',
    impact: 9,
  },
  {
    id: 3,
    type: 'recommendation',
    title: 'Reduce travel for route 4',
    description: 'Swapping visits 12 and 14 would save 15 minutes of travel time.',
    impact: 5,
  },
];

describe('RecommendationsPanel', () => {
  describe('empty state', () => {
    it('displays empty message when no items provided', () => {
      render(<RecommendationsPanel items={[]} />);

      expect(screen.getByText('No recommendations available')).toBeInTheDocument();
    });

    it('renders accessible region', () => {
      render(<RecommendationsPanel items={[]} />);

      expect(screen.getByRole('region', { name: 'Recommendations' })).toBeInTheDocument();
    });
  });

  describe('rendering items', () => {
    it('renders all items with titles and descriptions', () => {
      render(<RecommendationsPanel items={sampleRecommendations} />);

      expect(screen.getByText('Rebalance workloads')).toBeInTheDocument();
      expect(screen.getByText('Carer C approaching overtime')).toBeInTheDocument();
      expect(screen.getByText('Reduce travel for route 4')).toBeInTheDocument();
    });

    it('orders items by impact descending', () => {
      render(<RecommendationsPanel items={sampleRecommendations} />);

      const listItems = screen.getAllByRole('listitem');
      expect(listItems).toHaveLength(3);

      // Impact 9 should be first
      expect(within(listItems[0]).getByText('Carer C approaching overtime')).toBeInTheDocument();
      // Impact 8 second
      expect(within(listItems[1]).getByText('Rebalance workloads')).toBeInTheDocument();
      // Impact 5 third
      expect(within(listItems[2]).getByText('Reduce travel for route 4')).toBeInTheDocument();
    });

    it('limits display to 10 items maximum', () => {
      const manyItems: Recommendation[] = Array.from({ length: 15 }, (_, i) => ({
        id: i + 1,
        type: 'recommendation' as const,
        title: `Recommendation ${i + 1}`,
        description: `Description for item ${i + 1}`,
        impact: 15 - i,
      }));

      render(<RecommendationsPanel items={manyItems} />);

      const listItems = screen.getAllByRole('listitem');
      expect(listItems).toHaveLength(10);
    });

    it('displays the top 10 by impact when more than 10 are provided', () => {
      const manyItems: Recommendation[] = Array.from({ length: 15 }, (_, i) => ({
        id: i + 1,
        type: 'recommendation' as const,
        title: `Rec ${i + 1}`,
        description: `Desc ${i + 1}`,
        impact: i + 1, // lower ids have lower impact
      }));

      render(<RecommendationsPanel items={manyItems} />);

      // Top 10 by impact: items with impact 15..6 (ids 15..6)
      expect(screen.getByText('Rec 15')).toBeInTheDocument();
      expect(screen.getByText('Rec 6')).toBeInTheDocument();
      // Item with impact 5 (id 5) should not be displayed
      expect(screen.queryByText('Rec 5')).not.toBeInTheDocument();
    });
  });

  describe('visual distinction between types', () => {
    it('renders warning icon for warning items', () => {
      render(<RecommendationsPanel items={[sampleRecommendations[1]]} />);

      expect(screen.getByText('⚠️')).toBeInTheDocument();
    });

    it('renders lightbulb icon for recommendation items', () => {
      render(<RecommendationsPanel items={[sampleRecommendations[0]]} />);

      expect(screen.getByText('💡')).toBeInTheDocument();
    });

    it('applies amber border for warnings', () => {
      render(<RecommendationsPanel items={[sampleRecommendations[1]]} />);

      const listItem = screen.getByRole('listitem');
      expect(listItem.className).toContain('border-l-amber-400');
    });

    it('applies blue border for recommendations', () => {
      render(<RecommendationsPanel items={[sampleRecommendations[0]]} />);

      const listItem = screen.getByRole('listitem');
      expect(listItem.className).toContain('border-l-blue-400');
    });
  });

  describe('description truncation', () => {
    it('truncates descriptions longer than 200 characters', () => {
      const longDescription = 'A'.repeat(250);
      const item: Recommendation = {
        id: 1,
        type: 'recommendation',
        title: 'Long desc',
        description: longDescription,
        impact: 5,
      };

      render(<RecommendationsPanel items={[item]} />);

      const descEl = screen.getByText('A'.repeat(200));
      expect(descEl).toBeInTheDocument();
      // Should not contain the full 250-char string
      expect(screen.queryByText(longDescription)).not.toBeInTheDocument();
    });

    it('does not truncate descriptions at or under 200 characters', () => {
      const exactDescription = 'B'.repeat(200);
      const item: Recommendation = {
        id: 1,
        type: 'recommendation',
        title: 'Exact desc',
        description: exactDescription,
        impact: 5,
      };

      render(<RecommendationsPanel items={[item]} />);

      expect(screen.getByText(exactDescription)).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible labels on list items', () => {
      render(<RecommendationsPanel items={sampleRecommendations} />);

      expect(
        screen.getByLabelText('Warning: Carer C approaching overtime')
      ).toBeInTheDocument();
      expect(
        screen.getByLabelText('Recommendation: Rebalance workloads')
      ).toBeInTheDocument();
    });

    it('renders with list role', () => {
      render(<RecommendationsPanel items={sampleRecommendations} />);

      expect(screen.getByRole('list')).toBeInTheDocument();
    });
  });
});
