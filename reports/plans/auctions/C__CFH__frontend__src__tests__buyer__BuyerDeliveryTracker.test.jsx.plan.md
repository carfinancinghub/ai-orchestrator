# Plan: C:\CFH\frontend\src\tests\buyer\BuyerDeliveryTracker.test.jsx
**Module:** auctions

## Overview
- Purpose: (fill)
- Dependencies: (fill)

## File Summary
- Path: $p
- Size: 1673
- Modified: 05/15/2025 14:44:58Z

### Extracts
// File: BuyerDeliveryTracker.test.jsx
// Path: frontend/src/tests/buyer/BuyerDeliveryTracker.test.jsx
// Purpose: Verify delivery tracking + map rendering
// Author: Cod1 - Rivers Auction QA
// Date: May 14, 2025
// 👑 Cod1 Crown Certified

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import BuyerDeliveryTracker from '@components/buyer/BuyerDeliveryTracker';

jest.mock('axios');

describe('BuyerDeliveryTracker Component', () => {
  const mockDelivery = {
    stage: 'In Transit',
    lastUpdated: new Date().toISOString(),
    location: { lat: 34.05, lng: -118.24 },
  };

  it('renders delivery info (free user)', async () => {
    axios.get.mockResolvedValueOnce({ data: { status: mockDelivery } });

    render(<BuyerDeliveryTracker deliveryId="del123" isPremium={false} />);
    await waitFor(() => expect(screen.getByText(/In Transit/)).toBeInTheDocument());
    expect(screen.getByText(/Real-time tracking available/)).toBeInTheDocument();
  });

  it('renders live map for premium', async () => {
    axios.get.mockResolvedValueOnce({ data: { status: mockDelivery } });

    render(<BuyerDeliveryTracker deliveryId="del123" isPremium />);
    await waitFor(() => expect(screen.getByText(/Delivery Tracker/)).toBeInTheDocument());
  });

  it('shows error on fetch failure', asy
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
