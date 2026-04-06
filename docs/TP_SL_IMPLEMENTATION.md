# Take Profit & Stop Loss Implementation

## Critical Requirement
**After TP1 is hit, stop-loss MUST move to entry price. This is a hard requirement.**

---

## Take Profit Levels (Fixed)

### TP1 - 1% from Entry
- **Price**: Entry + 1%
- **Close**: 10% of position
- **Remaining**: 90%
- **Action**: ⚠️ **CRITICAL** - Move stop-loss to entry price immediately

### TP2 - 2% from Entry
- **Price**: Entry + 2%
- **Close**: 15% of position (from initial)
- **Remaining**: 75%

### TP3 - 5% from Entry
- **Price**: Entry + 5%
- **Close**: 35% of position (from initial)
- **Remaining**: 40%

### TP4 - 6.5% from Entry
- **Price**: Entry + 6.5%
- **Close**: 35% of position (from initial)
- **Remaining**: 5%

### TP5 - 8% from Entry
- **Price**: Entry + 8%
- **Close**: 50% of remaining position (2.5% of initial)
- **Remaining**: 2.5% (runner - manual close)

---

## Stop Loss Management

### Initial Stop Loss
- **Distance**: 5% below entry (for BUY orders)
- **Type**: STOP_MARKET order
- **Quantity**: Full position size

### After TP1 (CRITICAL)
- **New Stop Loss**: Entry price (breakeven)
- **Action**: Cancel old stop-loss, place new one at entry
- **Failure Handling**: If this fails, the system will raise an error (critical requirement)

---

## Implementation Details

### Files Created
1. `position_manager.py` - Tracks open positions and quantities
2. `tp_sl_manager.py` - Handles TP/SL order placement and monitoring

### Key Features
- **Position Tracking**: Tracks remaining quantity after each TP
- **Automatic TP Orders**: Places all TP limit orders on entry
- **Stop-Loss Management**: Monitors TP1 and moves SL to entry
- **Background Monitoring**: Continuous monitoring thread checks TP/SL status

### Monitoring
- Background thread checks every 5 seconds
- Verifies TP1 execution
- Moves stop-loss to entry when TP1 fills
- Tracks all TP levels and updates position quantities

---

## Order Flow

1. **Entry**: Market BUY order placed
2. **Initial SL**: Stop-loss at 5% below entry
3. **TP Orders**: All 5 TP limit orders placed simultaneously
4. **Monitoring**: Background thread monitors order status
5. **TP1 Hit**: When TP1 fills:
   - Cancel old stop-loss
   - Place new stop-loss at entry price
   - Update remaining quantity (90% left)
6. **Subsequent TPs**: As each TP fills, update remaining quantity
7. **TP5**: Closes 50% of remaining, leaves 2.5% as runner

---

## Error Handling

### Critical Errors
- **Cannot move SL to entry after TP1**: Raises exception (project requirement)
- **TP1 order not found**: Logs error, continues monitoring
- **Stop-loss placement fails**: Logs critical error

### Non-Critical Errors
- TP order placement failures (logged but don't stop execution)
- Order status check failures (retry on next cycle)

---

## Testing Checklist

- [ ] TP1 executes and closes 10% of position
- [ ] Stop-loss moves to entry after TP1 (CRITICAL)
- [ ] TP2 executes and closes 15% of position
- [ ] TP3 executes and closes 35% of position
- [ ] TP4 executes and closes 35% of position
- [ ] TP5 executes and closes 50% of remaining
- [ ] 2.5% remains as runner
- [ ] Stop-loss at entry protects remaining position

---

## Notes

- All TP levels are **fixed** (not configurable) as per requirements
- Only stop-loss percentage is configurable (default: 5%)
- Position quantities are tracked precisely
- System will fail loudly if critical requirement (SL to entry) cannot be met


