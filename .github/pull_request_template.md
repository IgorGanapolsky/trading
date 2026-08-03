# Pull request

## Work item

- Linear issue:
- Agent:
- Base SHA:
- Branch/worktree:
- Files or systems claimed:

## Change

- Scope:
- Deleted surfaces and recovery impact:
- Out of scope:

## Verification

- [ ] Targeted tests
- [ ] `make check`
- [ ] RAG read/write round trip when RAG changes
- [ ] Orchestration smoke test when orchestration changes
- [ ] `TRADING_ENV=paper make dry-run` when operational paths change
- [ ] CI green on this exact head SHA

## Evidence boundaries

- Test result:
- CI run:
- Protected-system result:
- Broker/order/fill impact: none unless explicitly evidenced here

## Coordination

- [ ] Linear issue and vault claim updated
- [ ] No overlapping active claim or worktree
- [ ] Claim will be marked done or released after merge
