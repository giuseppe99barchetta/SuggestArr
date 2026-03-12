# SuggestArr Design System

> **Single source of truth for all visual styling in SuggestArr.**

---

## 📚 Documentation

| Document | Purpose | Audience |
|----------|---------|----------|
| **[variables.css](./variables.css)** | 🏛️ **Canonical token definitions** | All developers |
| **[DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)** | 📖 Complete design system guide | New contributors, design review |
| **[DESIGN_TOKENS_CHEATSHEET.md](./DESIGN_TOKENS_CHEATSHEET.md)** | ⚡ Quick reference for daily use | Active developers |
| **[MIGRATION_ROADMAP.md](./MIGRATION_ROADMAP.md)** | 🗺️ Refactoring tracker | Maintainers, contributors |

---

## 🚀 Quick Start

### For New Developers

1. **Read the cheatsheet:** [DESIGN_TOKENS_CHEATSHEET.md](./DESIGN_TOKENS_CHEATSHEET.md) (5 min)
2. **Bookmark for reference:** Keep it open while coding
3. **Follow the rules:** Always use design tokens, never hardcode values

### For Contributors

Before submitting a PR with style changes:

1. ✅ All colors use `var(--color-*)` or `var(--surface-*)`
2. ✅ All spacing uses `var(--spacing-*)`
3. ✅ All font sizes use `var(--font-size-*)`
4. ✅ All shadows use `var(--shadow-*)`
5. ✅ All border-radius uses `var(--radius-*)`

### For Maintainers

Track migration progress in [MIGRATION_ROADMAP.md](./MIGRATION_ROADMAP.md).

---

## 🎨 Design Token Categories

### **Colors** ([variables.css#L17-L89](./variables.css))
- Surface hierarchy (backgrounds)
- Semantic colors (success, warning, error, info)
- Text colors
- Border colors
- Alpha transparency modifiers

### **Spacing** ([variables.css#L91-L108](./variables.css))
- 8px-based scale (2xs → 3xl)
- Use for ALL margins, paddings, gaps

### **Typography** ([variables.css#L110-L163](./variables.css))
- Font sizes (xs → 5xl)
- Font weights (normal → extrabold)
- Line heights

### **Elevation** ([variables.css#L165-L190](./variables.css))
- Shadow scale (sm → 2xl)
- Focus states
- Glow effects

### **Border Radius** ([variables.css#L192-L205](./variables.css))
- Consistent rounding (sm → xl, full)

### **Component Density** ([variables.css#L207-L297](./variables.css))
- Button sizing (sm, md, lg)
- Input sizing (sm, md, lg)
- Card structure
- Modal structure
- Badges, dropdowns, etc.

---

## 📁 File Structure

```
client/src/assets/styles/
├── variables.css               # ⭐ CANONICAL - Design tokens
├── global.css                  # Global styles, utility classes
├── theme.css                   # ⚠️  DEPRECATED - Legacy tokens (to be refactored)
│
├── DESIGN_SYSTEM.md            # Complete design system guide
├── DESIGN_TOKENS_CHEATSHEET.md # Quick reference
├── MIGRATION_ROADMAP.md        # Refactoring tracker
├── README.md                   # This file
│
├── wizard.css                  # Wizard-specific styles
├── dashboardPage.css           # Dashboard-specific styles
├── requestsPage.css            # Requests page styles
├── aiSearchPage.css            # AI Search page styles
├── logs.css                    # Logs page styles
├── toast-custom.css            # Toast notification overrides
└── advancedFilterConfig.css    # Advanced filter styles
```

---

## ⚠️ Critical Information

### DO ✅

```css
/* Use design tokens */
.my-component {
  background: var(--surface-elevated);
  padding: var(--spacing-lg);
  font-size: var(--font-size-base);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}
```

### DON'T ❌

```css
/* Hardcoded values */
.my-component {
  background: rgba(0, 0, 0, 0.8);
  padding: 1.5rem;
  font-size: 16px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}
```

---

## 🔧 Migration Status

**Current State:** ⚠️ In Progress

The codebase is being migrated from a legacy dual-token system to a unified design system.

