# Prompt Caching Implementation

## Overview

Implemented Anthropic's prompt caching feature to reduce costs and latency by caching the CLAUDE.md instructions and bot workflow rules.

## Changes Made

### 1. Agent Configuration ([agent/agent.py:120-143](agent/agent.py#L120-L143))

Enabled prompt caching with extended TTL (1 hour):

```python
proposal_agent = Agent(
    name="Tekne Proposal Generator",
    model=Claude(
        id="claude-sonnet-4-5",
        cache_system_prompt=True,        # Enable caching for system instructions
        betas=["extended-cache-ttl-2025-04-11"],  # Extended cache TTL
        extended_cache_time=True,        # Use 1-hour cache instead of 5-min
    ),
    # ... rest of config
)
```

### 2. Cost Tracking Updates ([core/cost_tracking.py:13-122](core/cost_tracking.py#L13-L122))

Enhanced cost tracking to include cache metrics:

**New parameters:**
- `cache_read_tokens`: Tokens read from cache (90% cost savings)
- `cache_creation_tokens`: Tokens written to cache (2x cost for 1-hour TTL)

**Tracked metrics:**
- Session-level cache usage
- Daily cache statistics
- Total cumulative cache savings

### 3. Response Logging ([agent/agent.py:174-211](agent/agent.py#L174-L211))

Added detailed cache metrics logging:

```python
# Cache metrics (Agno exposes these from Anthropic API)
cache_read_tokens = getattr(response.metrics, 'cache_read_tokens', 0)
cache_creation_tokens = getattr(response.metrics, 'cache_write_tokens', 0)

# Pricing breakdown
base_input_cost = (input_tokens / 1_000_000) * CLAUDE_INPUT_PRICE_PER_1M
cache_write_cost = (cache_creation_tokens / 1_000_000) * (CLAUDE_INPUT_PRICE_PER_1M * 2.0)
cache_read_cost = (cache_read_tokens / 1_000_000) * (CLAUDE_INPUT_PRICE_PER_1M * 0.1)
output_cost = (output_tokens / 1_000_000) * CLAUDE_OUTPUT_PRICE_PER_1M
```

## How It Works

### What Gets Cached

The system caches the complete system instructions loaded from:
- `submodules/tekne-proposals/CLAUDE.md` (~619 lines, ~19KB)
- Bot-specific workflow instructions (~112 lines)

**Total cacheable content:** ~30KB of instructions

### Cache Behavior

1. **First request (cache write):**
   - Costs 2x base input price for cached content
   - Creates a 1-hour cache entry
   - Example: 5,000 tokens × $3/M × 2.0 = **$0.030**

2. **Subsequent requests (cache read):**
   - Costs 0.1x base input price for cached content
   - Valid for 1 hour from last write
   - Example: 5,000 tokens × $3/M × 0.1 = **$0.0015**
   - **Savings: 90% vs non-cached!**

3. **Cache expiration:**
   - Cache expires after 1 hour of inactivity
   - Next request will create a new cache (write cost)

### Cost Comparison

| Scenario | Without Cache | With Cache (1st) | With Cache (2nd+) | Savings |
|----------|--------------|------------------|-------------------|---------|
| 5K tokens instructions | $0.015 | $0.030 | $0.0015 | 90% after 2nd request |
| 10 requests/hour | $0.150 | $0.030 + $0.0135 | $0.0435 | 71% total |
| 50 requests/hour | $0.750 | $0.030 + $0.0735 | $0.1035 | 86% total |

## Expected Impact

### For CLAUDE.md (~5,000 tokens estimate)

**Before caching:**
- Every request: 5,000 tokens × $3/M = **$0.015**
- 100 requests/day: **$1.50/day**
- 30 days: **$45.00/month**

**After caching (assuming 10 requests/hour average):**
- Cache writes: ~24/day × $0.030 = **$0.72/day**
- Cache reads: ~76/day × $0.0015 = **$0.11/day**
- Total: **$0.83/day** = **$24.90/month**
- **Savings: $20.10/month (45%)**

### Break-even Point

Caching breaks even after **2 requests** within the 1-hour window:
- 1st request (write): $0.030
- 2nd request (read): $0.0015
- Total: $0.0315 vs $0.030 without cache
- 3rd+ requests: Pure savings

## Monitoring

### Log Messages

