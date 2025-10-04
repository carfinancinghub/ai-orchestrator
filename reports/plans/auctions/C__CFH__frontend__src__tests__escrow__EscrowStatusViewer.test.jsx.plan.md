# Plan: C:\CFH\frontend\src\tests\escrow\EscrowStatusViewer.test.jsx
**Module:** auctions

## Overview
- Purpose: (fill)
- Dependencies: (fill)

## File Summary
- Path: $p
- Size: 4181
- Modified: 05/17/2025 04:30:30Z

### Extracts
```
// 👑 Crown Certified Test — EscrowStatusViewer.test.jsx
// Path: frontend/src/tests/escrow/EscrowStatusViewer.test.jsx
// Purpose: Unit tests for EscrowStatusViewer component, covering rendering, premium gating, API calls, and error states.
// Author: Rivers Auction Team — May 16, 2025

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EscrowStatusViewer from '@components/escrow/EscrowStatusViewer';
import { api } from '@services/api';
import logger from '@utils/logger';

jest.mock('@services/api');
jest.mock('@utils/logger', () => ({
  error: jest.fn(),
}));

describe('EscrowStatusViewer', () => {
  const mockTransactionId = 'tx1';
  const mockStatus = {
    transactionId: 'tx1',
    actionType: 'create',
    userId: 'u1',
    status: 'pending',
    createdAt: '2025-05-16T12:00:00Z',
  };
  const mockAuditTrail = [{ event: 'created', timestamp: '2025-05-16' }];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders transaction status', async () => {
    api.get.mockResolvedValue({ data: { data: mockStatus } });

    render(<EscrowStatusViewer transactionId={mockTransactionId} isPremium={false} />);

    await waitFor(() => {
      expect(screen.getByText('Escrow Status')).toBeInTheDocument();
      expect(screen.getByText('tx1')).toBeInTheDocument();
      ex
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
