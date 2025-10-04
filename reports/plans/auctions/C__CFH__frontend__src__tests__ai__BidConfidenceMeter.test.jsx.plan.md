# Plan: C:\CFH\frontend\src\tests\ai\BidConfidenceMeter.test.jsx
**Module:** auctions

## Overview
- Purpose: (fill)
- Dependencies: (fill)

## File Summary
- Path: $p
- Size: 3360
- Modified: 05/17/2025 18:18:12Z

### Extracts
```
// 👑 Crown Certified Test — BidConfidenceMeter.test.jsx
// Path: frontend/src/tests/ai/BidConfidenceMeter.test.jsx
// Purpose: Unit tests for BidConfidenceMeter component, covering rendering, premium gating, API calls, and error states.
// Author: Rivers Auction Team — May 17, 2025

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import BidConfidenceMeter from '@components/ai/BidConfidenceMeter';
import { api } from '@services/api';
import logger from '@utils/logger';

jest.mock('@services/api');
jest.mock('@utils/logger', () => ({
  error: jest.fn(),
}));

describe('BidConfidenceMeter', () => {
  const mockProps = {
    auctionId: 'a1',
    bidAmount: 1000,
    isPremium: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders confidence score for non-premium user', async () => {
    api.get.mockResolvedValue({
      data: { data: { prediction: { successProbability: 0.75 } } },
    });

    render(<BidConfidenceMeter {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Bid Confidence Meter')).toBeInTheDocument();
      expect(screen.getByText(/Confidence Score: 75.0%/i)).toBeInTheDocument();
      expect(screen.queryByText(/Advice:/i)).not.toBeInTheDocument();
    });
  });

  it('renders bidding advice for premium user', asyn
...


## Consolidated Specs (draft)
- interface BidProps { amount: number; userId: string }

## Risks & Suggestions
- (fill) Consider AbortController for network races.

## Tiered Plan
- Free: basic extracts
- Premium: @aliases, typed props
- Wow++: monetization hooks

## TS Build Plan (draft)
- src/shared.ts
- src/index.ts
