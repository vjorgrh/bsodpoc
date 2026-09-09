# Pytest Automation Documentation Index

## 📚 Complete Documentation Map

### 1. **QUICK-REFERENCE.md** ⚡ START HERE
**Best for:** Quick answers, cheat sheets, command reference
- 1-minute overview
- Command cheat sheet
- Cleanup flags guide
- Troubleshooting Q&A
- Memory savings table

**Read if you:** Just want to use it quickly

---

### 2. **PYTEST-AUTOMATION.md** 📖 
**Best for:** Full usage guide and examples
- How pytest automation works
- Quick start commands
- 4-phase execution pipeline
- Cleanup system (why it matters)
- Detailed examples for different scenarios
- Migration notes from old approach

**Read if you:** Want to understand the complete system

---

### 3. **DRY-RUN-ANALYSIS.md** 🔍
**Best for:** Detailed technical breakdown of actual behavior
- Real DRY RUN output from `pytest tests/ -v`
- Line-by-line explanation of each phase
- What gets installed and why
- Installation decision tree
- Per-test breakdown (what each test needs)
- Memory timeline

**Read if you:** Want technical details of what actually happens

---

### 4. **INSTALLATION-FLOW-DIAGRAM.md** 📊
**Best for:** Visual understanding of the system
- ASCII flow diagrams
- Decision trees with branches
- Requirements folder structure
- Scenario examples with exact installations
- Real-world examples (chaos tests vs VM tests)

**Read if you:** Learn better with visual diagrams

---

### 5. **COMPLETE-PYTEST-AUTOMATION-GUIDE.md** 📚
**Best for:** Comprehensive reference (everything in one place)
- Complete architecture overview
- Full DRY RUN breakdown
- Library installation with code examples
- Memory usage timeline
- How marker detection works
- Running tests different ways
- Cleanup flags explained
- Summary tables

**Read if you:** Want one comprehensive document with all info

---

### 6. **MODULAR-REQUIREMENTS-QUICK-START.md** 📦
**Best for:** Understanding the modular requirements structure
- Requirements folder organization
- What goes in each file
- Installation syntax
- Cleanup flags reference
- Memory savings by library

**Read if you:** Want to understand the requirements/ directory

---

## 🎯 Quick Navigation by Use Case

### "I just want to run tests"
→ Read: **QUICK-REFERENCE.md**
- Just copy commands from the cheat sheet

### "How does it actually work?"
→ Read: **DRY-RUN-ANALYSIS.md**
- See the real output and explanation

### "I need visual explanation"
→ Read: **INSTALLATION-FLOW-DIAGRAM.md**
- Flow diagrams and decision trees

### "I need everything in one place"
→ Read: **COMPLETE-PYTEST-AUTOMATION-GUIDE.md**
- Comprehensive reference document

### "What are the cleanup options?"
→ Read: **PYTEST-AUTOMATION.md** (Migration section)
- All cleanup scenarios explained

---

## 📋 What Each Documentation Covers

| Document | Length | Audience | Focus |
|----------|--------|----------|-------|
| QUICK-REFERENCE | 3KB | Developers | Cheat sheet |
| PYTEST-AUTOMATION | 5KB | Users | Full guide |
| DRY-RUN-ANALYSIS | 9KB | Technical | Actual behavior |
| INSTALLATION-FLOW-DIAGRAM | 14KB | Visual learners | Diagrams |
| COMPLETE-PYTEST-AUTOMATION-GUIDE | 14KB | Reference | Everything |
| MODULAR-REQUIREMENTS-QUICK-START | 7KB | Advanced users | Requirements details |

---

## 🔧 The System at a Glance

### When you run `pytest tests/ -v`

```
PHASE 1: Pre-cleanup
  └─ Remove old optional libraries

PHASE 2: Modular install (marker-driven)
  ├─ Always: base.txt + vm.txt + reporting.txt
  └─ If @pytest.mark.krkn: krknlib.txt
  └─ If @pytest.mark.benchmark: benchmark.txt

PHASE 3: Run tests
  └─ All dependencies available

PHASE 4: Post-cleanup (if tests pass + flags)
  └─ Remove optional libs to free memory
```

**Memory:** 165MB installed, 55MB final (with --cleanup-all)

---

## 📊 Key Numbers