### Completion Status

- [x] **Phase 1:** Design system definition ✅
- [ ] **Phase 2:** Core stylesheets (In Progress)
- [ ] **Phase 3:** Vue components
- [ ] **Phase 4:** Enforcement & linting

See [MIGRATION_ROADMAP.md](./MIGRATION_ROADMAP.md) for detailed tracking.

### Known Issues

1. **`theme.css` conflicts with `variables.css`**
   - Contains duplicate token definitions with different values
   - Must be refactored to use canonical tokens
   - **Status:** Blocking

2. **Widespread hardcoded values**
   - 100+ hardcoded colors
   - 60+ hardcoded spacing values
   - 40+ hardcoded font sizes
   - **Status:** Being addressed per migration roadmap

---

## 📖 Usage Examples

### Button Variants

```css
/* Primary button (default size) */
.btn-primary {
  height: var(--btn-height-md);
  padding: 0 var(--btn-padding-x-md);
  font-size: var(--btn-font-size-md);
  font-weight: var(--font-weight-semibold);
  background: var(--color-primary);
  color: white;
  border-radius: var(--btn-border-radius);
  transition: var(--transition-base);
}

/* Success button (large) */
.btn-success-lg {
  height: var(--btn-height-lg);
  padding: 0 var(--btn-padding-x-lg);
  font-size: var(--btn-font-size-lg);
  background: var(--color-success);
  color: white;
  border-radius: var(--btn-border-radius);
}
```

### Form Input

```css
.form-input {
  height: var(--input-height-md);
  padding: 0 var(--input-padding-x-md);
  font-size: var(--input-font-size-md);
  background: var(--surface-interactive);
  border: 1px solid var(--color-border-light);
  border-radius: var(--input-border-radius);
  color: var(--color-text-primary);
}

.form-input:focus {
  outline: none;
  border-color: var(--color-border-focus);
  box-shadow: var(--shadow-focus);
}
```

### Card Component

```css
.card {
  background: var(--card-background);
  padding: var(--card-padding-md);
  border-radius: var(--card-border-radius);
  border: 1px solid var(--card-border-color);
  box-shadow: var(--shadow-sm);
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
  transition: var(--transition-base);
}

.card-header {
  padding-bottom: var(--spacing-md);
  margin-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--color-border-light);
}
```

### Alert Messages

```css
.alert-success {
  background: var(--color-success-alpha-10);
  color: var(--color-success);
  border: 1px solid var(--color-success);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}

.alert-error {
  background: var(--color-error-alpha-10);
  color: var(--color-error);
  border: 1px solid var(--color-error);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}
```

---

## 🎯 Design Principles

### 1. Consistency
Every component should feel like part of the same product.

### 2. Maintainability
Changes to design tokens propagate automatically across the entire app.

### 3. Scalability
Adding new components is faster with pre-defined patterns.

### 4. Accessibility
Standard spacing and typography ensure better readability.

### 5. Performance
Reduced CSS duplication through token reuse.

---

## 🧪 Testing Checklist

Before merging style changes:

- [ ] Visual regression test on all affected pages
- [ ] Responsive behavior (mobile, tablet, desktop)
- [ ] Dark mode compatibility (if applicable)
- [ ] Keyboard navigation still works
- [ ] No hardcoded values introduced
- [ ] Design tokens used correctly

---

## 🤝 Contributing

### Adding New Components

1. Import design tokens (automatically available via `global.css`)
2. Use only design tokens for styling
3. Follow component density rules (see [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md#component-patterns))
4. Document any edge cases

### Modifying Existing Components

1. Check if component is already in migration queue
2. Follow migration workflow (see [MIGRATION_ROADMAP.md](./MIGRATION_ROADMAP.md#migration-workflow-per-file))
3. Update roadmap with completion status

### Proposing New Tokens

If you need a value not in the design system:

1. Check if existing token can be used (or calculated)
2. Consult design system guide for rationale
3. Open issue/discussion before adding new tokens
4. Document use case and rationale

---

## 🔗 Related Resources

- **CONTRIBUTING.md** - General contribution guidelines