**Cache write:**
```
🔄 Cache: 0 read (90% savings!) + 5,234 write
💵 Cost: $0.0000 base + $0.0314 write + $0.0000 read + $0.0120 out = $0.0434 total
```

**Cache hit:**
```
🔄 Cache: 5,234 read (90% savings!) + 0 write
💚 Cache savings: $0.0141 (vs non-cached)
💵 Cost: $0.0000 base + $0.0000 write + $0.0016 read + $0.0120 out = $0.0136 total
```

### Cost Tracking File

The `cost_tracking.txt` file now includes cache metrics:

```json
{
  "total": {
    "cost": 1.234,
    "input_tokens": 50000,
    "output_tokens": 30000,
    "cache_read_tokens": 120000,      // NEW
    "cache_creation_tokens": 15000    // NEW
  },
  "sessions": {
    "user_123": {
      "cache_read_tokens": 25000,     // NEW
      "cache_creation_tokens": 5000   // NEW
    }
  },
  "daily": {
    "2026-01-01": {
      "cache_read_tokens": 50000,     // NEW
      "cache_creation_tokens": 10000  // NEW
    }
  }
}
```

## Best Practices

### 1. Keep Instructions Stable

The cache is invalidated when system instructions change. To maximize cache hits:
- ✅ Load CLAUDE.md once at startup (already implemented)
- ✅ Avoid dynamic instruction generation
- ✅ Use in-memory cache for instructions (already implemented)

### 2. Optimal Request Patterns

Best scenarios for caching:
- ✅ Multiple requests within 1 hour
- ✅ Conversational flows (proposal creation dialog)
- ✅ Batch operations (editing multiple proposals)

Less optimal:
- ❌ Single isolated requests
- ❌ Requests >1 hour apart

### 3. Monitor Cache Effectiveness

Check logs for cache hit rate:
```bash
grep "Cache:" logs/bot.log | grep "read" | wc -l  # Cache hits
grep "Cache:" logs/bot.log | grep "write" | wc -l # Cache writes
```

## References

- [Agno Prompt Caching Documentation](https://docs.agno.com/integrations/models/native/anthropic/usage/prompt-caching)
- [Anthropic Prompt Caching Guide](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Claude Pricing](https://www.anthropic.com/pricing)

## Migration Notes

### Backward Compatibility

✅ Fully backward compatible:
- Old `cost_tracking.txt` files are automatically migrated
- Cache fields default to 0 if missing
- No breaking changes to API

### Testing

To verify caching is working:

1. **Check logs after first request:**
   ```
   Should see: "Cache: 0 read + XXXX write"
   ```

2. **Check logs after second request (within 1 hour):**
   ```
   Should see: "Cache: XXXX read + 0 write"
   Should see: "Cache savings: $0.XXXX"
   ```

3. **Monitor cost reduction:**
   ```python
   from core.cost_tracking import get_cost_stats
   stats = get_cost_stats()
   print(f"Total cache reads: {stats['total']['cache_read_tokens']:,}")
   print(f"Total cache writes: {stats['total']['cache_creation_tokens']:,}")
   ```

## Troubleshooting

### Cache Not Working

If you don't see cache metrics in logs:

1. **Verify Agno version:**
   ```bash
   pip show agno | grep Version
   # Should be >= 0.1.0 (with cache_system_prompt support)
   ```

2. **Check instructions length:**
   - Minimum ~1024 tokens required for caching
   - CLAUDE.md should be well above this threshold

3. **Verify API key has access:**
   - Extended cache TTL requires API beta access
   - Check Anthropic dashboard for beta features

### High Cache Write Costs

If seeing too many cache writes:

- Cache TTL is 1 hour - writes only happen after expiration
- Consider if requests are actually >1 hour apart
- For infrequent usage, standard 5-min cache might be more cost-effective

### Unexpected Cost Increases

If costs increase after implementation:

- First request per hour has 2x cache write cost
- Break-even is at 2 requests/hour
- For <2 requests/hour, consider disabling extended cache:
  ```python
  model=Claude(
      id="claude-sonnet-4-5",
      cache_system_prompt=True,    # Keep this
      # Remove betas and extended_cache_time
  )
  ```

## Future Enhancements

Potential improvements:

1. **Cache tool definitions separately** (currently included in system cache)
2. **Track cache hit rate metrics** (% of requests using cache)
3. **Adaptive caching** (disable for low-frequency users)
4. **Cache warming** (pre-populate cache during off-peak hours)
