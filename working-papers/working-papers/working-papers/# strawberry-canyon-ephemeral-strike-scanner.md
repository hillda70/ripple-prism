# Strawberry Canyon Ephemeral Strike Scanner

The **Ephemeral Strike Scanner** is a lightweight Python tool for detecting short-lived option-strike activity near the current underlying price. Its purpose is to identify strikes that may matter *right now* because they sit close enough to spot price to become active hedging zones.

The scanner is designed for the **Gamma Garden** and **Strawberry Canyon** workflow: find low-entropy, actionable option signals from simple CSV inputs, preserve the raw evidence, and emit clean rows that can later be pushed into Trello, Airtable, Obsidian, or another execution log.

## Core Idea

The scanner looks for option strikes that are within **one ATR** of the current spot price.

In plain language:

> If a strike is close enough to the underlying price, and there is meaningful open interest and gamma there, it may become a live hedging zone.

The script does not try to predict the market. It filters for **where convexity may become active**.

## Inputs

The scanner expects four basic inputs:

1. A minute CSV from vendor one, such as MarketChameleon.
2. A minute CSV from vendor two, such as Barchart.
3. An options-chain snapshot with strike, side, open interest, gamma, bid, and ask.
4. An ATR14 file for the underlying.

The dual-vendor design is important. The scanner only emits a signal when both vendor feeds agree closely enough on the latest price.

## Dual-Vendor Parity

Before scanning the chain, the script checks whether the two vendor feeds are aligned.

It compares the latest price from both minute files. If the difference is larger than the allowed tolerance, the script stops and emits nothing.

This prevents bad rows from stale data, broken exports, or vendor noise.

The principle is simple:

> No parity, no signal.

## Strike Filtering

Once spot price and ATR are known, the script loops through the option chain.

For every strike, it calculates:

```text
dist_atr = abs(strike - spot) / ATR14
