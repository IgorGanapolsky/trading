# Pull request

## Work item

- Linear issue:
- Agent:
- Base SHA:
- Branch/worktree:
- Files or systems claimed:
- Coordination legacy reason:

## Change

- Scope:
- Deleted surfaces and recovery impact:
- Out of scope:

## Security Impact Assessment

Please consider and describe the security implications of your changes:

- [ ] No security impact
- [ ] Low security impact
- [ ] Medium security impact
- [ ] High security impact

Security considerations:
- Does this change affect credential handling? 
- Does this change modify access controls?
- Does this change introduce new dependencies?
- Does this change modify workflow permissions?
- Have secrets been properly handled without hardcoding?

## Verification

- [ ] Targeted tests
- [ ] `make check`
- [ ] RAG read/write round trip when RAG changes
- [ ] Orchestration smoke test when orchestration changes
- [ ] `TRADING_ENV=paper make dry-run` when operational paths change
- [ ] CI green on this exact head SHA
- [ ] Security implications have been considered and addressed
- [ ] Dependencies have been reviewed for security vulnerabilities
- [ ] No hardcoded secrets or credentials have been added

## Evidence boundaries

- Test result:
- CI run:
- Protected-system result:
- Broker/order/fill impact: none unless explicitly evidenced here

## Coordination

- [ ] Linear issue and vault claim updated
- [ ] No overlapping active claim or worktree
- [ ] Claim will be marked done or released after merge
