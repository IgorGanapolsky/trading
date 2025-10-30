# ⚡ DAILY QUICKSTART GUIDE

## What To Do Each Day (30 seconds)

```bash
cd /Users/ganapolsky_i/workspace/git/igor/trading
python3 daily_checkin.py
```

That's it! That's your entire daily routine.

---

## What You'll See

```
📊 DAILY CHECK-IN REPORT
📅 Thursday, October 30, 2025 at 10:00 AM

🎯 30-DAY CHALLENGE PROGRESS
Day 2 of 30 (7% complete)
Days Remaining: 28

💰 ACCOUNT SUMMARY
Total Equity:     $100,015.00
Cash:             $99,992.00
Positions Value:  $     23.00
P/L:              $+    15.00 (+0.015%)

📈 CURRENT POSITIONS (2)
📈 SPY   | $6.00 → $6.50 | P/L: $+0.50
📈 GOOGL | $2.00 → $2.20 | P/L: $+0.20

🔄 TODAY'S TRADES (2)
✅ T1_CORE    | QQQ   | $6.00
✅ T2_GROWTH  | MSFT  | $2.00
```

---

## When Things Look Good 📈

**Equity going up? P/L positive?**

✅ System is working
✅ Keep letting it run
✅ Don't change anything

**Your action**: None. Let it compound.

---

## When Things Look Bad 📉

**Equity going down? P/L negative?**

⚠️ Normal market volatility
⚠️ Don't panic
⚠️ Review after 7-10 days

**Your action**: Stay patient. Check in tomorrow.

---

## Weekly Check (Every Sunday)

```bash
python3 daily_checkin.py  # Regular report

# Then ask yourself:
# 1. Am I profitable this week?
# 2. Are positions making sense?
# 3. Any red flags?
# 4. Should I adjust anything?
```

**If week was good**: Keep going
**If week was bad**: Wait another week
**If 3 bad weeks**: Review strategy

---

## Monthly Review (After 30 Days)

```bash
python3 daily_checkin.py

# Evaluate:
# - Total P/L
# - Win rate
# - Max drawdown
# - Consistency

# Decision:
# - If profitable → Consider going live (50% size)
# - If break-even → Continue paper trading 30 more days
# - If losing → Analyze and adjust strategy
```

---

## Emergency Commands

### System Not Running?
```bash
crontab -l | grep autonomous_trader
# Should show cron job

# If missing:
./setup_cron.sh
```

### Check Today's Execution
```bash
tail -f logs/cron.log
```

### Manual Run (Testing)
```bash
python3 autonomous_trader.py
```

---

## Questions to Ask Daily

### Is the system running?
```bash
ls -lt data/trades*.json | head -1
# Should show today's date
```

### What's my current P/L?
```bash
python3 daily_checkin.py | grep "Total P/L"
```

### What positions do I have?
```bash
python3 check_positions.py
```

### What trades executed today?
```bash
cat data/trades_$(date +%Y-%m-%d).json
```

---

## Red Flags to Watch For

❌ **Cron job not running** → Recreate with `./setup_cron.sh`
❌ **No trades executing** → Check `logs/cron.log`
❌ **P/L dropping fast** → Circuit breaker should trigger
❌ **Same symbol every day** → Rotation might be stuck
❌ **Orders not filling** → Market might be closed

---

## Success Indicators

✅ **Daily trades executing** → System working
✅ **Positions accumulating** → Building portfolio
✅ **P/L trending up** → Strategy working
✅ **No error logs** → Code stable
✅ **State file updating** → Memory working

---

## Your Daily Workflow

### Morning (After Market Open)
```bash
# 9:35 AM: System auto-trades
# 10:00 AM: You check results

python3 daily_checkin.py
```

### Mid-Day (Optional)
```bash
# If curious, check positions
python3 check_positions.py
```

### Evening (Optional)
```bash
# Review what happened
cat data/trades_$(date +%Y-%m-%d).json
```

---

## Remember

🎯 **Goal**: $10/day × 30 days = $300 invested
📊 **Target**: 10% return = $30 profit
⏰ **Timeline**: 30 days for initial validation
✅ **Success**: Positive P/L, consistent execution

**Don't overthink it. Let the system work.**

---

## TL;DR

**Every morning**:
```bash
python3 daily_checkin.py
```

**Every Sunday**:
```bash
python3 daily_checkin.py
# Review the week
```

**After 30 days**:
```bash
python3 daily_checkin.py
# Make go-live decision
```

**That's it!** 🚀
