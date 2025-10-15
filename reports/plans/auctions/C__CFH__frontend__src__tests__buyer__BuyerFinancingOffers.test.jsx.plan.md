# Plan: C:\CFH\frontend\src\tests\buyer\BuyerFinancingOffers.test.jsx
**Module:** auctions

## Overview
- Purpose: (fill)
- Dependencies: (fill)

## File Summary
- Path: $p
- Size: 1727
- Modified: 05/15/2025 14:44:58Z

### Extracts
// File: BuyerFinancingOffers.test.jsx
// Path: frontend/src/tests/buyer/BuyerFinancingOffers.test.jsx
// Purpose: Validate rendering of lender offers and premium AI ranking
// Author: Cod1 - Rivers Auction QA
// Date: May 14, 2025
// 👑 Cod1 Crown Certified

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import BuyerFinancingOffers from '@components/buyer/BuyerFinancingOffers';

jest.mock('axios');

describe('BuyerFinancingOffers Component', () => {
  const mockOffers = [
    { id: 'o1', lenderName: 'Bank A', apr: 3.2, term: 36 },
    { id: 'o2', lenderName: 'Credit Union B', apr: 2.9, term: 48 },
  ];

  it('renders basic offers for free user', async () => {
    axios.get.mockResolvedValueOnce({ data: { offers: mockOffers } });
    render(<BuyerFinancingOffers buyerId="b1" auctionId="a1" isPremium={false} />);
    await waitFor(() => expect(screen.getByText(/Bank A/)).toBeInTheDocument());
    expect(screen.getByText(/Upgrade to premium/)).toBeInTheDocument();
  });

  it('renders comparison grid for premium user', async () => {
    axios.get.mockResolvedValueOnce({ data: { offers: mockOffers } });
    render(<BuyerFinancingOffers buyerId="b1" auctionId="a1" isPremium />);
    await waitFor(() => expect(screen.getByText(/Financing Offers/)).toBeInTheDocument());
  });

  
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
