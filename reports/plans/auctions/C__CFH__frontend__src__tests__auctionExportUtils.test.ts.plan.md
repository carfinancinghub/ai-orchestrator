# Plan: C:\CFH\frontend\src\tests\auctionExportUtils.test.ts
**Module:** auctions

## Overview
- Purpose: (fill)
- Dependencies: (fill)

## File Summary
- Path: $p
- Size: 3644
- Modified: 07/22/2025 06:09:48Z

### Extracts
// File: auctionExportUtils.test.ts
// Path: frontend/src/tests/auctionExportUtils.test.ts
// Author: Cod5 (07212245, July 21, 2025, 22:45 PDT)
// Purpose: Unit tests for auctionExportUtils.ts to ensure reliable auction data and dispute summary exports

import { exportAuctionDataAsCSV, exportAuctionSummaryAsPDF, exportDisputeSummaryAsPDF } from '@utils/auction/auctionExportUtils';
import axios from '@utils/axios';
import { logError } from '@utils/logger';
import { toast } from '@utils/react-toastify';

// Mock dependencies
jest.mock('@utils/axios', () => ({
  post: jest.fn(),
}));
jest.mock('@utils/logger', () => ({ logError: jest.fn() }));
jest.mock('@utils/react-toastify', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

describe('auctionExportUtils', () => {
  const mockAuctions = [
    { id: '1', title: 'Toyota Camry', currentBid: 15000, timeRemaining: '2h 30m' },
    { id: '2', title: 'Honda Civic', currentBid: 12000, timeRemaining: '1h 15m' },
  ];
  const mockSummaryData = {
    totalAuctions: 2,
    totalBidValue: 27000,
    trendingVehicles: [{ make: 'Toyota', model: 'Camry', count: 1 }],
  };
  const mockVotes = [{ vote: 'for' }, { vote: 'against' }];

  beforeEach(() => {
    jest.clearAllMocks();
    (axios.post as jest.Mock).mockResolvedValue({ data: { url: 'mock-url' } });
  });

  it('exports auction data as CSV', a
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