| Item | Size | When |
|------|------|------|
| base.txt | 50MB | Always |
| vm.txt | 5MB | Always |
| krknlib.txt | 80MB | If @krkn marker |
| benchmark.txt | 0MB | If @benchmark marker |
| reporting.txt | 30MB | Always |
| **Total** | **165MB** | Full suite |
| **Minimal** | **55MB** | After cleanup |
| **Saved** | **110MB** | With --cleanup-all |

---

## 🚀 Getting Started

### Beginner
1. Read **QUICK-REFERENCE.md** (5 min)
2. Run: `pytest tests/ -v`
3. Done!

### Intermediate
1. Read **QUICK-REFERENCE.md** (5 min)
2. Read **PYTEST-AUTOMATION.md** (10 min)
3. Run with cleanup: `pytest tests/ -v --cleanup-all`
4. Done!

### Advanced
1. Read **DRY-RUN-ANALYSIS.md** (15 min)
2. Read **INSTALLATION-FLOW-DIAGRAM.md** (10 min)
3. Read **COMPLETE-PYTEST-AUTOMATION-GUIDE.md** (20 min)
4. Understand marker detection and conditional installs
5. Customize requirements/ files as needed

---

## ✅ Verification Checklist

After reading documentation, verify you understand:

- [ ] What PHASE 1 (pre-cleanup) does
- [ ] What PHASE 2 (modular install) does
- [ ] How test markers drive dependency installation
- [ ] Why krkn-lib is installed conditionally
- [ ] How to use `--cleanup-*` flags
- [ ] Memory savings with cleanup enabled
- [ ] What happens if tests fail (keep deps)
- [ ] How to run only specific tests

---

## 🔗 Related Files

### Implementation
```
conftest.py                      # pytest entrypoint
scripts/pytest_automation.py     # automation logic
```

### Requirements
```
requirements/
├── base.txt          (50MB)
├── vm.txt            (5MB)
├── krknlib.txt       (80MB)
├── benchmark.txt     (0MB)
└── reporting.txt     (30MB)
```

### Tests
```
tests/
├── test_chaos.py     (uses @pytest.mark.krkn)
└── test_sample1.py   (uses @pytest.mark.bsod, @pytest.mark.benchmark)
```

---

## 💡 Pro Tips

1. **Quick test:** `pytest tests/test_sample1.py -v` (85MB)
2. **Full test + cleanup:** `pytest tests/ -v --cleanup-all` (55MB final)
3. **Debugging:** Don't use cleanup flags to keep all deps
4. **Marker-driven:** Add @pytest.mark.krkn to tests that need krkn-lib
5. **Memory monitoring:** Check before/after with `du -sh .venv`

---

## 📞 Common Questions

**Q: Which doc should I read first?**
A: QUICK-REFERENCE.md (5 min cheat sheet)

**Q: How much memory does it save?**
A: 110MB with --cleanup-all

**Q: Can I customize requirements files?**
A: Yes! Edit requirements/*.txt directly

**Q: How do I add new marker detection?**
A: Edit scripts/pytest_automation.py, add to pytest_collection_finish()

**Q: What if a test needs a library not installed?**
A: Add the library to the appropriate requirements/*.txt file and re-run

---

## 🎓 Learning Path

### Level 1: User
- Read: QUICK-REFERENCE.md
- Do: Run `pytest tests/ -v`

### Level 2: Advanced User
- Read: QUICK-REFERENCE.md + PYTEST-AUTOMATION.md
- Do: Run with `--cleanup-all` flag

### Level 3: Power User
- Read: All documentation
- Do: Customize requirements/ files, add markers

### Level 4: Developer
- Read: DRY-RUN-ANALYSIS.md + COMPLETE-PYTEST-AUTOMATION-GUIDE.md
- Do: Modify scripts/pytest_automation.py logic

---

## 🔄 Documentation Updates

- **QUICK-REFERENCE.md**: Update with new cleanup flags
- **PYTEST-AUTOMATION.md**: Update with new scenarios
- **DRY-RUN-ANALYSIS.md**: Update with real DRY RUN outputs
- **INSTALLATION-FLOW-DIAGRAM.md**: Update with new decision trees
- **COMPLETE-PYTEST-AUTOMATION-GUIDE.md**: Comprehensive refresh
- **MODULAR-REQUIREMENTS-QUICK-START.md**: Update with new requirements

---

**Choose a document and get started! 🚀**
