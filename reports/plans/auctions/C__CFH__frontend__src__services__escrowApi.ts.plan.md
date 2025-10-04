# Plan: C:\CFH\frontend\src\services\escrowApi.ts
**Module:** auctions

## Overview
- Purpose: (fill)
- Dependencies: (fill)

## File Summary
- Path: $p
- Size: 1344
- Modified: 06/11/2025 06:38:18Z

### Extracts
/**
 * @file escrowApi.ts
 * @path C:\CFH\frontend\src\services\escrowApi.ts
 * @author Mini Team
 * @created 2025-06-10 [0823]
 * @purpose Centralizes all API requests and client-side validation for the escrow module.
 * @user_impact Provides a single, reliable point for frontend components to communicate with the backend.
 * @version 1.0.0
 */
import axios from 'axios';
import Joi from 'joi';

const API_URL = '/api/escrow';
const getAuthToken = () => `Bearer ${localStorage.getItem('jwt_token')}`;

export const proposeConditionSchema = Joi.object({
    description: Joi.string().min(50).max(500).required().messages({
        'string.empty': 'Description is required.',
        'string.min': 'Description must be at least 50 characters long.',
        'string.max': 'Description cannot exceed 500 characters.'
    })
});

export const escrowApi = {
    getTransaction: (transactionId: string) => {
        return axios.get(`${API_URL}/transactions/${transactionId}`, {
            headers: { Authorization: getAuthToken() }
        });
    },

    proposeCondition: (transactionId: string, description: string) => {
        return axios.post(`${API_URL}/transactions/${transactionId}/conditions/propose`, { description }, {
            headers: { Authorization: getAuthToken() }
        });
    },
};



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
