import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type {
  Trade, GateDecision, Control, PnlSummary, PnlPoint, TradeProposal,
  IbStatus, IbAccount, IbPosition, IbExecution, IbOrders, IbList, FlexData, IbPnl, IbNavSeries,
} from "./types";

// All data flows through one RTK Query slice — automatic caching, refetching, and loading state.
export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({ baseUrl: "/api" }),
  tagTypes: ["Control", "Proposals"],
  // Poll live-ish views every 15s.
  refetchOnFocus: true,
  endpoints: (b) => ({
    // ---- Bot DB (Postgres) ----
    positions: b.query<Trade[], void>({ query: () => "/positions" }),
    trades: b.query<Trade[], number | void>({ query: (limit = 200) => `/trades?limit=${limit}` }),
    gateDecisions: b.query<GateDecision[], number | void>({
      query: (limit = 200) => `/gate-decisions?limit=${limit}` }),
    pnl: b.query<PnlSummary, void>({ query: () => "/pnl" }),
    pnlSeries: b.query<PnlPoint[], void>({ query: () => "/pnl-series" }),
    control: b.query<Control, void>({ query: () => "/control", providesTags: ["Control"] }),
    setControl: b.mutation<Control, { trading_enabled: boolean; notes?: string }>({
      query: (body) => ({ url: "/control", method: "POST",
        body: { ...body, updated_by: "console" } }),
      invalidatesTags: ["Control"],
    }),
    // ---- Manual entry approval ----
    proposals: b.query<TradeProposal[], number | void>({
      query: (limit = 100) => `/proposals?limit=${limit}`, providesTags: ["Proposals"] }),
    decideProposal: b.mutation<TradeProposal,
      { id: number; decision: "approve" | "reject"; note?: string; quantity?: number }>({
      query: ({ id, decision, note, quantity }) => ({
        url: `/proposals/${id}/${decision}`, method: "POST",
        body: { note: note ?? null, decided_by: "console", quantity: quantity ?? null } }),
      invalidatesTags: ["Proposals"],
    }),
    // ---- Live IBKR paper account (read-only) ----
    ibStatus: b.query<IbStatus, void>({ query: () => "/ib/status" }),
    ibAccount: b.query<IbAccount, void>({ query: () => "/ib/account" }),
    ibPositions: b.query<IbList<IbPosition>, void>({ query: () => "/ib/positions" }),
    ibExecutions: b.query<IbList<IbExecution>, void>({ query: () => "/ib/executions" }),
    ibOrders: b.query<IbOrders, void>({ query: () => "/ib/orders" }),
    // ---- Real TWS account data (paper) ----
    ibPnl: b.query<IbPnl, void>({ query: () => "/ib/pnl" }),
    ibNavSeries: b.query<IbNavSeries, void>({ query: () => "/ib/nav-series" }),
    flexData: b.query<FlexData, void>({ query: () => "/flex/data" }),
  }),
});

export const {
  usePositionsQuery, useTradesQuery, useGateDecisionsQuery, usePnlQuery, usePnlSeriesQuery,
  useControlQuery, useSetControlMutation, useProposalsQuery, useDecideProposalMutation,
  useIbStatusQuery, useIbAccountQuery, useIbPositionsQuery, useIbExecutionsQuery, useIbOrdersQuery,
  useIbPnlQuery, useIbNavSeriesQuery, useFlexDataQuery,
} = api;
