# Token Optimization Strategies

## Current State (After Granular Editing)

### What We Already Optimized:
✅ **Output tokens**: Reduced by 80% using `update_proposal_field()`
- Before: ~1,700 tokens (full YAML rewrite)
- After: ~350 tokens (field update only)
- **Savings**: ~$0.03 per edit

## Further Optimization: Input Tokens

### Problem:
Even with granular editing, we still load the **entire YAML** file to update one field:

```python
# Current approach
with open(yaml_file, 'r') as f:
    data = yaml.safe_load(f)  # ⚠️ Loads ALL 4,800 chars (~1,200 tokens)

# Navigate and update one field
data['sections'][0]['title'] = "New Title"
```

### Solutions:

## Strategy 1: Selective Reading with `yq`

Use `yq` (YAML query tool) to extract only needed fields:

```bash
# Read only meta.title (not entire file)
yq eval '.meta.title' proposal.yml
```

**Benefits**:
- ✅ Reads only specific field
- ✅ No Python YAML parsing overhead
- ✅ Faster execution
- ❌ Requires `yq` installed

**Token savings**: ~70-90% on input when reading single fields

## Strategy 2: Structure-Only Reading

New tool: `get_proposal_structure()` returns outline without content:

```
Title: Pop the Moment
Client: Coca-Cola

Sections (6):
  [0] Experience Vision
      → 0 bullets
  [1] Why This Works at Rock in Rio
      → 5 bullets
  [2] Technical Scope
  [3] Project Timeline
  [4] Investment
  [5] Team
```

**Input size**: ~200 chars vs ~4,800 chars (96% reduction!)

**Use cases**:
- User asks: "Which section has the budget?"
- Agent needs to know section count/titles
- Navigating proposal structure

## Strategy 3: Minimal Response Format

Instead of returning full YAML path in response:

```python
# Before (verbose)
return f"✅ Successfully updated {field_path} in {yaml_file_path}"

# After (minimal)
return "✅ Updated"
```

**Output token savings**: ~50-70% on confirmation messages

## Strategy 4: Smart Caching

Cache frequently accessed fields:

```python
# Cache meta fields (rarely change)
@lru_cache(maxsize=100)
def get_proposal_meta(yaml_path: str) -> dict:
    """Returns only meta fields, cached"""
    ...
```

## Estimated Total Savings

### Current Usage (with granular editing):
| Operation | Input | Output | Total | Cost |
|-----------|-------|--------|-------|------|
| Edit title | 1,200 | 350 | 1,550 | $0.05 |

### With ALL Optimizations:
| Operation | Input | Output | Total | Cost | Savings |
|-----------|-------|--------|-------|------|---------|
| Get structure | 100 | 50 | 150 | $0.001 | **98%** |
| Read field (yq) | 50 | 20 | 70 | $0.0005 | **99%** |
| Update field | 300 | 80 | 380 | $0.012 | **76%** |

## Recommendations

### Immediate (High Impact, Low Effort):
1. ✅ **Minimal responses** - Just return "✅ Updated" instead of full paths
2. ✅ **Structure-only tool** - For navigation queries
3. ⚠️ **yq for reads** - Only if we often read before writing

### Future (Lower Priority):
4. **Chunk-based editing** - Only load relevant section
5. **Diff-based updates** - Only send changed lines
6. **Binary format** - Use MessagePack instead of YAML (not worth it)

## Trade-offs

### Adding `yq`:
- ✅ Faster field reads
- ✅ Lower memory usage
- ❌ Extra dependency
- ❌ Fallback complexity

### Minimal responses:
- ✅ Free savings
- ✅ No code complexity
- ⚠️ Less verbose (might be desired?)

### Structure-only reading:
- ✅ Huge savings for navigation
- ✅ No dependencies
- ⚠️ Requires new tool

## Implementation Priority

1. **Phase 1** (Do Now): Minimal responses ⚡
2. **Phase 2** (This Week): Structure-only tool 📋
3. **Phase 3** (Optional): yq integration 🔧

## Real Example

### User: "Change the title to something creative"

**Current flow**:
1. Load full YAML (1,200 tokens input)
2. Generate new title
3. Update field
4. Return verbose message (350 tokens output)
**Total**: ~1,550 tokens = **$0.05**

**Optimized flow**:
1. Read only `meta.title` with yq (50 tokens)
2. Generate new title
3. Update field with minimal response (80 tokens)
**Total**: ~130 tokens = **$0.004**

**Savings**: **92% per operation** 💰

## Next Steps

Want to implement any of these? The easiest wins are:
1. Minimal response messages (5 min)
2. Structure-only tool (30 min)
3. yq integration (1-2 hours)
